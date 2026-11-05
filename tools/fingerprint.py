#!/usr/bin/env python3
# Adapted from Halo_Serdes@6e79c4a: tools/fingerprint.py (record/compare/raised kept; the
# recorded set is dspip's reference outputs instead of Halo's link engines)
"""Numerical fingerprint of the references: prove a refactor did not move a bit.

Rule 6: tests assert thresholds (NMSE below a bound, lockstep zero mismatches); a change
meant to leave behaviour alone has to be checked bit for bit. This records, for every IP
configuration dsp_ip ships, the exact integer outputs of the Python reference (as SHA-256
of the int64 array) plus the derived configuration scalars. Every IP under ``ip/`` is
covered: a Python reference where dsp_ip runs one (``RECORDERS``), else the hashes of the
consumer's committed goldens.

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


def record_dp_cal_lms() -> dict:
    from dspip.ip.dp_cal_lms.ref import load_set, reference_values
    from dspip.ipspec import IP_ROOT, load_ipspec

    spec = load_ipspec(IP_ROOT / "dp_cal_lms")
    out = {}
    for vs in spec.vector_sets:
        d = spec.root / vs.dir
        cfg, v0, e, r = load_set(d)
        out[vs.name] = {"in": digest(e) + digest(r), "v_start": v0, "out": digest(reference_values(d)),
                        "config": cfg.to_dict()}
    return out


def record_dtc_dither() -> dict:
    from dspip.ip.dtc_dither.ref import load_set, reference_codes
    from dspip.ipspec import IP_ROOT, load_ipspec

    spec = load_ipspec(IP_ROOT / "dtc_dither")
    out = {}
    for vs in spec.vector_sets:
        d = spec.root / vs.dir
        n_bits, frac_bits, x = load_set(d)
        out[vs.name] = {"in": digest(x), "out": digest(reference_codes(d)),
                        "n_bits": n_bits, "frac_bits": frac_bits}
    return out


def record_polar_dpd_lut() -> dict:
    from dspip.ip.polar_dpd_lut.ref import load_set, reference_outputs
    from dspip.ipspec import IP_ROOT, load_ipspec

    spec = load_ipspec(IP_ROOT / "polar_dpd_lut")
    out = {}
    for vs in spec.vector_sets:
        d = spec.root / vs.dir
        s = load_set(d)
        amp, ph = reference_outputs(d)
        out[vs.name] = {"rom": digest(s["amp_rom"]) + digest(s["ph_rom"]), "in": digest(s["addr"]),
                        "amp": digest(amp), "ph": digest(ph)}
    return out


def record_committed(name: str) -> dict:
    """An IP whose reference is not run here (its tb self-checks against the consumer's
    committed goldens, e.g. the Halo IPs): the sha256 of every committed vector file."""
    from dspip import vectors as V
    from dspip.ipspec import IP_ROOT, load_ipspec

    spec = load_ipspec(IP_ROOT / name)
    return {vs.name: {k: v[:16] for k, v in sorted(V.hash_dir(spec.root / vs.dir).items())
                      if not k.startswith("rtl_")}
            for vs in spec.vector_sets}


RECORDERS = {"dpd_poly": record_dpd_poly, "sat_shift": record_sat_shift,
             "dp_cal_lms": record_dp_cal_lms, "dtc_dither": record_dtc_dither,
             "polar_dpd_lut": record_polar_dpd_lut}


def record_all() -> dict:
    """Every IP under ip/: its Python reference where dsp_ip runs one, else its goldens."""
    from dspip.ipspec import all_ips

    fp = {}
    for spec in all_ips():
        fn = RECORDERS.get(spec.name)
        fp[spec.name] = _guarded(fn if fn else (lambda n=spec.name: record_committed(n)))
        print(f"  {spec.name}", file=sys.stderr, flush=True)
    return fp


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
        fp = record_all()
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
