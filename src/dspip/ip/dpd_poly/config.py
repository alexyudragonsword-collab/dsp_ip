"""``DpdPolyConfig``: every bit width, scale exponent and shift of the dpd_poly datapath.

Rule 2 says bit widths are configuration, not constants. This module derives one frozen
configuration from the consumer's export (integer coefficient JSON + the calibration block
of input samples) and the requested widths, tracks the scale exponent of every integer
quantity through the datapath, and emits the generated ``dims.svh`` the RTL is built with.

Scale bookkeeping (value = int · 2^exp):

================  ===========================================  ==========================
quantity          how it is made                               exp
================  ===========================================  ==========================
x code            round_half_even(x / 2^e_in), sat w_in         e_in
a (envelope)      isqrt((I²+Q²) << 2F)                          e_in - F
pw_k              sat_u(w_pw, rshift_round(a^k, q_k))           k·(e_in - F) + q_k
envp (2 factors)  sat_u(w_pw, rshift_round(pw·pw, q_pair))      sum of the two + q_pair
phi_c             x · envp                                      e_in + exp(envp)
code_phi_c        sat(w_phi, rshift_round(phi_c, s_c))          e_c = exp(phi_c) + s_c
code_w            from the export                               e_w
prod_c            code_w · code_phi_c (complex)                 e_w + e_c
acc               Σ prod_c << (e_c - e_min)                     e_w + e_min
y                 sat(w_out, rshift_round(acc, s_out))          e_out = e_in + out_headroom
================  ===========================================  ==========================

``e_c`` is chosen per column with upstream's rule (``_pow2_step``: the smallest power-of-two
step that covers the column's peak over the calibration block with qmax = 2^(W-1)-1), so the
integer datapath quantizes each basis column to the same grid the float model did. In-datapath
rounding is round-half-up (Halo's ``rshift_round``); only the offline input quantization is
round-half-even like upstream — a deliberate, documented difference.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass

import numpy as np

from dspip.fixed import bits_for_signed
from dspip.ip.dpd_poly import datapath as dp
from dspip.ip.dpd_poly.terms import (
    Term,
    depths,
    line_index,
    max_k,
    terms_from_model,
)

PER_TERM_FIELD_BITS = 8  # width of each per-term entry in the packed dims vectors


def ceil_log2_ratio(peak: int, qmax: int) -> int:
    """ceil(log2(peak / qmax)) computed exactly on integers (peak > 0)."""
    e = 0
    while (qmax << e) < peak:          # e >= 0 branch
        e += 1
    if e == 0:
        while e > -64 and (peak << (-(e - 1))) <= qmax:   # peak <= qmax * 2^(e-1) ?
            e -= 1
    return e


def quantize_input(x: np.ndarray, e_in: int, w_in: int) -> tuple[np.ndarray, np.ndarray]:
    """Offline input quantization (round-half-even like upstream's ``np.round``), int64."""
    x = np.asarray(x, dtype=complex)
    lo, hi = -(1 << (w_in - 1)), (1 << (w_in - 1)) - 1
    step = 2.0 ** e_in
    xi = np.clip(np.round(x.real / step), lo, hi).astype(np.int64)
    xq = np.clip(np.round(x.imag / step), lo, hi).astype(np.int64)
    return xi, xq


@dataclass(frozen=True)
class DpdPolyConfig:
    basis: str
    model_class: str
    model_config: tuple[tuple[str, int], ...]
    w_in: int
    w_coef: int
    w_phi: int
    w_pw: int
    w_out: int
    env_frac: int
    e_in: int
    e_out: int
    e_w: int
    coef_re: tuple[int, ...]
    coef_im: tuple[int, ...]
    terms: tuple[Term, ...]
    e_c: tuple[int, ...]
    s_c: tuple[int, ...]
    al_c: tuple[int, ...]
    q_k: tuple[int, ...]  # q_k[k-1], k = 1..max_k
    q_pair: tuple[int, ...]  # per term; 0 unless the term has two envelope factors
    w_acc: int
    s_out: int
    lead: int
    x_depth: int
    env_depth: int
    cal_n: int

    # ---- derived scalars -----------------------------------------------------------
    @property
    def n_terms(self) -> int:
        return len(self.terms)

    @property
    def w_env(self) -> int:
        return self.w_in + self.env_frac

    @property
    def max_k(self) -> int:
        return len(self.q_k)

    @property
    def exp_a(self) -> int:
        return self.e_in - self.env_frac

    def exp_pw(self, k: int) -> int:
        return k * self.exp_a + self.q_k[k - 1]

    def exp_envp(self, t: Term) -> int:
        if not t.env:
            return 0
        if len(t.env) == 1:
            return self.exp_pw(t.env[0][1])
        return self.exp_pw(t.env[0][1]) + self.exp_pw(t.env[1][1]) + self.q_pair[t.col]

    def exp_phi(self, t: Term) -> int:
        return self.e_in + self.exp_envp(t)

    @property
    def e_min(self) -> int:
        return min(self.e_c)

    def x_idx(self, t: Term) -> int:
        return line_index(t.x_delay, self.lead)

    def env_idx(self, t: Term, i: int) -> int:
        return line_index(t.env[i][0], self.lead)

    @property
    def model_config_dict(self) -> dict:
        return dict(self.model_config)

    # ---- construction --------------------------------------------------------------
    @classmethod
    def derive(cls, coeffs: dict, x_cal: np.ndarray, *, basis: str = "",
               w_in: int | None = None, w_coef: int | None = None, w_phi: int | None = None,
               w_pw: int | None = None, w_out: int | None = None, env_frac: int = 0,
               in_headroom: int = 0, out_headroom: int = 0) -> DpdPolyConfig:
        """Derive a configuration from an exported coeffs JSON (dict) and the calibration
        block ``x_cal`` (complex float, the consumer's reference input)."""
        W = int(coeffs["w_bits"])
        w_in = w_in or W
        w_coef = w_coef or W
        w_phi = w_phi or W
        w_pw = w_pw or W
        w_out = w_out or w_in
        terms = terms_from_model(coeffs["model_class"], coeffs["config"])
        lead, x_depth, env_depth = depths(terms)
        mk = max_k(terms)
        coef_re = tuple(int(v) for v in coeffs["coeffs_real"])
        coef_im = tuple(int(v) for v in coeffs["coeffs_imag"])
        if len(coef_re) != len(terms):
            raise ValueError(f"{len(coef_re)} coefficients for {len(terms)} terms")
        cmax = max(max(map(abs, coef_re)), max(map(abs, coef_im)))
        if cmax >= (1 << (w_coef - 1)) + 1:
            raise ValueError(f"coefficient codes need more than w_coef={w_coef} bits")

        # input scale: upstream rule on the calibration block peak
        x_cal = np.asarray(x_cal, dtype=complex)
        peak = float(max(np.abs(x_cal.real).max(), np.abs(x_cal.imag).max()))
        qmax = (1 << (w_in - 1)) - 1
        e_in = (int(math.ceil(math.log2(peak / qmax))) if peak > 0 else 0) + in_headroom
        xi, xq = quantize_input(x_cal, e_in, w_in)

        a_max = dp.envelope_max(w_in, env_frac)
        q_k = tuple(dp.power_shift(a_max, k, w_pw) for k in range(1, mk + 1))
        pw_max = [1] + [dp.power(a_max, k, q_k[k - 1], w_pw) for k in range(1, mk + 1)]
        # two-factor terms: shift the pw·pw product so its bound fits w_pw bits (a fixed
        # q_pair = w_pw silently zeroes the product when pw_1 does not fill the word)
        q_pair = tuple(
            dp.pair_shift(pw_max[t.env[0][1]], pw_max[t.env[1][1]], w_pw) if len(t.env) == 2 else 0
            for t in terms)

        proto = cls(basis=basis or coeffs["model_class"], model_class=coeffs["model_class"],
                    model_config=tuple(sorted((k, int(v)) for k, v in coeffs["config"].items())),
                    w_in=w_in, w_coef=w_coef, w_phi=w_phi, w_pw=w_pw, w_out=w_out,
                    env_frac=env_frac, e_in=e_in, e_out=e_in + out_headroom,
                    e_w=int(coeffs["coeff_scale_exp"]), coef_re=coef_re, coef_im=coef_im,
                    terms=terms, e_c=(0,) * len(terms), s_c=(0,) * len(terms),
                    al_c=(0,) * len(terms), q_k=q_k, q_pair=q_pair, w_acc=0, s_out=0,
                    lead=lead, x_depth=x_depth, env_depth=env_depth, cal_n=len(x_cal))

        # per-column scale from the integer-path peak over the calibration block
        from dspip.ip.dpd_poly.ref import phi_peaks  # local import: ref imports config

        peaks = phi_peaks(proto, xi.tolist(), xq.tolist())
        qmax_phi = (1 << (w_phi - 1)) - 1
        e_c, s_c = [], []
        for t, pk in zip(terms, peaks):
            ep = proto.exp_phi(t)
            if pk == 0:
                ec, sc = ep, 0
            else:
                ec = ep + ceil_log2_ratio(pk, qmax_phi)
                sc = ec - ep
                if sc < 0:          # column never needs the full word: no left shift in RTL
                    ec, sc = ep, 0
            e_c.append(ec)
            s_c.append(sc)
        e_min = min(e_c)
        al_c = [ec - e_min for ec in e_c]
        # accumulator bound: |Re/Im prod| <= 2 * 2^(w_coef-1) * 2^(w_phi-1), shifted, summed
        bound = sum((1 << (w_coef + w_phi - 1)) << al for al in al_c)
        w_acc = bits_for_signed(bound)
        s_out = (e_in + out_headroom) - (proto.e_w + e_min)
        if s_out < 0:
            raise ValueError(f"s_out={s_out} < 0: output scale finer than the accumulator; "
                             f"raise out_headroom or widen w_phi")
        cfg = cls(**{**asdict_shallow(proto), "e_c": tuple(e_c), "s_c": tuple(s_c),
                     "al_c": tuple(al_c), "w_acc": w_acc, "s_out": s_out})
        cfg.check_int64()
        return cfg

    def check_int64(self) -> bool:
        """True if the numpy int64 vectorised reference can run this config without
        overflow (a^k and the accumulator must fit in 63 bits)."""
        a_max = dp.envelope_max(self.w_in, self.env_frac)
        return (a_max ** self.max_k).bit_length() <= 63 and self.w_acc <= 63

    # ---- serialisation -------------------------------------------------------------
    def to_dict(self) -> dict:
        d = asdict_shallow(self)
        d["terms"] = [[t.col, t.x_delay, [list(f) for f in t.env]] for t in self.terms]
        d["model_config"] = dict(self.model_config)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> DpdPolyConfig:
        d = dict(d)
        d["terms"] = tuple(Term(c, xd, tuple(tuple(f) for f in env)) for c, xd, env in d["terms"])
        d["model_config"] = tuple(sorted((k, int(v)) for k, v in d["model_config"].items()))
        for k in ("coef_re", "coef_im", "e_c", "s_c", "al_c", "q_k", "q_pair"):
            d[k] = tuple(int(v) for v in d[k])
        return cls(**d)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=1)

    @classmethod
    def from_json(cls, s: str) -> DpdPolyConfig:
        return cls.from_dict(json.loads(s))

    # ---- RTL dims ------------------------------------------------------------------
    def to_svh_params(self, p: int = 1) -> str:
        """``dims_params.svh``: the *parameters* of the top module and the testbench, included
        inside their ``#( ... )`` parameter lists so port widths can use them and ``P`` can be
        overridden from the command line (yosys 0.33 cannot resolve package scopes in a port
        list, so a package is not an option)."""
        lines = [
            f"parameter int P         = {p},",
            f"parameter int N_TERMS   = {self.n_terms},",
            f"parameter int W_IN      = {self.w_in},",
            f"parameter int W_COEF    = {self.w_coef},",
            f"parameter int W_PHI     = {self.w_phi},",
            f"parameter int W_PW      = {self.w_pw},",
            f"parameter int W_ENV     = {self.w_env},",
            f"parameter int W_ACC     = {self.w_acc},",
            f"parameter int W_OUT     = {self.w_out},",
            f"parameter int MAX_K     = {self.max_k},",
            f"parameter int LEAD      = {self.lead},",
            f"parameter int X_DEPTH   = {self.x_depth},",
            f"parameter int ENV_DEPTH = {self.env_depth}",
        ]
        return ("// Generated by dspip.ip.dpd_poly.config.DpdPolyConfig.to_svh_params — do not "
                "edit.\n// Included inside the #( ... ) parameter list of dpd_poly and its tb.\n"
                + "\n".join(lines) + "\n")

    def to_svh(self, n_samples: int) -> str:
        """``dims.svh``: localparams included in the module *body* (per-term tables and the
        scalars ports do not need). Per-term tables are packed vectors (``[c*8 +: 8]``)
        because yosys 0.33 cannot read unpacked-array localparams and iverilog's support is
        partial."""
        B = PER_TERM_FIELD_BITS
        n = self.n_terms

        def packed(name: str, vals: list[int]) -> str:
            assert all(0 <= v < (1 << B) for v in vals), (name, vals)
            # element c lives at bits [c*B +: B]; concatenation lists MSB (last term) first
            body = ", ".join(f"{B}'d{v}" for v in reversed(vals))
            return f"localparam logic [{n * B - 1}:0] {name} = {{{body}}};"

        xd, ed0, k0, ed1, k1 = [], [], [], [], []
        for t in self.terms:
            xd.append(self.x_idx(t))
            if len(t.env) >= 1:
                ed0.append(self.env_idx(t, 0))
                k0.append(t.env[0][1])
            else:
                ed0.append(0)
                k0.append(0)
            if len(t.env) == 2:
                ed1.append(self.env_idx(t, 1))
                k1.append(t.env[1][1])
            else:
                ed1.append(0)
                k1.append(0)
        qpw = list(self.q_k) + [0] * (4 - self.max_k)
        lines = [
            "// Generated by dspip.ip.dpd_poly.config.DpdPolyConfig.to_svh — do not edit.",
            f"// basis={self.basis} W_IN={self.w_in} e_in={self.e_in} e_w={self.e_w} "
            f"e_min={self.e_min} e_out={self.e_out}",
            f"localparam int ENV_FRAC  = {self.env_frac};",
            f"localparam int S_OUT     = {self.s_out};",
            f"localparam int Q_PW1     = {qpw[0]};",
            f"localparam int Q_PW2     = {qpw[1]};",
            f"localparam int Q_PW3     = {qpw[2]};",
            f"localparam int Q_PW4     = {qpw[3]};",
            f"localparam int N_SAMPLES = {n_samples};",
            f"localparam int TF_BITS   = {B};",
            packed("T_XD", xd),
            packed("T_ED0", ed0),
            packed("T_K0", k0),
            packed("T_ED1", ed1),
            packed("T_K1", k1),
            packed("T_QP", list(self.q_pair)),
            packed("T_SH", list(self.s_c)),
            packed("T_AL", list(self.al_c)),
        ]
        return "\n".join(lines) + "\n"

    def summary(self) -> str:
        return (f"{self.basis}: {self.n_terms} terms, W_IN={self.w_in} W_COEF={self.w_coef} "
                f"W_PHI={self.w_phi} W_PW={self.w_pw} F={self.env_frac} W_ACC={self.w_acc} "
                f"W_OUT={self.w_out}; e_in={self.e_in} e_w={self.e_w} "
                f"e_c=[{min(self.e_c)},{max(self.e_c)}] s_c=[{min(self.s_c)},{max(self.s_c)}] "
                f"al_max={max(self.al_c)} S_OUT={self.s_out} lead={self.lead} "
                f"depth x/env={self.x_depth}/{self.env_depth}")


def asdict_shallow(cfg: DpdPolyConfig) -> dict:
    """``dataclasses.asdict`` recurses into Term tuples; keep them as-is."""
    return {f: getattr(cfg, f) for f in cfg.__dataclass_fields__}


__all__ = ["DpdPolyConfig", "quantize_input", "ceil_log2_ratio", "asdict", "PER_TERM_FIELD_BITS"]
