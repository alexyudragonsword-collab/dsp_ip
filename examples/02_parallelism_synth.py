#!/usr/bin/env python3
"""Example 02 — parallelism P × estimated frequency × estimated area (rule 5: open flow only).

Reads the ``results/synth/*.json`` written by ``tools/synth.py`` and prints, per basis and
P, the yosys/ABC critical path, the frequency estimate, throughput = f_est × P, the area
estimate, and the one-line conclusion "P = ? reaches 640 MSPS". Every number is an
*estimate* in the sense of docs/synthesis.md (NanGate45 typical, no wire load).

    python tools/synth.py --ip dpd_poly --set ddr_r1_w16 --P 1   # (and P=2, 4, gmp510_w16)
    python examples/02_parallelism_synth.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results" / "synth"


def load() -> list[dict]:
    reps = [json.loads(p.read_text()) for p in sorted(RESULTS.glob("*.json"))]
    bad = [r for r in reps if r.get("kind") != "estimate"]
    if bad:
        raise SystemExit("synthesis result without kind=estimate: refusing to print it")
    return reps


def print_table(reps: list[dict]) -> None:
    if not reps:
        print("no results/synth/*.json yet: run tools/synth.py first")
        return
    lib = reps[0]["liberty"]["label"]
    print(f"dpd_poly synthesis estimates — yosys + ABC, {lib}, no wire load (docs/synthesis.md)")
    print(f"{'set':<12}{'P':>3}{'mode':>8}{'path ps':>9}{'f_est MHz':>11}{'MSPS':>8}"
          f"{'area mm^2':>11}{'cells':>10}{'P@640':>7}")
    for r in sorted(reps, key=lambda r: (r["set"], r["P"], r["mode"])):
        print(f"{r['set']:<12}{r['P']:>3}{r['mode']:>8}{r['delay_ps']:>9.0f}{r['f_est_mhz']:>11.0f}"
              f"{r['throughput_est_msps']:>8.0f}{r['area_um2'] / 1e6:>11.3f}{r['cells']:>10}"
              f"{r['p_for_640msps']:>7}")
    print()
    for basis in sorted({r["set"] for r in reps}):
        rs = [r for r in reps if r["set"] == basis]
        hier = [r for r in rs if r["mode"] == "hier"] or rs   # real term count when available
        f = min(r["f_est_mhz"] for r in hier)
        p = max(r["p_for_640msps"] for r in hier)
        ok = [r for r in hier if r["throughput_est_msps"] >= 640]
        hit = f", the synthesized P={min(r['P'] for r in ok)} point already exceeds it" if ok else ""
        tag = "hier, real term count" if hier is not rs else "budget extrapolation"
        print(f"{basis}: f_est >= {f:.0f} MHz ({tag}, estimate), so P = {p} reaches 640 MSPS{hit}.")


if __name__ == "__main__":
    print_table(load())
    sys.exit(0)
