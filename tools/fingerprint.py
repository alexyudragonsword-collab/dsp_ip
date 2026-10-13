#!/usr/bin/env python3
# Adapted from Halo_Serdes@6e79c4a: tools/fingerprint.py (record/compare/raised kept; the
# recorded set is dspip's reference outputs instead of Halo's link engines)
"""Numerical fingerprint of the references: prove a refactor did not move a bit.

Rule 6: tests assert thresholds (NMSE below a bound, lockstep zero mismatches); a change
meant to leave behaviour alone has to be checked bit for bit. This records, for every IP
configuration dsp_ip ships, the exact integer outputs of the Python reference (as SHA-256
of the int64 array) plus the derived configuration scalars.

    python tools/fingerprint.py record before.json     # on the base commit
    python tools/fingerprint.py record after.json      # on the change
    python tools/fingerprint.py compare before.json after.json

``compare`` prints every differing value and exits 1 if there is one. Entries that raised
instead of recording are listed, because two sides failing the same way compare equal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))


def digest(a) -> str:
    return hashlib.sha256(np.ascontiguousarray(np.asarray(a, dtype=np.int64))).hexdigest()[:16]


def _guarded(fn):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def record_dpd_poly() -> dict:
    from dspip.ip.dpd_poly.config import DpdPolyConfig, quantize_input
    from dspip.ip.dpd_poly.floatref import load_upstream
    from dspip.ip.dpd_poly.ref import DpdPolyRef

    out = {}
    for basis in ("ddr_r1", "gmp510"):
        for w in (16, 12):
            for w_pw, f in ((None, 0), (20, 2)):
                key = f"{basis}/w{w}/pw{w_pw or w}/f{f}"

                def one(basis=basis, w=w, w_pw=w_pw, f=f):
                    up = load_upstream(basis, w)
                    cfg = DpdPolyConfig.derive(up.coeffs, up.x, basis=basis, w_pw=w_pw,
                                               env_frac=f)
                    xi, xq = quantize_input(up.x, cfg.e_in, cfg.w_in)
                    ref = DpdPolyRef(cfg)
                    if cfg.check_int64():
                        yr, yi = ref.run_vec(xi, xq)
                    else:
                        r = ref.run(xi.tolist(), xq.tolist())
                        yr, yi = np.array(r.y_re), np.array(r.y_im)
                    return {"y_re": digest(yr), "y_im": digest(yi), "n": int(len(yr)),
                            "e_in": cfg.e_in, "s_out": cfg.s_out, "w_acc": cfg.w_acc,
                            "e_c": digest(cfg.e_c), "s_c": digest(cfg.s_c),
                            "q_k": list(cfg.q_k), "x": digest(xi) + digest(xq)}

                out[key] = _guarded(one)
                print(f"  {key}", file=sys.stderr, flush=True)
    return out


def record_sat_shift() -> dict:
    from dspip.ip.sat_shift.ref import vectors

    out = {}
    for name, (v, s, w, y) in vectors().items():
        out[name] = {"in": digest(v), "out": digest(y), "shift": s, "w": w}
    return out


def compare(a: dict, b: dict) -> tuple[int, list[str]]:
    """(leaf values compared, the differing ones as 'path: old -> new')."""
    diffs, n = [], 0

    def walk(path, x, y):
        nonlocal n
        if isinstance(x, dict) or isinstance(y, dict):
            x = x if isinstance(x, dict) else {}
            y = y if isinstance(y, dict) else {}
            for k in sorted(set(x) | set(y)):
                walk(path + [k], x.get(k), y.get(k))
        else:
            n += 1
            if x != y:
                diffs.append(" / ".join(path) + f": {x!r} -> {y!r}")

    walk([], a, b)
    return n, diffs


def raised(fp: dict) -> list[str]:
    out = []

    def walk(path, x):
        if isinstance(x, dict):
            for k in sorted(x):
                if k == "error":
                    out.append(" / ".join(path) + f": {x[k]}")
                else:
                    walk(path + [k], x[k])

    walk([], fp)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("record", help="run the references and write the fingerprint")
    rec.add_argument("out", type=Path)
    cmp_ = sub.add_parser("compare", help="diff two fingerprints; exit 1 on any difference")
    cmp_.add_argument("a", type=Path)
    cmp_.add_argument("b", type=Path)
    args = ap.parse_args(argv)

    if args.cmd == "record":
        t0 = time.time()
        fp = {"dpd_poly": _guarded(record_dpd_poly), "sat_shift": _guarded(record_sat_shift)}
        args.out.write_text(json.dumps(fp, indent=1, sort_keys=True))
        n, _ = compare(fp, {})
        print(f"wrote {args.out}: {n} values [{time.time() - t0:.0f}s]")
        _report_raised(fp)
        return 0
    a, b = json.loads(args.a.read_text()), json.loads(args.b.read_text())
    n, diffs = compare(a, b)
    print(f"compared {n} values")
    _report_raised(b)
    if diffs:
        print(f"{len(diffs)} differ:")
        for d in diffs:
            print("  " + d)
        return 1
    print("bit-identical")
    return 0


def _report_raised(fp: dict) -> None:
    errs = raised(fp)
    if errs:
        print(f"{len(errs)} entries raised instead of recording values:")
        for e in errs:
            print("  " + e)


if __name__ == "__main__":
    sys.exit(main())
