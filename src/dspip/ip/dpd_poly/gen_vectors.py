"""Lockstep vector sets of dpd_poly (``ip/dpd_poly/vectors/<set>/``).

Every set is: the consumer's exported integer coefficients and input block (rule 3), the
configuration derived from them, and the golden output of the integer reference (rule 1).
``rand_w16`` reuses the GMP W16 configuration with a seeded random input that includes
full-scale extremes, so the saturation and tie-rounding paths are exercised (real data never
reaches them); its generator asserts that at least one column code and one output saturate.

Files (all read by the tb through ``+vecdir``): ``x_re.txt x_im.txt`` (N input codes),
``w_re.txt w_im.txt`` (coefficients), ``y_re.txt y_im.txt`` (golden), ``dims_params.svh``,
``dims.svh``, ``config.json`` (for the probe and for humans).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from dspip.ip.dpd_poly.config import DpdPolyConfig, quantize_input
from dspip.ip.dpd_poly.floatref import load_upstream
from dspip.ip.dpd_poly.ref import DpdPolyRef
from dspip.vectors import read_ints, write_ints

SETS = {
    #  name:         (basis, W, input)
    "ddr_r1_w16": ("ddr_r1", 16, "upstream"),
    "gmp510_w16": ("gmp510", 16, "upstream"),
    "ddr_r1_w12": ("ddr_r1", 12, "upstream"),
    "gmp510_w12": ("gmp510", 12, "upstream"),
    "rand_w16": ("gmp510", 16, "random"),
}
RAND_N = 2048
RAND_SEED = 2024


def random_codes(cfg: DpdPolyConfig, n: int = RAND_N, seed: int = RAND_SEED):
    """Uniform full-range codes plus injected corners: both rails on I and Q (max envelope),
    rail/zero pairs, and a stretch of small values (small envelope, k=4 rounding)."""
    rng = np.random.default_rng(seed)
    hi = (1 << (cfg.w_in - 1)) - 1
    lo = -(1 << (cfg.w_in - 1))
    xi = rng.integers(lo, hi + 1, size=n, dtype=np.int64)
    xq = rng.integers(lo, hi + 1, size=n, dtype=np.int64)
    corners = [(hi, hi), (lo, lo), (hi, lo), (lo, hi), (hi, 0), (0, lo), (0, 0), (1, -1),
               (lo, 0), (0, hi), (hi, 1), (-1, lo)]
    for i, (a, b) in enumerate(corners):
        xi[100 + i], xq[100 + i] = a, b
    # a run of rails: every delayed tap at full scale -> output saturation
    xi[300:340] = hi
    xq[300:340] = lo
    xi[600:700] = rng.integers(-40, 41, size=100)
    xq[600:700] = rng.integers(-40, 41, size=100)
    return xi, xq


def build(set_name: str) -> tuple[DpdPolyConfig, np.ndarray, np.ndarray]:
    basis, w, kind = SETS[set_name]
    up = load_upstream(basis, w)
    cfg = DpdPolyConfig.derive(up.coeffs, up.x, basis=basis)
    if kind == "upstream":
        xi, xq = quantize_input(up.x, cfg.e_in, cfg.w_in)
    else:
        xi, xq = random_codes(cfg)
    return cfg, xi, xq


def generate(set_name: str, out_dir: Path) -> None:
    cfg, xi, xq = build(set_name)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    r = DpdPolyRef(cfg).run(xi.tolist(), xq.tolist())
    if SETS[set_name][2] == "random":
        assert r.n_sat_out > 0, "rand set must saturate the output at least once"
        assert r.n_sat_phi > 0, "rand set must saturate a column code at least once"
    write_ints(out_dir / "x_re.txt", xi)
    write_ints(out_dir / "x_im.txt", xq)
    write_ints(out_dir / "w_re.txt", cfg.coef_re)
    write_ints(out_dir / "w_im.txt", cfg.coef_im)
    write_ints(out_dir / "y_re.txt", r.y_re)
    write_ints(out_dir / "y_im.txt", r.y_im)
    (out_dir / "dims_params.svh").write_text(cfg.to_svh_params())
    (out_dir / "dims.svh").write_text(cfg.to_svh(len(xi)))
    (out_dir / "config.json").write_text(cfg.to_json())
    (out_dir / "STATS.txt").write_text(
        f"{cfg.summary()}\nn={len(xi)} n_sat_phi={r.n_sat_phi} n_sat_out={r.n_sat_out}\n")


def probe(set_dir: Path, sample: int) -> str:
    """The reference's registers at output ``sample`` (what lockstep prints on a mismatch)."""
    set_dir = Path(set_dir)
    cfg = DpdPolyConfig.from_json((set_dir / "config.json").read_text())
    xi = read_ints(set_dir / "x_re.txt")
    xq = read_ints(set_dir / "x_im.txt")
    r = DpdPolyRef(cfg).run(xi, xq, trace_samples=[sample])
    t = r.traces[sample]
    idx = sample + cfg.lead
    newest = (xi[idx], xq[idx]) if idx < len(xi) else (0, 0)
    big = sorted(range(cfg.n_terms), key=lambda c: -(abs(t.code_re[c]) + abs(t.code_im[c])))[:6]
    lines = [
        f"sample {sample}: newest window sample (x[{idx}]) = {newest}, a={t.a}, pw={t.pw[1:]}",
        f"acc_re={t.acc_re} acc_im={t.acc_im} -> y=({t.y_re},{t.y_im}) via >>{cfg.s_out} sat{cfg.w_out}",
        "largest column codes (term: x_delay env -> code_re,code_im * w_re,w_im << al):",
    ]
    for c in big:
        tm = cfg.terms[c]
        lines.append(f"  c{c}: x(n-{tm.x_delay}) env{list(tm.env)} s_c={cfg.s_c[c]} -> "
                     f"({t.code_re[c]},{t.code_im[c]}) * ({cfg.coef_re[c]},{cfg.coef_im[c]}) "
                     f"<< {cfg.al_c[c]}")
    return "\n".join(lines)


def config_of(set_name: str) -> DpdPolyConfig:
    return build(set_name)[0]


def write_all(root: Path) -> None:
    for name in SETS:
        generate(name, root / name)


if __name__ == "__main__":
    import sys

    write_all(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("ip/dpd_poly/vectors"))
    print(json.dumps({k: v for k, v in SETS.items()}, indent=1))
