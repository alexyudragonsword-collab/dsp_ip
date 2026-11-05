#!/usr/bin/env python3
"""Rule 3 for ip/dp_cal_lms: re-export the vector set with polar_tx at the pinned SHA and
compare it with the committed one.

    python tools/check_dp_cal_export.py --polar-tx _siblings/polar_tx

Runs ``python -m polartx.export.dp_cal_vectors`` from that checkout (it must be
importable: ``pip install -e <checkout>``). The integer streams and ``dp_cal_dims.svh`` must
match byte for byte; in ``dp_cal_meta.json`` everything but the two measured floats must
match exactly, and those within 1e-9 relative (they are a summary, not the contract).
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SET = REPO / "ip" / "dp_cal_lms" / "vectors" / "ble_5pct"
EXACT = ("dp_cal_err.txt", "dp_cal_reg.txt", "dp_cal_value.txt", "dp_cal_dims.svh")
FLOATS = ("tail_mean", "evm_pct")


def compare(fresh: Path, committed: Path = SET) -> list[str]:
    problems = []
    for name in EXACT:
        if (fresh / name).read_bytes() != (committed / name).read_bytes():
            problems.append(f"{name}: differs from the committed file")
    a = json.loads((fresh / "dp_cal_meta.json").read_text())
    b = json.loads((committed / "dp_cal_meta.json").read_text())
    for k in sorted(set(a) | set(b)):
        if k in FLOATS:
            if not math.isclose(a.get(k, math.nan), b.get(k, math.nan), rel_tol=1e-9):
                problems.append(f"dp_cal_meta.json {k}: {a.get(k)} != {b.get(k)}")
        elif a.get(k) != b.get(k):
            problems.append(f"dp_cal_meta.json {k}: {a.get(k)!r} != {b.get(k)!r}")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--polar-tx", type=Path, required=True, help="polar_tx checkout at the pin")
    args = ap.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run([sys.executable, "-m", "polartx.export.dp_cal_vectors", tmp],
                           cwd=args.polar_tx, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout + r.stderr, file=sys.stderr)
            return 2
        problems = compare(Path(tmp))
    for p in problems:
        print("DRIFT " + p)
    print("OK: dp_cal_lms vectors re-exported identically" if not problems
          else f"{len(problems)} difference(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
