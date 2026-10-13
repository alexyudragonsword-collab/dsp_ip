"""The bit-true reference of dpd_poly — the truth the RTL must equal sample for sample.

``DpdPolyRef.run`` is a per-sample pure-``int`` loop over the primitives in ``datapath.py``,
with no numpy in the arithmetic path, so there is no word length it can silently exceed.
``DpdPolyRef.run_vec`` is a numpy int64 twin for speed; ``tests/test_ref.py`` proves the two
identical and ``run_vec`` refuses configurations int64 cannot hold (``check_int64``).

Streaming semantics (what the RTL implements): samples enter a history window one per
step; the output for sample n is produced ``lead`` steps after it entered (GMP's leading
envelope looks one sample ahead). The window is reset to zero, which is upstream's
zero-padded ``delayed()``; the ``lead`` trailing zero samples the caller feeds reproduce
its zero fill at the end of a block.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from dspip.fixed import rshift_round, saturate
from dspip.ip.dpd_poly import datapath as dp
from dspip.ip.dpd_poly.config import DpdPolyConfig


@dataclass
class SampleTrace:
    """Internal registers of one output sample (the probes ``tools/lockstep.py`` prints)."""
    n: int
    a: int
    pw: list[int]
    envp: list[int]
    phi_re: list[int]
    phi_im: list[int]
    code_re: list[int]
    code_im: list[int]
    acc_re: int
    acc_im: int
    y_re: int
    y_im: int


@dataclass
class RunResult:
    y_re: list[int]
    y_im: list[int]
    traces: dict[int, SampleTrace] = field(default_factory=dict)


class _Plan:
    """Per-term tap indices resolved once."""

    def __init__(self, cfg: DpdPolyConfig):
        self.cfg = cfg
        self.x_idx = [cfg.x_idx(t) for t in cfg.terms]
        self.kind = []     # 0: no envelope, 1: one factor, 2: two factors
        self.e0 = []
        self.k0 = []
        self.e1 = []
        self.k1 = []
        for t in cfg.terms:
            self.kind.append(len(t.env))
            self.e0.append(cfg.env_idx(t, 0) if len(t.env) >= 1 else 0)
            self.k0.append(t.env[0][1] if len(t.env) >= 1 else 0)
            self.e1.append(cfg.env_idx(t, 1) if len(t.env) == 2 else 0)
            self.k1.append(t.env[1][1] if len(t.env) == 2 else 0)


def _stream(cfg: DpdPolyConfig, plan: _Plan, x_re, x_im):
    """Generator: per output sample yields (n, a, pws, envp list, phi lists) — the part
    of the datapath before column quantization, shared with config derivation."""
    n_in = len(x_re)
    xw_re = [0] * cfg.x_depth
    xw_im = [0] * cfg.x_depth
    pw_w = [[1] + [0] * cfg.max_k for _ in range(cfg.env_depth)]
    for t in range(n_in + cfg.lead):
        sre = int(x_re[t]) if t < n_in else 0
        sim = int(x_im[t]) if t < n_in else 0
        a = dp.envelope(sre, sim, cfg.env_frac)
        pws = [1] + [dp.power(a, k, cfg.q_k[k - 1], cfg.w_pw) for k in range(1, cfg.max_k + 1)]
        xw_re.insert(0, sre)
        xw_re.pop()
        xw_im.insert(0, sim)
        xw_im.pop()
        pw_w.insert(0, pws)
        pw_w.pop()
        if t < cfg.lead:
            continue
        envp, phr, phi = [], [], []
        for c in range(cfg.n_terms):
            kind = plan.kind[c]
            if kind == 0:
                ep = 1
            elif kind == 1:
                ep = pw_w[plan.e0[c]][plan.k0[c]]
            else:
                ep = dp.env_product(pw_w[plan.e0[c]][plan.k0[c]],
                                    pw_w[plan.e1[c]][plan.k1[c]], cfg.q_pair[c], cfg.w_pw)
            pr, pi = dp.term_phi(xw_re[plan.x_idx[c]], xw_im[plan.x_idx[c]], ep)
            envp.append(ep)
            phr.append(pr)
            phi.append(pi)
        yield t - cfg.lead, a, pws, envp, phr, phi


def phi_peaks(cfg: DpdPolyConfig, x_re, x_im) -> list[int]:
    """max(|Re phi_c|, |Im phi_c|) over the block, per term (config derivation)."""
    plan = _Plan(cfg)
    peaks = [0] * cfg.n_terms
    for _n, _a, _pws, _envp, phr, phi in _stream(cfg, plan, x_re, x_im):
        for c in range(cfg.n_terms):
            m = max(abs(phr[c]), abs(phi[c]))
            if m > peaks[c]:
                peaks[c] = m
    return peaks


class DpdPolyRef:
    def __init__(self, cfg: DpdPolyConfig):
        self.cfg = cfg
        self.plan = _Plan(cfg)

    # ---- the truth: per-sample pure ints ----------------------------------------------
    def run(self, x_re, x_im, trace_samples=()) -> RunResult:
        cfg = self.cfg
        trace_samples = set(trace_samples)
        y_re, y_im, traces = [], [], {}
        for n, a, pws, envp, phr, phi in _stream(cfg, self.plan, x_re, x_im):
            acc_re = acc_im = 0
            code_re, code_im = [], []
            for c in range(cfg.n_terms):
                cr = dp.quantize_phi(phr[c], cfg.s_c[c], cfg.w_phi)
                ci = dp.quantize_phi(phi[c], cfg.s_c[c], cfg.w_phi)
                mr, mi = dp.cmul(cr, ci, cfg.coef_re[c], cfg.coef_im[c])
                acc_re += mr << cfg.al_c[c]
                acc_im += mi << cfg.al_c[c]
                if n in trace_samples:
                    code_re.append(cr)
                    code_im.append(ci)
            yr = dp.output(acc_re, cfg.s_out, cfg.w_out)
            yi = dp.output(acc_im, cfg.s_out, cfg.w_out)
            y_re.append(yr)
            y_im.append(yi)
            if n in trace_samples:
                traces[n] = SampleTrace(n, a, pws, envp, phr, phi, code_re, code_im,
                                        acc_re, acc_im, yr, yi)
        return RunResult(y_re, y_im, traces)

    # ---- numpy int64 twin -------------------------------------------------------------
    def run_vec(self, x_re, x_im) -> tuple[np.ndarray, np.ndarray]:
        cfg = self.cfg
        if not cfg.check_int64():
            raise OverflowError("config exceeds int64 (a^k or accumulator > 63 bits); "
                                "use DpdPolyRef.run (unbounded ints)")
        from dspip.vendor.padpd.pa.memory_polynomial import delayed

        xr = np.asarray(x_re, dtype=np.int64)
        xi = np.asarray(x_im, dtype=np.int64)
        a = _isqrt_vec((xr * xr + xi * xi) << (2 * cfg.env_frac))
        pw = [np.ones_like(a)]
        hi = np.int64((1 << cfg.w_pw) - 1)
        for k in range(1, cfg.max_k + 1):
            v = rshift_round(a ** k, cfg.q_k[k - 1])
            pw.append(np.minimum(v, hi))
        acc_re = np.zeros_like(xr)
        acc_im = np.zeros_like(xr)
        for c, t in enumerate(cfg.terms):
            if not t.env:
                ep = pw[0]
            elif len(t.env) == 1:
                ep = delayed(pw[t.env[0][1]], t.env[0][0])
            else:
                p0 = delayed(pw[t.env[0][1]], t.env[0][0])
                p1 = delayed(pw[t.env[1][1]], t.env[1][0])
                ep = np.minimum(rshift_round(p0 * p1, cfg.q_pair[c]), hi)
            dx_re = delayed(xr, t.x_delay)
            dx_im = delayed(xi, t.x_delay)
            cr = saturate(rshift_round(dx_re * ep, cfg.s_c[c]), cfg.w_phi)
            ci = saturate(rshift_round(dx_im * ep, cfg.s_c[c]), cfg.w_phi)
            wr, wi = np.int64(cfg.coef_re[c]), np.int64(cfg.coef_im[c])
            acc_re += (cr * wr - ci * wi) << cfg.al_c[c]
            acc_im += (cr * wi + ci * wr) << cfg.al_c[c]
        y_re = saturate(rshift_round(acc_re, cfg.s_out), cfg.w_out)
        y_im = saturate(rshift_round(acc_im, cfg.s_out), cfg.w_out)
        return y_re, y_im


def _isqrt_vec(n: np.ndarray) -> np.ndarray:
    """Exact floor(sqrt(n)) for int64 n >= 0 (float estimate + integer fix-up)."""
    r = np.floor(np.sqrt(n.astype(np.float64))).astype(np.int64)
    for _ in range(3):
        r = np.where(r * r > n, r - 1, r)
        r = np.where((r + 1) * (r + 1) <= n, r + 1, r)
    assert np.all(r * r <= n) and np.all((r + 1) * (r + 1) > n)
    return r
