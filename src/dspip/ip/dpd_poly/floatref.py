"""Rule 2 for dpd_poly: the fixed-point reference answers to floating point.

Three comparisons, in increasing cost:

1. ``upstream_fixed_output`` — the vendored ``FixedPointPolyModel`` (PA_DPD's float
   emulation of quantization) rebuilt from the exported integer coefficients; it must
   reproduce the ``i_out/q_out`` columns of the export (validates the vendored path).
2. ``nmse_db`` of the integer reference against (1) — a torch-free proxy, run in ``pytest``.
3. ACLR through PA_DPD's neural PA surrogate (``SurrogateEval``) — exactly the recipe of
   PA_DPD ``scripts/quantize_dpd.py`` that produced the table in its
   ``docs/03_roadmap.md``: needs torch, the OpenDPD dataset and the PA_DPD checkout
   (for ``padpd.nn``); skipped when absent, mandatory in the ``fixed-vs-float`` CI job.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from dspip.ip.dpd_poly.config import DpdPolyConfig, quantize_input
from dspip.ip.dpd_poly.ref import DpdPolyRef
from dspip.vendor.padpd.deploy.fixed_point import FixedPointPolyModel
from dspip.vendor.padpd.pa.presets import ddr_volterra_default, gmp_opendpd_510

REPO = Path(__file__).resolve().parents[4]
UPSTREAM_DIR = REPO / "ip" / "dpd_poly" / "upstream" / "DPA_160MHz"
BASES = {"ddr_r1": ddr_volterra_default, "gmp510": gmp_opendpd_510}
WARMUP = 200  # PA_DPD scripts/quantize_dpd.py

# PA_DPD docs/03_roadmap.md lines 108-117 (@08b9725): ACLR_AVG dBc, DPA_160MHz, neural surrogate
UPSTREAM_TABLE = {
    "ddr_r1": {"float": -51.6, 16: -51.3, 12: -40.4, 10: -29.4},
    "gmp510": {"float": -50.2, 16: -50.1, 12: -46.6, 10: -38.5},
}


@dataclass
class UpstreamExport:
    basis: str
    w_bits: int
    coeffs: dict
    x: np.ndarray          # complex float input (refvec i_in, q_in)
    y_upstream: np.ndarray  # upstream FixedPointPolyModel float output (i_out, q_out)


def load_upstream(basis: str, w_bits: int, root: Path = UPSTREAM_DIR) -> UpstreamExport:
    coeffs = json.loads((root / f"{basis}_w{w_bits}_coeffs.json").read_text())
    d = np.loadtxt(root / f"{basis}_w{w_bits}_refvec.csv", delimiter=",", skiprows=1)
    return UpstreamExport(basis, w_bits, coeffs, d[:, 0] + 1j * d[:, 1], d[:, 2] + 1j * d[:, 3])


def upstream_model(coeffs: dict):
    """The upstream linear-params model with coefficients rebuilt from the integer codes
    (value = code · 2^exp); requantizing them is the identity, so
    ``FixedPointPolyModel`` on this model is the exact upstream fixed-point emulation."""
    m = BASES[_basis_of(coeffs)]()
    m.coeffs = (np.asarray(coeffs["coeffs_real"], dtype=float)
                + 1j * np.asarray(coeffs["coeffs_imag"], dtype=float)) * 2.0 ** coeffs["coeff_scale_exp"]
    return m


def _basis_of(coeffs: dict) -> str:
    return {"DDRVolterraModel": "ddr_r1", "GMPModel": "gmp510"}[coeffs["model_class"]]


def upstream_fixed_output(coeffs: dict, x: np.ndarray) -> np.ndarray:
    w = int(coeffs["w_bits"])
    return FixedPointPolyModel(upstream_model(coeffs), w, w)(np.asarray(x, dtype=complex))


def int_ref_output(cfg: DpdPolyConfig, x: np.ndarray, vec: bool = True) -> np.ndarray:
    """Integer reference on float input ``x``, returned as float at scale 2^e_out."""
    xi, xq = quantize_input(x, cfg.e_in, cfg.w_in)
    ref = DpdPolyRef(cfg)
    if vec:
        yr, yi = ref.run_vec(xi, xq)
    else:
        r = ref.run(xi.tolist(), xq.tolist())
        yr, yi = np.asarray(r.y_re), np.asarray(r.y_im)
    return (yr + 1j * yi) * 2.0 ** cfg.e_out


def nmse_db(ref: np.ndarray, est: np.ndarray) -> float:
    ref = np.asarray(ref)
    est = np.asarray(est)
    return float(10 * np.log10(np.sum(np.abs(est - ref) ** 2) / np.sum(np.abs(ref) ** 2)))


# ---------------------------------------------------------------------------------------
# ACLR through PA_DPD's neural surrogate (optional dependencies)
# ---------------------------------------------------------------------------------------


def find_pa_dpd_src() -> Path | None:
    """The PA_DPD checkout's ``src`` (for ``padpd.nn`` and the checkpoint)."""
    cands = [os.environ.get("DSPIP_SIBLING_PA_DPD"), "/home/user/PA_DPD",
             "/home/user/alexyudragonsword-collab/pa_dpd", str(REPO.parent / "PA_DPD"),
             str(REPO / "_siblings" / "PA_DPD")]
    for c in cands:
        if c and (Path(c) / "src" / "padpd" / "nn").exists():
            return Path(c) / "src"
    return None


def find_dataset() -> Path | None:
    cands = [os.environ.get("DSPIP_OPENDPD_DATASET"),
             "/home/user/alexyudragonsword-collab/OpenDPD/datasets/DPA_160MHz",
             str(REPO.parent / "OpenDPD" / "datasets" / "DPA_160MHz"),
             str(REPO / "_siblings" / "OpenDPD" / "datasets" / "DPA_160MHz")]
    for c in cands:
        if c and (Path(c) / "spec.json").exists():
            return Path(c)
    return None


def surrogate_available() -> bool:
    try:
        import torch  # noqa: F401
    except ImportError:
        return False
    return find_pa_dpd_src() is not None and find_dataset() is not None


class SurrogateEval:
    """PA_DPD's ACLR recipe: ``pa(predist(concat(val.x[-200:], test.x)))[200:]`` through the
    DGRU surrogate ``models/DPA_160MHz_dgru_h8_f200.pt``, ``aclr_opendpd(...)['avg_dbc']``."""

    def __init__(self, dataset_dir: Path | None = None, pa_model: Path | None = None):
        from dspip.vendor.padpd.data.opendpd import load_opendpd_dataset
        from dspip.vendor.padpd.metrics.opendpd_compat import aclr_opendpd, target_gain_opendpd

        src = find_pa_dpd_src()
        if src is None:
            raise RuntimeError("PA_DPD checkout not found (DSPIP_SIBLING_PA_DPD)")
        if str(src) not in sys.path:
            sys.path.append(str(src))
        from padpd.nn import NeuralPAModel  # noqa: E402  (needs torch)

        self.dataset_dir = Path(dataset_dir or find_dataset())
        ds = load_opendpd_dataset(str(self.dataset_dir))
        self.tr, self.va, self.te, self.spec = ds["train"], ds["val"], ds["test"], ds["spec"]
        self.fs = self.tr.sample_rate_hz
        self._aclr_args = (self.fs, self.spec["bw_main_ch"], self.spec["n_sub_ch"],
                           self.spec["nperseg"])
        self._aclr = aclr_opendpd
        self.target_gain = target_gain_opendpd(self.tr.x, self.tr.y)
        pa_model = pa_model or (src.parent / "models" / "DPA_160MHz_dgru_h8_f200.pt")
        self.pa = NeuralPAModel.load(str(pa_model))
        self.eval_x = np.concatenate([self.va.x[-WARMUP:], self.te.x])

    def aclr(self, predist) -> float:
        y = self.pa(predist(self.eval_x))[WARMUP:]
        return float(self._aclr(y, *self._aclr_args)["avg_dbc"])

    def fit_ila(self, basis: str):
        from dspip.vendor.padpd.dpd.ila import ILAPredistorter

        ila = ILAPredistorter(model_factory=BASES[basis], target_gain=self.target_gain,
                              fit_kwargs={"regularization": 1e-9})
        ila.fit_measured(self.tr.x, self.tr.y)
        return ila

    def upstream_row(self, basis: str, bits=(16, 12, 10)) -> dict:
        """One row of the upstream table, recomputed with upstream's own code."""
        ila = self.fit_ila(basis)
        model = ila.dpd_model
        row = {"float": self.aclr(ila)}
        for b in bits:
            fp = FixedPointPolyModel(model, w_bits=b, sig_bits=b)
            row[b] = self.aclr(lambda x, m=fp: m(x))
        return row

    def int_ref_aclr(self, coeffs: dict, **cfg_kwargs) -> tuple[float, DpdPolyConfig]:
        """ACLR of the integer reference configured from ``coeffs``; the scale calibration
        block is the evaluation block itself (what upstream's block-adaptive scaling
        amounts to), so the comparison isolates the integer datapath."""
        cfg = DpdPolyConfig.derive(coeffs, self.eval_x, basis=_basis_of(coeffs), **cfg_kwargs)
        return self.aclr(lambda x, c=cfg: int_ref_output(c, x)), cfg

    def int_ref_rows(self, basis: str, bits=(16, 12, 10), variants=None) -> dict:
        """{W: {variant: aclr}} of the integer reference, coefficients exported at W."""
        variants = variants or {"default": {}, "pw+4": {"w_pw_plus": 4}}
        rows = {}
        for w in bits:
            coeffs = self.export_coeffs(basis, w)
            rows[w] = {}
            for name, kw in variants.items():
                kw = dict(kw)
                if "w_pw_plus" in kw:
                    kw["w_pw"] = w + kw.pop("w_pw_plus")
                a, cfg = self.int_ref_aclr(coeffs, **kw)
                rows[w][name] = {"aclr": a, "cfg": cfg.summary()}
        return rows

    def export_coeffs(self, basis: str, w_bits: int) -> dict:
        """What ``export_deploy.py --w-bits W`` writes (in memory)."""
        from dspip.vendor.padpd.deploy.export import _int_codes

        model = self.fit_ila(basis).dpd_model
        cr, ci, e = _int_codes(model.coeffs, w_bits)
        return {"model_class": type(model).__name__, "config": model.get_config(),
                "n_coeffs": len(model.coeffs), "w_bits": w_bits, "coeff_scale_exp": e,
                "coeffs_real": cr.tolist(), "coeffs_imag": ci.tolist()}


def build_aclr_table(bits=(16, 12, 10), out: Path | None = None) -> dict:
    """The rule-2 table for dpd_poly (``examples/01_bitwidth_aclr.py`` writes it to
    ``results/aclr_table.json``): per basis, the upstream row recomputed with upstream's
    code, the integer reference's ACLR per bit width and variant, and the torch-free NMSE
    of the integer reference against the upstream export block."""
    table = {"_meta": {"dataset": "DPA_160MHz", "metric": "ACLR_AVG dBc via PA_DPD DGRU surrogate",
                       "upstream_doc": "PA_DPD@08b9725 docs/03_roadmap.md:108-117",
                       "upstream_table": {b: {str(k): v for k, v in r.items()}
                                          for b, r in UPSTREAM_TABLE.items()}}}
    ev = SurrogateEval()
    for basis in BASES:
        row = ev.upstream_row(basis, bits)
        rows = ev.int_ref_rows(basis, bits)
        nmse = {}
        for w in (16, 12):
            up = load_upstream(basis, w)
            cfg = DpdPolyConfig.derive(up.coeffs, up.x, basis=basis)
            nmse[str(w)] = nmse_db(up.y_upstream, int_ref_output(cfg, up.x))
        table[basis] = {
            "upstream_recomputed": {str(k): v for k, v in row.items()},
            "int_ref": {str(w): {name: v["aclr"] for name, v in r.items()} for w, r in rows.items()},
            "int_ref_cfg": {str(w): {name: v["cfg"] for name, v in r.items()}
                            for w, r in rows.items()},
            "nmse_vs_upstream_db": nmse,
        }
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(table, indent=1))
    return table
