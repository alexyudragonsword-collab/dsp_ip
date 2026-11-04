#!/usr/bin/env python3
"""Rule 3 drift gate: re-run the consumer's export and compare with the committed copy.

    python tools/check_upstream_export.py --pa-dpd <PA_DPD checkout @5718b83> \
        --dataset <OpenDPD>/datasets/DPA_160MHz [--out <scratch dir>]

Re-runs ``scripts/export_deploy.py`` (W16 and W12) from the pinned PA_DPD checkout against
the pinned OpenDPD dataset and compares with ``ip/dpd_poly/upstream/DPA_160MHz/``:

- exact: the input columns ``i_in/q_in`` and integer input codes ``i_in_code/q_in_code``,
  ``model_class``, ``config``, ``n_coeffs``, ``coeff_scale_exp``, and the ``fixed_point``
  exponents (they follow from the exact input block, so they cannot wobble);
- tolerant: coefficient codes within ±1 LSB, ``i_out/q_out`` within 1e-9 relative
  (the ILA fit goes through LAPACK, which is not bit-repeatable across machines).

Exit 1 on any difference beyond that. Everything the lockstep uses is derived from the
*committed* files; this tool only proves they still are what the consumer produces.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
UP = REPO / "ip" / "dpd_poly" / "upstream" / "DPA_160MHz"
BASES = ("ddr_r1", "gmp510")
BITS = (16, 12)


def compare_coeffs(a: dict, b: dict, max_lsb: int = 1) -> list[str]:
    probs = []
    for k in ("model_class", "config", "n_coeffs", "coeff_scale_exp", "w_bits", "fixed_point"):
        if a.get(k) != b.get(k):
            probs.append(f"{k}: committed {a.get(k)!r} != re-export {b.get(k)!r}")
    for k in ("coeffs_real", "coeffs_imag"):
        x, y = np.asarray(a[k]), np.asarray(b[k])
        if x.shape != y.shape:
            probs.append(f"{k}: length {x.shape} != {y.shape}")
            continue
        d = np.abs(x - y).max() if len(x) else 0
        if d > max_lsb:
            probs.append(f"{k}: max |delta code| = {d} > {max_lsb}")
    return probs


REFVEC_COLS = ("i_in", "q_in", "i_out", "q_out")        # + "i_in_code", "q_in_code" (#3)


def read_refvec(path: Path) -> tuple[np.ndarray, tuple[str, ...]]:
    """The reference CSV and its column names from the header (PA_DPD@08b9725 wrote four
    float columns; from PA_DPD#3 on, two integer input-code columns follow them)."""
    names = tuple(path.read_text().splitlines()[0].strip().split(","))
    return np.loadtxt(path, delimiter=",", skiprows=1, ndmin=2), names


def compare_refvec(a: np.ndarray, b: np.ndarray, rtol: float = 1e-9,
                   names: tuple[str, ...] = REFVEC_COLS) -> list[str]:
    """Inputs and input codes exact, outputs within ``rtol`` of the output scale."""
    probs = []
    if a.shape != b.shape:
        return [f"refvec shape {a.shape} != {b.shape}"]
    col = {n: i for i, n in enumerate(names)}
    exact = [col[n] for n in ("i_in", "q_in", "i_in_code", "q_in_code") if n in col]
    if not np.array_equal(a[:, exact[:2]], b[:, exact[:2]]):
        probs.append("i_in/q_in differ (must be exact)")
    if len(exact) > 2 and not np.array_equal(a[:, exact[2:]], b[:, exact[2:]]):
        probs.append("i_in_code/q_in_code differ (must be exact)")
    out = [col["i_out"], col["q_out"]]
    scale = np.abs(a[:, out]).max()
    d = np.abs(a[:, out] - b[:, out]).max() / scale if scale else 0
    if d > rtol:
        probs.append(f"i_out/q_out relative difference {d:.2e} > {rtol}")
    return probs


def check_dir(committed: Path, fresh: Path) -> list[str]:
    probs = []
    for basis in BASES:
        for w in BITS:
            cj = committed / f"{basis}_w{w}_coeffs.json"
            fj = fresh / f"{basis}_w{w}_coeffs.json"
            if not fj.exists():
                probs.append(f"{fj.name}: not produced")
                continue
            probs += [f"{cj.name}: {p}" for p in compare_coeffs(json.loads(cj.read_text()),
                                                               json.loads(fj.read_text()))]
            cv, cn = read_refvec(committed / f"{basis}_w{w}_refvec.csv")
            fv, fn = read_refvec(fresh / f"{basis}_w{w}_refvec.csv")
            if cn != fn:
                probs.append(f"{basis}_w{w}_refvec.csv: columns {cn} != re-export {fn}")
                continue
            probs += [f"{basis}_w{w}_refvec.csv: {p}" for p in compare_refvec(cv, fv, names=cn)]
    return probs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pa-dpd", required=True, type=Path)
    ap.add_argument("--dataset", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    out = args.out or Path(tempfile.mkdtemp(prefix="dspip_export_"))
    env = {**os.environ, "PYTHONPATH": str(args.pa_dpd / "src")}
    for w in BITS:
        r = subprocess.run([sys.executable, str(args.pa_dpd / "scripts" / "export_deploy.py"),
                            "--dataset-dir", str(args.dataset), "--w-bits", str(w),
                            "--out", str(out)], env=env, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout[-2000:], r.stderr[-2000:])
            print(f"export_deploy.py --w-bits {w} failed")
            return 1
    fresh = out / "DPA_160MHz"
    probs = check_dir(UP, fresh)
    if probs:
        print("upstream export drift:")
        for p in probs:
            print("  " + p)
        return 1
    print(f"OK: re-export in {fresh} matches {UP} (exact inputs/config, codes within 1 LSB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
