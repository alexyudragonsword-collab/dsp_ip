#!/usr/bin/env python3
"""Rule 3 for the IPs fed by polar_tx: re-export every committed vector set with polar_tx at
the pinned SHA and compare it with the committed one.

    python tools/check_polartx_export.py --polar-tx _siblings/polar_tx
    python tools/check_polartx_export.py --polar-tx ../polar_tx --write   # (re)create the sets

Each set is produced by one polar_tx command (``SETS`` below, the same command its SOURCE.md
names), run from that checkout (it must be importable: ``pip install -e <checkout>``).
Integer streams, ROM images and ``*_dims.svh`` must match byte for byte; in the ``*_meta.json``
integers, strings and structure must match exactly and every float (scalar or inside a list,
e.g. the float LUT polar_dpd_lut documents next to its ROMs) within 1e-9 relative / 1e-12
absolute: those are informative and their last ulp follows the CPU and numpy build, the
integers the RTL is checked against do not. ``--write`` copies the fresh export over the committed files
(SOURCE.md is never touched) for a deliberate re-pin; re-lock afterwards with
``tools/lockstep.py <ip> --update-lock``.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
IP = REPO / "ip"

# (ip, set, polar_tx module, extra args)
SETS = [
    ("dp_cal_lms", "ble_5pct", "polartx.export.dp_cal_vectors", []),
    ("dp_cal_lms", "ble_m5pct", "polartx.export.dp_cal_vectors", ["--variant", "ble_m5pct"]),
    ("dp_cal_lms", "sat_top", "polartx.export.dp_cal_vectors", ["--variant", "sat_top"]),
    ("dp_cal_lms", "narrow", "polartx.export.dp_cal_vectors", ["--variant", "narrow"]),
    ("dtc_dither", "random", "polartx.export.rtl_vectors", ["dtc_random"]),
    ("dtc_dither", "ramp", "polartx.export.rtl_vectors", ["dtc_ramp"]),
    ("polar_dpd_lut", "wifi20", "polartx.export.rtl_vectors", ["dpd_lut"]),
    ("cfr_clip", "mixed", "polartx.export.rtl_vectors", ["cfr_clip"]),
    ("dtc_phase_acc", "random", "polartx.export.rtl_vectors", ["phase_acc"]),
    ("dpa_thermo_decode", "all_codes", "polartx.export.rtl_vectors", ["thermo"]),
    ("polar_datapath", "wifi20", "polartx.export.rtl_vectors", ["datapath"]),
]
REL_TOL, ABS_TOL = 1e-9, 1e-12


def same(a, b) -> bool:
    """Equal, except floats (anywhere in the structure) only need to agree within tolerance."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, float) or isinstance(b, float):
        return (isinstance(a, (int, float)) and isinstance(b, (int, float))
                and math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL))
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    return type(a) is type(b) and a == b


def command(module: str, args: list[str], outdir: str) -> list[str]:
    # rtl_vectors takes the set name before OUTDIR, dp_cal_vectors takes options after it
    if module.endswith("rtl_vectors"):
        return [sys.executable, "-m", module, *args, outdir]
    return [sys.executable, "-m", module, outdir, *args]


def compare(fresh: Path, committed: Path) -> list[str]:
    problems = []
    names = sorted({p.name for p in fresh.iterdir()} | {p.name for p in committed.iterdir()}
                   - {"SOURCE.md"})
    for name in names:
        a, b = fresh / name, committed / name
        if not a.exists() or not b.exists():
            problems.append(f"{name}: only in {'committed' if b.exists() else 'fresh'} set")
        elif name.endswith("_meta.json"):
            ja, jb = json.loads(a.read_text()), json.loads(b.read_text())
            for k in sorted(set(ja) | set(jb)):
                if k not in ja or k not in jb:
                    problems.append(f"{name} {k}: only in {'fresh' if k in ja else 'committed'}")
                elif not same(ja[k], jb[k]):
                    problems.append(f"{name} {k}: differs")
        elif a.read_bytes() != b.read_bytes():
            problems.append(f"{name}: differs from the committed file")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--polar-tx", type=Path, required=True, help="polar_tx checkout at the pin")
    ap.add_argument("--write", action="store_true", help="overwrite the committed sets")
    ap.add_argument("--only", help="ip/set, e.g. dtc_dither/ramp")
    args = ap.parse_args(argv)
    n_bad = 0
    for ip, name, module, extra in SETS:
        if args.only and args.only != f"{ip}/{name}":
            continue
        committed = IP / ip / "vectors" / name
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(command(module, extra, tmp), cwd=args.polar_tx,
                               capture_output=True, text=True)
            if r.returncode != 0:
                print(f"ERROR {ip}/{name}: export failed\n{r.stdout}{r.stderr}", file=sys.stderr)
                return 2
            if args.write:
                committed.mkdir(parents=True, exist_ok=True)
                for p in Path(tmp).iterdir():
                    shutil.copy2(p, committed / p.name)
                print(f"wrote {ip}/{name}")
                continue
            problems = compare(Path(tmp), committed)
        for p in problems:
            print(f"DRIFT {ip}/{name}: {p}")
        n_bad += bool(problems)
        if not problems:
            print(f"OK    {ip}/{name}")
    if not args.write:
        print("OK: every polar_tx set re-exported identically" if not n_bad
              else f"{n_bad} set(s) differ")
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
