#!/usr/bin/env python3
"""Render docs/results.md from results/*.json (rule 5: numbers in documents are generated
from the recorded results, never typed). ``tests/test_docs_numbers.py`` re-renders and
compares, so an edited number in the document fails CI.

    python tools/render_tables.py            # writes docs/results.md
    python tools/render_tables.py --check    # exit 1 if docs/results.md is stale
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ACLR = REPO / "results" / "aclr_table.json"
SYNTH = REPO / "results" / "synth"
OUT = REPO / "docs" / "results.md"


def aclr_section() -> str:
    if not ACLR.exists():
        return "_results/aclr_table.json not present — run examples/01_bitwidth_aclr.py._\n"
    t = json.loads(ACLR.read_text())
    bits = list(t["ddr_r1"]["int_ref"].keys())
    variants = list(next(iter(t["ddr_r1"]["int_ref"].values())).keys())
    lines = [
        f"Dataset {t['_meta']['dataset']}; metric {t['_meta']['metric']}; upstream numbers from "
        f"{t['_meta']['upstream_doc']}.",
        "",
        "| basis | model | float | " + " | ".join(f"W{b}" for b in bits) + " |",
        "|---|---|---|" + "---|" * len(bits),
    ]
    for basis in ("ddr_r1", "gmp510"):
        row = t[basis]
        doc = t["_meta"]["upstream_table"][basis]
        lines.append(f"| {basis} | PA_DPD doc | {doc['float']:.1f} | "
                     + " | ".join(f"{doc[b]:.1f}" for b in bits) + " |")
        up = row["upstream_recomputed"]
        lines.append(f"| | upstream recomputed (vendored code) | {up['float']:.2f} | "
                     + " | ".join(f"{up[b]:.2f}" for b in bits) + " |")
        for v in variants:
            lines.append(f"| | **int ref** ({v}) | | "
                         + " | ".join(f"{row['int_ref'][b][v]:.2f}" for b in bits) + " |")
        lines.append("| | NMSE int ref vs upstream (dB) | | "
                     + " | ".join(f"{row['nmse_vs_upstream_db'][b]:.1f}"
                                  if b in row["nmse_vs_upstream_db"] else "–" for b in bits) + " |")
    worst = max(abs(t[b]["upstream_recomputed"][str(k)] - v)
                for b in ("ddr_r1", "gmp510")
                for k, v in t["_meta"]["upstream_table"][b].items())
    w16 = max(abs(t[b]["int_ref"]["16"][variants[0]] - t["_meta"]["upstream_table"][b]["16"])
              for b in ("ddr_r1", "gmp510"))
    lines += ["",
              f"Max |upstream recomputed − PA_DPD doc| = {worst:.2f} dB; "
              f"max |int ref W16 ({variants[0]}) − PA_DPD doc W16| = {w16:.2f} dB.",
              ""]
    return "\n".join(lines)


def synth_section() -> str:
    reps = [json.loads(p.read_text()) for p in sorted(SYNTH.glob("*.json"))]
    reps = [r for r in reps if r.get("ip") == "dpd_poly"]
    if not reps:
        return "_results/synth/*.json not present — run tools/synth.py._\n"
    lib = reps[0]["liberty"]["label"]
    lines = [
        f"**Estimates** — yosys ({reps[0]['yosys']}) + ABC, {lib}, no wire load; "
        f"f_est = 1/(ABC critical path + DFF t_cq + t_setup); method per row in the JSON "
        f"(see `docs/synthesis.md`).",
        "",
        "| set | P | mode | critical path (ps) | f_est (MHz) | throughput (MSPS) | area (mm²) | cells | P for 640 MSPS |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(reps, key=lambda r: (r["set"], r["P"], r["mode"])):
        lines.append(f"| {r['set']} | {r['P']} | {r['mode']} | {r['delay_ps']:.0f} | "
                     f"{r['f_est_mhz']:.0f} | {r['throughput_est_msps']:.0f} | "
                     f"{r['area_um2'] / 1e6:.3f} | {r['cells']} | {r['p_for_640msps']} |")
    lines.append("")
    # P > 1 by construction: dpd_poly is P copies of (front end + term bank + tree) sharing one
    # history window and the coefficient registers, so area scales ~linearly in P and the
    # pipeline stages are identical; only the window fan-out grows (not modelled: no wire load).
    constructed = []
    for basis in sorted({r["set"] for r in reps}):
        h1 = [r for r in reps if r["set"] == basis and r["mode"] == "hier" and r["P"] == 1]
        have = {r["P"] for r in reps if r["set"] == basis and r["mode"] == "hier"}
        for P in (2, 4):
            if h1 and P not in have:
                r = h1[0]
                constructed.append(
                    f"| {basis} | {P} | by construction | {r['delay_ps']:.0f} | {r['f_est_mhz']:.0f} | "
                    f"{r['f_est_mhz'] * P:.0f} | ≈{r['area_um2'] * P / 1e6:.3f} | ≈{r['cells'] * P} | "
                    f"{max(1, math.ceil(640 / r['f_est_mhz']))} |")
    if constructed:
        lines.append("P = 2 / 4 rows **by construction** (not synthesized — the user chose to stop "
                     "after the P = 1 points): same stages, P copies of the term bank and tree, "
                     "throughput = f_est × P, area ≈ P × area(P=1); window fan-out not modelled.")
        lines.append("")
        lines.append("| set | P | mode | critical path (ps) | f_est (MHz) | throughput (MSPS) | area (mm²) | cells | P for 640 MSPS |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        lines += constructed
        lines.append("")
    for basis in sorted({r["set"] for r in reps}):
        rs = [r for r in reps if r["set"] == basis]
        hier = [r for r in rs if r["mode"] == "hier"] or rs   # real term count when available
        f = min(r["f_est_mhz"] for r in hier)
        p = max(r["p_for_640msps"] for r in hier)
        tag = "hier, real term count" if hier is not rs else "budget extrapolation"
        lines.append(f"- **{basis}**: f_est ≥ {f:.0f} MHz ({tag}, estimate) ⇒ **P = {p}** reaches "
                     f"640 MSPS (throughput = f_clk × P).")
        budget = [r for r in rs if r["mode"] == "budget"]
        if hier is not rs and budget:
            fb = min(r["f_est_mhz"] for r in budget)
            pb = max(r["p_for_640msps"] for r in budget)
            if pb != p:
                lines.append(f"  - conservative reading: the flattened budget points map to f_est ≥ "
                             f"{fb:.0f} MHz ⇒ P = {pb}; the two mappings disagree, see "
                             f"`docs/synthesis.md`.")
        for h in [r for r in rs if r["mode"] == "hier"]:
            b = [r for r in rs if r["mode"] == "budget" and r["P"] == h["P"]]
            if b:
                err = (b[0]["area_um2"] - h["area_um2"]) / h["area_um2"] * 100
                lines.append(f"  - P={h['P']}: budget extrapolation vs hier area {err:+.0f} %, "
                             f"critical path {b[0]['delay_ps']:.0f} vs {h['delay_ps']:.0f} ps.")
    lines.append("")
    return "\n".join(lines)


def render() -> str:
    return ("# Results (generated — do not edit; `python tools/render_tables.py`)\n\n"
            "## Fixed-point vs float: ACLR (rule 2)\n\n" + aclr_section()
            + "\n## Parallelism × frequency × area (rule 5)\n\n" + synth_section())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    text = render()
    if args.check:
        if not OUT.exists() or OUT.read_text() != text:
            print(f"{OUT} is stale: run python tools/render_tables.py")
            return 1
        print("docs/results.md up to date")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
