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
  unit    one leaf module alone (``--module dpd_pow``, ``--param K1=1``): a minutes-long
          probe of a single pipeline stage, written to results/synth/units/, never a
          datapath number (the hier report's ``modules`` field says which module to probe).

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

# The pinned yosys (tools/get_yosys.sh). Committed estimates must come from exactly this
# build (tests/test_synth_tool.py); an unpinned yosys still runs, for exploration.
YOSYS_PIN = "oss-cad-suite 2026-10-25"
YOSYS_PIN_VERSION = "Yosys 0.70+219 (git sha1 5053d0e26, Release, Clang /usr/bin/clang++ 21.1.8)"
_PINNED_BIN = REPO / "third_party" / "oss-cad-suite" / "bin" / "yosys"


def yosys_bin() -> str | None:
    """$DSPIP_YOSYS, else the pinned build under third_party/, else yosys on PATH."""
    env = os.environ.get("DSPIP_YOSYS")
    if env:
        return env
    if _PINNED_BIN.exists():
        return str(_PINNED_BIN)
    return shutil.which("yosys")
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


_EXTRACT = re.compile(r"Extracting gate netlist of module `([^']*)'")
_DELAY = re.compile(r"ABC:.*?Delay\s*=\s*([0-9.]+)\s*ps")


_ABC_PASS = re.compile(r"^[\d.]+ Executing ABC pass", re.M)


def parse_abc_modules(log: str) -> dict:
    """Per-module worst ABC delay: ``{base module name: {"delay_ps", "instances"}}``.
    Yosys names every parameterization ``$paramod$<hash>\\dpd_term``; the base name is what
    a reader wants, the worst delay over all its parameterizations is what sets f_est.

    Within one ``abc`` pass the n-th reported delay belongs to the n-th extracted module.
    yosys 0.33 interleaves "Extracting gate netlist of module X" with X's ABC output;
    yosys 0.70 logs all extractions first and the ABC outputs after them, in the same
    order. Pairing by position inside each pass that reports delays (``synth``'s own
    ``abc -fast`` does not) works for both; a pass whose counts disagree is reported
    under ``"?"`` rather than guessed."""
    out: dict = {}
    cuts = [m.start() for m in _ABC_PASS.finditer(log)] + [len(log)]
    for a, b in zip(cuts, cuts[1:]):
        blk = log[a:b]
        names = [m.group(1).rsplit("\\", 1)[-1].lstrip("\\$") for m in _EXTRACT.finditer(blk)]
        delays = [float(x) for x in _DELAY.findall(blk)]
        if not delays:
            continue
        if len(names) != len(delays):
            names = ["?"] * len(delays)
        for name, d in zip(names, delays):
            e = out.setdefault(name, {"delay_ps": 0.0, "instances": 0})
            e["delay_ps"] = max(e["delay_ps"], d)
            e["instances"] += 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["delay_ps"]))


_CELLS_OLD = re.compile(r"^\s*Number of cells:\s+(\d+)\s*$", re.M)
_CELLS_NEW = re.compile(r"^\s*(\d+)\s+\S+\s+cells\s*$", re.M)      # yosys >= ~0.40 table
_DFF_OLD = re.compile(r"^\s+(\S*(?:DFF|dfxtp)\S*)\s+(\d+)\s*$", re.M)
_DFF_NEW = re.compile(r"^\s*(\d+)\s+\S+\s+(\S*(?:DFF|dfxtp)\S*)\s*$", re.M)


def parse_stat_json(path: Path) -> dict | None:
    """Design totals from ``stat -json -liberty`` (yosys 0.33 and 0.70 both write it).
    Cells = library cells only (0.70's ``num_cells`` also counts submodule instances);
    flops = every DFF-type cell. Exact, unlike the text table at >= 1e7 cells."""
    if not path.exists():
        return None
    d = json.loads(path.read_text())
    des = d.get("design") or {}
    mods = set(d.get("modules") or {})
    by_type = {k: v for k, v in (des.get("num_cells_by_type") or {}).items()
               if not k.startswith(("$", "\\")) and k not in mods}
    if not by_type:
        return None
    return {"area_um2": des.get("area"),
            "cells": int(sum(by_type.values())),
            "flops": int(sum(v for k, v in by_type.items() if "DFF" in k or "dfxtp" in k))}


def parse_stat(log: str) -> dict:
    """The last ``stat -liberty`` block: chip area, cell count, flop count.

    Two layouts: yosys 0.33 prints ``Number of cells: N`` then ``CELL  N`` lines;
    yosys 0.70 prints a table ``N  AREA cells`` then ``N  AREA  CELL`` lines. Either
    way the design totals are the last cell-count line of the block (per-module
    sections come first in hierarchical runs) and the flop lines that follow it."""
    blk = log[log.rfind("Printing statistics"):] if "Printing statistics" in log else log
    area = re.findall(r"Chip area for (?:top )?module '\\?([^']+)':\s*([0-9.]+)", blk)
    last = None
    for rx in (_CELLS_OLD, _CELLS_NEW):
        for m in rx.finditer(blk):
            if last is None or m.start() > last.start():
                last = m
    flops = None
    if last is not None:
        tail = blk[last.end():]
        tail = tail[:tail.find("Chip area")] if "Chip area" in tail else tail
        n = [int(c) for _, c in _DFF_OLD.findall(tail)] + [int(c) for c, _ in _DFF_NEW.findall(tail)]
        flops = sum(n) if n else None
    cells = int(last.group(1)) if last else None
    if last is not None and last.re is _CELLS_NEW:
        # yosys 0.70's total line also counts submodule instances and $scopeinfo; report
        # library cells only (what stat -json's per-type counts give): sum the cell-type
        # rows of the totals, skipping $-types, module names and the submodules line
        mods = set(re.findall(r"^=== (\S+) ===", blk, re.M))
        tail = blk[last.end():]
        tail = tail[:tail.find("Chip area")] if "Chip area" in tail else tail
        rows = re.findall(r"^\s*(\d+)\s+\S+\s+(\S+)\s*$", tail, re.M)
        lib = [int(c) for c, name in rows
               if not name.startswith(("$", "\\")) and name not in mods and name != "submodules"]
        if lib:
            cells = sum(lib)
    return {"area_um2": float(area[-1][1]) if area else None, "cells": cells, "flops": flops}


# --- flow ----------------------------------------------------------------------------------


def yosys_version() -> str:
    r = subprocess.run([yosys_bin(), "-V"], capture_output=True, text=True)
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
              flatten: bool = True, top: str | None = None) -> tuple[str, float]:
    work.mkdir(parents=True, exist_ok=True)
    (work / "abc.script").write_text(abc_script)
    top = top or spec.top
    srcs = " ".join(str(p) for p in spec.rtl_paths())
    chp = " ".join(f"-chparam {k} {v}" for k, v in params.items())
    lines = [f"read_verilog -sv -I {set_dir} {srcs}", f"hierarchy -top {top} {chp}"]
    if flatten:
        lines.append(f"synth -top {top} -flatten")
    else:
        keep = " ".join(f"*{m}*" for m in keep_modules(spec))
        lines += ["proc",
                  f"setattr -mod -set keep_hierarchy 1 {keep}" if keep else "",
                  "flatten",
                  f"synth -top {top}"]
    lines += [
        f"dfflibmap -liberty {lib}",
        f"abc -liberty {lib} -script {work / 'abc.script'}",
        "opt_clean",
        f"stat -liberty {lib}",
        # exact numbers for the report: the text table rounds counts >= 1e7 to E-notation
        f"tee -q -o {work / 'stat.json'} stat -json -liberty {lib}",
    ]
    ys = "\n".join(ln for ln in lines if ln) + "\n"
    (work / "synth.ys").write_text(ys)
    t0 = time.time()
    r = subprocess.run([yosys_bin(), "-q", "-l", str(work / "yosys.log"), str(work / "synth.ys")],
                       capture_output=True, text=True)
    dt = time.time() - t0
    log = (work / "yosys.log").read_text() if (work / "yosys.log").exists() else ""
    if r.returncode != 0:
        raise RuntimeError(f"yosys failed ({work / 'yosys.log'}):\n{(r.stdout + r.stderr)[-2000:]}\n"
                           f"{log[-2000:]}")
    return log, dt


def synth_point(spec, set_name: str, lib_name: str, P: int, mode: str, terms: int | None,
                dch: bool, target_ps: float | None = None, legacy: bool = False,
                module: str | None = None, params: dict | None = None) -> dict:
    """One estimate. ``mode == "unit"`` synthesizes ``module`` (one of the IP's own leaf
    modules) alone as the top with its default parameters plus ``params`` (``-chparam``):
    minutes instead of hours, for finding and fixing the stage that sets the critical path."""
    if mode == "unit" and not module:
        raise ValueError("--mode unit needs --module")
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
    ptag = "_".join(f"{k}{v}" for k, v in sorted((params or {}).items()))
    tag = (f"{set_name}__P{P}__{mode}__{lib_name}" + (f"__{module}" if module else "")
           + (f"__{ptag}" if ptag else "") + ("_legacy" if legacy else "")
           + ("_dch" if dch else "") + (f"_D{int(target_ps)}" if target_ps else ""))
    work = RESULTS / "logs" / spec.name / tag
    base_params = {"P": P} if ("P" in spec.params and mode != "unit") else {}
    if mode == "unit":
        base_params.update(params or {})
    ff = ff_overhead_ps(lib_path, lib["dff"])
    rep = {"kind": "estimate", "ip": spec.name, "set": set_name, "P": P, "mode": mode,
           "liberty": {"name": lib_name, "label": lib["label"],
                       "sha256": hashlib.sha256(lib_path.read_bytes()).hexdigest()},
           "yosys": yosys_version(), "yosys_pin": YOSYS_PIN if yosys_version() == YOSYS_PIN_VERSION else None,
           "abc_script": script.strip().replace("\n", "; "),
           "target_ps": target_ps,
           "ff": ff, "n_terms_full": n_full, "points": []}
    points = []
    if mode == "unit":
        rep["module"] = module
        rep["module_params"] = dict(params or {})
        points.append(("unit", {}))
    elif mode in ("full", "hier") or n_full is None:
        points.append((mode if n_full is not None else "full", {}))
    else:
        t = terms or 16
        points.append((f"terms{t}", {"N_TERMS": t}))
        points.append((f"terms{2 * t}", {"N_TERMS": 2 * t}))
    for label, extra in points:
        log, dt = run_yosys(spec, set_dir, lib_path, {**base_params, **extra}, work / label,
                            script, flatten=(mode != "hier"), top=module if mode == "unit" else None)
        delays = parse_abc_delay(log)
        st = parse_stat(log)
        sj = parse_stat_json(work / label / "stat.json")
        if sj is not None:
            st = {**st, **{k: v for k, v in sj.items() if v is not None}}
        pt = {"label": label, "params": {**base_params, **extra}, "delay_ps": max(delays) if delays else None,
              "runtime_s": round(dt, 1), **st}
        rep["points"].append(pt)
        if mode == "hier":
            rep["modules"] = parse_abc_modules(log)   # which stage sets the critical path
    # frequency from the worst critical path over the points
    delay = max(p["delay_ps"] for p in rep["points"] if p["delay_ps"] is not None)
    period = delay + ff["total_ps"]
    f_mhz = 1e6 / period
    rep["delay_ps"] = delay
    rep["period_ps"] = round(period, 1)
    rep["f_est_mhz"] = round(f_mhz, 1)
    rep["throughput_est_msps"] = round(f_mhz * P, 1)
    rep["p_for_640msps"] = math.ceil(640.0 / f_mhz)
    if mode == "unit":
        rep["area_um2"] = rep["points"][0]["area_um2"]
        rep["cells"] = rep["points"][0]["cells"]
        rep["method"] = (f"leaf module {module} synthesized alone (default parameters"
                         f"{' + ' + ptag if ptag else ''}), flattened; delay = ABC stime "
                         "(no wire load) + liberty DFF t_cq + t_setup. A stage probe, not a "
                         "datapath number: never enters docs/results.md")
    elif mode == "hier":
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
    ap.add_argument("--mode", choices=["budget", "full", "hier", "unit"], default="budget")
    ap.add_argument("--terms", type=int, help="budget mode: smaller term count T (and 2T)")
    ap.add_argument("--module", help="unit mode: the leaf module to synthesize alone")
    ap.add_argument("--param", action="append", default=[], metavar="K=V",
                    help="unit mode: -chparam override, e.g. --param K1=1 (repeatable)")
    ap.add_argument("--lib", choices=list(LIBS), default="nangate45")
    ap.add_argument("--legacy-map", action="store_true", dest="legacy",
                    help="old ABC 'map' flow instead of the default &nf flow (comparison)")
    ap.add_argument("--dch", action="store_true", help="legacy flow: dch before map")
    ap.add_argument("--target-ps", type=float, default=None,
                    help=f"ABC delay target in ps (default {DEFAULT_TARGET_PS:.0f} for the &nf flow)")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    if yosys_bin() is None:
        print("yosys not found: run tools/get_yosys.sh", file=sys.stderr)
        return 2
    if yosys_version() != YOSYS_PIN_VERSION:
        print(f"warning: {yosys_version()!r} is not the pinned {YOSYS_PIN} build "
              "(tools/get_yosys.sh); do not commit these numbers", file=sys.stderr)
    spec = load_ipspec(IP_ROOT / args.ip)
    params = dict(kv.split("=", 1) for kv in args.param)
    rep = synth_point(spec, args.set_name, args.lib, args.P, args.mode, args.terms, args.dch,
                      args.target_ps, args.legacy, module=args.module, params=params)
    RESULTS.mkdir(parents=True, exist_ok=True)
    suffix = (("_legacy" if args.legacy else "") + ("_dch" if args.dch else "")
              + (f"_D{int(args.target_ps)}" if args.target_ps else ""))
    if args.mode == "unit":
        # stage probes live in units/: render_tables only reads results/synth/*.json
        ptag = "_".join(f"{k}{v}" for k, v in sorted(params.items()))
        out = args.out or RESULTS / "units" / f"{args.module}{'__' + ptag if ptag else ''}{suffix}.json"
    else:
        out = args.out or RESULTS / f"{spec.name}__{args.set_name}__P{args.P}__{args.mode}{suffix}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1))
    if rep.get("modules"):
        print("  per-module worst ABC delay (ps): " + ", ".join(
            f"{m} {v['delay_ps']:.0f}" + (f" x{v['instances']}" if v["instances"] > 1 else "")
            for m, v in rep["modules"].items()))
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
