#!/usr/bin/env python3
"""Example 00 — run the lockstep for one IP and print the mismatch count (rule 1).

    python examples/00_lockstep.py                 # dpd_poly, every set, P=1 only
    python examples/00_lockstep.py sat_shift
    python examples/00_lockstep.py dpd_poly --param P=4 --sim iverilog

Equivalent to ``tools/lockstep.py``; this is just the shortest path to "0 mismatches".
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ip = argv.pop(0) if argv and not argv[0].startswith("-") else "dpd_poly"
    if "--param" not in argv and ip == "dpd_poly":
        argv += ["--param", "P=1"]
    spec = importlib.util.spec_from_file_location("lockstep", REPO / "tools" / "lockstep.py")
    ls = importlib.util.module_from_spec(spec)
    sys.modules["lockstep"] = ls
    spec.loader.exec_module(ls)
    rc = ls.main([ip] + argv)
    return rc


if __name__ == "__main__":
    sys.exit(main())
