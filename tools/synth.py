#!/usr/bin/env python3
"""Synthesis estimates with an open flow (rule 5): yosys + ABC + a public standard-cell
library. Every number this tool writes is labelled ``"kind": "estimate"`` and carries the
method, the library (name + sha256) and the yosys version; nothing here is a vendor number.

    python tools/synth.py --ip dpd_poly --set gmp510_w16 --P 1          # budget mode (CI)
    python tools/synth.py --ip dpd_poly --set ddr_r1_w16 --P 2 --mode full --dch
    python tools/synth.py --ip sat_shift --set signed_w40_s12_o16

Modes (``--mode``):
  budget  synthesize the top with N_TERMS reduced to T and 2T terms (``--terms``), flatten,
          fast ABC mapping. The critical path (f_est) is a property of the pipeline stages
          (multiplier, 2 adder levels, sqrt step) and does not depend on the term count;
          the area is extrapolated linearly to the full term count from the two points.
  full    synthesize the top flattened with the real N_TERMS (ABC on millions of cells:
          slow and >9 GB for the big bases).
  hier    real N_TERMS, hierarchy kept for the IP's own modules (helpers such as sat_shift
          flattened into them): ABC maps each derived module on its own, so memory stays
          small and the real term count is synthesized; delay = max over modules.

Frequency: ABC ``stime`` reports the longest combinational path of the mapped netlist with
the liberty's cell delays and no wire load; f_est = 1 / (delay + t_cq + t_setup) with the
flop numbers read from the liberty's DFF cell. Area: ``stat -liberty`` cell area in um^2.
See docs/synthesis.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from dspip.ipspec import IP_ROOT, load_ipspec  # noqa: E402

RESULTS = REPO / "results" / "synth"
LIBS = {
    "nangate45": {
        "path": REPO / "third_party/orfs/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib",
        "dff": "DFF_X1",
        "label": "NanGate45 (FreePDK45) typical, OpenROAD-flow-scripts@e5cc6e7",
    },
    "sky130": {
        "path": REPO / "third_party/sky130_fd_sc_hd/timing/sky130_fd_sc_hd__tt_025C_1v80.lib",
        "dff": "sky130_fd_sc_hd__dfxtp_1",
        "label": "sky130_fd_sc_hd tt_025C_1v80, skywater-pdk-libs-sky130_fd_sc_hd@28c101f",
    },
}
ABC_FAST = "strash\nmap\ntopo\nstime -p\n"
ABC_DCH = "strash\ndch -f\nmap\ntopo\nstime -p\n"
# yosys's own default liberty flow (&nf mapper) with a delay target, plus stime for the report
ABC_NF = ("strash\n&get -n\n&fraig -x\n&put\nscorr\ndc2\ndretime\nstrash\n&get -n\n&dch -f\n"
          "&nf -D {D}\n&put\ntopo\nstime -p\n")
DEFAULT_TARGET_PS = 1000.0


def abc_script(dch: bool, target_ps: float | None, legacy: bool = False) -> str:
    """ABC script. Default: the ``&nf`` mapper with a delay target (what yosys's own
    ``abc -liberty -D`` runs), which maps a 167 k-gate adder tree to 1441 ps where the old
    area-oriented ``map`` left a 1969 ps path. ``legacy`` selects the old ``map`` flow
    (``dch`` optional, ``-D`` optional) for comparison."""
    if not legacy:
        return ABC_NF.replace("{D}", str(int(target_ps or DEFAULT_TARGET_PS)))
    s = ABC_DCH if dch else ABC_FAST
    if target_ps:
        s = s.replace("\nmap\n", f"\nmap -D {int(target_ps)}\n")
    return s


# --- liberty helpers -----------------------------------------------------------------------


def _cell_block(lib_text: str, cell: str) -> str:
    m = re.search(r"cell\s*\(\s*\"?%s\"?\s*\)\s*\{" % re.escape(cell), lib_text)
    if not m:
        raise ValueError(f"cell {cell} not found in liberty")
    i, depth = m.end(), 1
    while depth and i < len(lib_text):
        depth += {"{": 1, "}": -1}.get(lib_text[i], 0)
        i += 1
    return lib_text[m.start():i]


def _pin_block(cell_text: str, pin: str) -> str:
    m = re.search(r"pin\s*\(\s*\"?%s\"?\s*\)\s*\{" % re.escape(pin), cell_text)
    if not m:
        raise ValueError(f"pin {pin} not found")
    i, depth = m.end(), 1
    while depth and i < len(cell_text):
        depth += {"{": 1, "}": -1}.get(cell_text[i], 0)
        i += 1
    return cell_text[m.start():i]


def _table_median(block: str, name: str) -> float:
    """Median of the first ``name(...) { values(...) }`` table in ``block`` (ns)."""
    m = re.search(r"%s\s*\([^)]*\)\s*\{(.*?)\}" % name, block, re.S)
    if not m:
        raise ValueError(f"table {name} not found")
    v = re.search(r"values\s*\((.*?)\)\s*;", m.group(1), re.S)
    nums = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", v.group(1))]
    nums.sort()
    return nums[len(nums) // 2]


def ff_overhead_ps(lib_path: Path, dff_cell: str) -> dict:
    """t_cq + t_setup (ps) of the liberty's plain D flip-flop, median table entries."""
    text = lib_path.read_text(errors="replace")
    unit = re.search(r"time_unit\s*:\s*\"?(\d+)\s*(ps|ns)\"?", text)
    scale = 1000.0 if (unit is None or unit.group(2) == "ns") else float(unit.group(1))
    cell = _cell_block(text, dff_cell)
    q = _pin_block(cell, "Q")
    tcq = max(_table_median(q, "cell_rise"), _table_median(q, "cell_fall")) * scale
    d = _pin_block(cell, "D")
    setup_blk = re.search(r"timing\s*\(\)\s*\{[^{}]*setup_rising.*?\}\s*\}", d, re.S)
    src = setup_blk.group(0) if setup_blk else d
    tsu = max(_table_median(src, "rise_constraint"), _table_median(src, "fall_constraint")) * scale
    return {"cell": dff_cell, "t_cq_ps": round(tcq, 1), "t_setup_ps": round(tsu, 1),
            "total_ps": round(tcq + tsu, 1)}


# --- log parsers --------------------------------------------------------------------------


def parse_abc_delay(log: str) -> list[float]:
    """Every ``ABC: ... Delay = X ps`` line (one per ABC invocation / module)."""
    return [float(x) for x in re.findall(r"ABC:.*?Delay\s*=\s*([0-9.]+)\s*ps", log)]


def parse_stat(log: str) -> dict:
    """The last ``stat -liberty`` block: chip area, cell count, flop count."""
    area = re.findall(r"Chip area for (?:top )?module '\\?([^']+)':\s*([0-9.]+)", log)
    cells = re.findall(r"Number of cells:\s+(\d+)", log)
    dff = re.findall(r"^\s+(\S*DFF\S*|\S*dfxtp\S*)\s+(\d+)\s*$", log, re.M)
    out = {"area_um2": float(area[-1][1]) if area else None,
           "cells": int(cells[-1]) if cells else None,
           "flops": sum(int(n) for _, n in dff[-40:]) if dff else None}
    return out


# --- flow ----------------------------------------------------------------------------------


def yosys_version() -> str:
    r = subprocess.run(["yosys", "-V"], capture_output=True, text=True)
    return r.stdout.strip()


def keep_modules(spec) -> list[str]:
    """Modules kept as hierarchy in --mode hier: the IP's own RTL modules except the top.
    Helpers pulled in from other IPs (e.g. ../sat_shift) are flattened into their parents so
    a pipeline stage never straddles a module boundary that ABC would time separately."""
    own = []
    for r in spec.rtl:
        if r.startswith(".."):
            continue
        stem = Path(r).stem
        if stem != spec.top:
            own.append(stem)
    return own


def run_yosys(spec, set_dir: Path, lib: Path, params: dict, work: Path, abc_script: str,
              flatten: bool = True) -> tuple[str, float]:
    work.mkdir(parents=True, exist_ok=True)
    (work / "abc.script").write_text(abc_script)
    srcs = " ".join(str(p) for p in spec.rtl_paths())
    chp = " ".join(f"-chparam {k} {v}" for k, v in params.items())
    lines = [f"read_verilog -sv -I {set_dir} {srcs}", f"hierarchy -top {spec.top} {chp}"]
    if flatten:
        lines.append(f"synth -top {spec.top} -flatten")
    else:
        keep = " ".join(f"*{m}*" for m in keep_modules(spec))
        lines += ["proc",
                  f"setattr -mod -set keep_hierarchy 1 {keep}" if keep else "",
                  "flatten",
                  f"synth -top {spec.top}"]
    lines += [
        f"dfflibmap -liberty {lib}",
        f"abc -liberty {lib} -script {work / 'abc.script'}",
        "opt_clean",
        f"stat -liberty {lib}",
    ]
    ys = "\n".join(ln for ln in lines if ln) + "\n"
    (work / "synth.ys").write_text(ys)
    t0 = time.time()
    r = subprocess.run(["yosys", "-q", "-l", str(work / "yosys.log"), str(work / "synth.ys")],
                       capture_output=True, text=True)
    dt = time.time() - t0
    log = (work / "yosys.log").read_text() if (work / "yosys.log").exists() else ""
    if r.returncode != 0:
        raise RuntimeError(f"yosys failed ({work / 'yosys.log'}):\n{(r.stdout + r.stderr)[-2000:]}\n"
                           f"{log[-2000:]}")
    return log, dt


def synth_point(spec, set_name: str, lib_name: str, P: int, mode: str, terms: int | None,
                dch: bool, target_ps: float | None = None, legacy: bool = False) -> dict:
    lib = LIBS[lib_name]
    lib_path = lib["path"]
    if not lib_path.exists():
        raise FileNotFoundError(f"{lib_path} missing: run tools/get_liberty.sh {lib_name}")
    set_dir = spec.set_dir(set_name)
    if not (set_dir / "dims_params.svh").exists() and not (set_dir / "dims.svh").exists():
        gen = spec.load_callable(spec.generator)
        gen(set_name, set_dir)
    n_full = None
    dp = set_dir / "dims_params.svh"
    if dp.exists():
        m = re.search(r"N_TERMS\s*=\s*(\d+)", dp.read_text())
        n_full = int(m.group(1)) if m else None
    script = abc_script(dch, target_ps, legacy)
    tag = (f"{set_name}__P{P}__{mode}__{lib_name}" + ("_legacy" if legacy else "")
           + ("_dch" if dch else "") + (f"_D{int(target_ps)}" if target_ps else ""))
    work = RESULTS / "logs" / spec.name / tag
    base_params = {"P": P} if "P" in spec.params else {}
    ff = ff_overhead_ps(lib_path, lib["dff"])
    rep = {"kind": "estimate", "ip": spec.name, "set": set_name, "P": P, "mode": mode,
           "liberty": {"name": lib_name, "label": lib["label"],
                       "sha256": hashlib.sha256(lib_path.read_bytes()).hexdigest()},
           "yosys": yosys_version(), "abc_script": script.strip().replace("\n", "; "),
           "target_ps": target_ps,
           "ff": ff, "n_terms_full": n_full, "points": []}
    points = []
    if mode in ("full", "hier") or n_full is None:
        points.append((mode if n_full is not None else "full", {}))
    else:
        t = terms or 16
        points.append((f"terms{t}", {"N_TERMS": t}))
        points.append((f"terms{2 * t}", {"N_TERMS": 2 * t}))
    for label, extra in points:
        log, dt = run_yosys(spec, set_dir, lib_path, {**base_params, **extra}, work / label,
                            script, flatten=(mode != "hier"))
        delays = parse_abc_delay(log)
        st = parse_stat(log)
        pt = {"label": label, "params": {**base_params, **extra}, "delay_ps": max(delays) if delays else None,
              "runtime_s": round(dt, 1), **st}
        rep["points"].append(pt)
    # frequency from the worst critical path over the points
    delay = max(p["delay_ps"] for p in rep["points"] if p["delay_ps"] is not None)
    period = delay + ff["total_ps"]
    f_mhz = 1e6 / period
    rep["delay_ps"] = delay
    rep["period_ps"] = round(period, 1)
    rep["f_est_mhz"] = round(f_mhz, 1)
    rep["throughput_est_msps"] = round(f_mhz * P, 1)
    rep["p_for_640msps"] = math.ceil(640.0 / f_mhz)
    if mode == "hier":
        rep["area_um2"] = rep["points"][0]["area_um2"]
        rep["cells"] = rep["points"][0]["cells"]
        rep["method"] = ("whole design, real term count, hierarchy kept for "
                         f"{', '.join(keep_modules(spec))} (helpers flattened into them); ABC "
                         "maps and times each module separately, delay = max over modules "
                         "(no wire load) + liberty DFF t_cq + t_setup; area = stat -liberty "
                         "hierarchy total")
    elif mode == "full" or n_full is None:
        rep["area_um2"] = rep["points"][0]["area_um2"]
        rep["cells"] = rep["points"][0]["cells"]
        rep["method"] = ("whole design synthesized with the real term count; "
                         "delay = ABC stime (no wire load) + liberty DFF t_cq + t_setup")
    else:
        a1, a2 = rep["points"][0], rep["points"][1]
        t1, t2 = a1["params"]["N_TERMS"], a2["params"]["N_TERMS"]
        slope = (a2["area_um2"] - a1["area_um2"]) / (t2 - t1)
        rep["area_per_term_um2"] = round(slope, 1)
        rep["area_um2"] = round(a1["area_um2"] + slope * (n_full - t1), 1)
        rep["cells"] = round(a1["cells"] + (a2["cells"] - a1["cells"]) / (t2 - t1) * (n_full - t1))
        rep["method"] = (f"top synthesized with N_TERMS={t1} and {t2}, flattened, fast ABC "
                         f"map; area extrapolated linearly to {n_full} terms; delay = max ABC "
                         "stime over both points (no wire load) + liberty DFF t_cq + t_setup")
    rep["runtime_s"] = round(sum(p["runtime_s"] for p in rep["points"]), 1)
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ip", required=True)
    ap.add_argument("--set", required=True, dest="set_name")
    ap.add_argument("--P", type=int, default=1)
    ap.add_argument("--mode", choices=["budget", "full", "hier"], default="budget")
    ap.add_argument("--terms", type=int, help="budget mode: smaller term count T (and 2T)")
    ap.add_argument("--lib", choices=list(LIBS), default="nangate45")
    ap.add_argument("--legacy-map", action="store_true", dest="legacy",
                    help="old ABC 'map' flow instead of the default &nf flow (comparison)")
    ap.add_argument("--dch", action="store_true", help="legacy flow: dch before map")
    ap.add_argument("--target-ps", type=float, default=None,
                    help=f"ABC delay target in ps (default {DEFAULT_TARGET_PS:.0f} for the &nf flow)")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    if shutil.which("yosys") is None:
        print("yosys not found; see ROADMAP 被外部阻塞", file=sys.stderr)
        return 2
    spec = load_ipspec(IP_ROOT / args.ip)
    rep = synth_point(spec, args.set_name, args.lib, args.P, args.mode, args.terms, args.dch,
                      args.target_ps, args.legacy)
    RESULTS.mkdir(parents=True, exist_ok=True)
    suffix = (("_legacy" if args.legacy else "") + ("_dch" if args.dch else "")
              + (f"_D{int(args.target_ps)}" if args.target_ps else ""))
    out = args.out or RESULTS / f"{spec.name}__{args.set_name}__P{args.P}__{args.mode}{suffix}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1))
    print(f"[estimate] {spec.name}/{args.set_name} P={args.P} {args.mode} ({args.lib}): "
          f"delay {rep['delay_ps']:.0f} ps + ff {rep['ff']['total_ps']:.0f} ps -> "
          f"f_est {rep['f_est_mhz']:.0f} MHz, {rep['throughput_est_msps']:.0f} MSPS, "
          f"area {rep['area_um2']:.0f} um^2, {rep['cells']} cells, "
          f"P for 640 MSPS = {rep['p_for_640msps']}  [{rep['runtime_s']}s]")
    print(f"  -> {out}")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    sys.exit(main())
