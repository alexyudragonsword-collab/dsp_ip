#!/usr/bin/env python3
"""Place-and-route estimate of one synthesizable block with OpenROAD (rule 5: open flow only,
"estimate"). It answers one question: how far is the no-wire-load ABC critical path that
``tools/synth.py`` reports from the path after placement, clock-tree synthesis and global
routing, with wire parasitics?

    python tools/pnr.py --ip dpd_poly --set ddr_r1_w16 --module dpd_term \\
        --param K1=1 --param Q_PAIR=15 --param SH=14
    python tools/pnr.py --ip dtc_dither --set ramp            # the IP's own top

Flow (NanGate45, the pinned OpenROAD-flow-scripts platform files; OpenROAD from
``tools/get_openroad.sh``):

1. yosys: the same synthesis as ``synth.py`` (pinned yosys, ``synth -flatten``, the default
   ``sopb`` ABC script, NanGate45 liberty), then ORFS's netlist clean-up (tie cells,
   ``setundef -zero``, ``splitnets``, ``insbuf``) and ``write_verilog``.
2. OpenROAD: floorplan at ``--util`` core utilization, tracks, pins, global placement,
   ``repair_design`` (max slew / cap / fanout buffering), detailed placement, clock-tree
   synthesis, ``global_route``, ``estimate_parasitics -global_routing``. By default no
   timing-driven optimization: the point is to compare the same netlist, not a better one;
   ``--repair-timing`` adds ``repair_timing -setup`` after CTS to see what it recovers.
3. Timing: a clock of ``--period`` ns on ``clk``, I/O constrained to the clock with zero
   external delay; ``f_est = 1 / (period - worst slack)`` at three points: the final netlist
   with ideal wires and an ideal clock (a second OpenROAD run), after placement, and after
   global routing with the propagated clock tree. ``wire_penalty`` = ideal / routed - 1 is the
   cost of the wires and the clock tree with the timer and the gate sizes held equal. The ABC
   delay from step 1 is reported too; it differs from the ideal-wire number by ABC's own
   timing model and by ``repair_design``'s gate sizing.

Detailed routing, RC extraction from the routed layout, and corners other than typical are not
done: the routed-wire numbers are an estimate between "no wires" and sign-off.
JSON goes to ``results/pnr/``; it never enters docs/results.md.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import synth as SY  # noqa: E402
from dspip.ipspec import IP_ROOT, load_ipspec  # noqa: E402

PLATFORM = REPO / "third_party/orfs/flow/platforms/nangate45"
OPENROAD = REPO / "third_party/openroad-env/bin/openroad-dspip"
RESULTS = REPO / "results" / "pnr"
SITE = "FreePDK45_38x28_10R_NP_162NW_34O"


def netlist(spec, set_dir: Path, top: str, params: dict, work: Path,
            hier: bool = False) -> tuple[str, float]:
    """Synthesize ``top`` exactly as synth.py does (flattened, sopb) and write the netlist.
    ``hier``: as ``synth.py --mode hier`` instead (the IP's own modules kept, so ABC maps each
    one separately; the only way a 1.6 M-cell dpd_poly gets through ABC), then the mapped
    netlist is flattened for OpenROAD. Returns (netlist path, ABC delay in ps, the worst
    module's when hier)."""
    lib = SY.LIBS["nangate45"]["path"]
    work.mkdir(parents=True, exist_ok=True)
    (work / "abc.script").write_text(SY.abc_script(False, None))
    srcs = " ".join(str(p) for p in spec.rtl_paths())
    chp, strs = SY.chparam_args(spec, params)
    out = work / f"{top}.v"
    keep = " ".join(f"*{m}*" for m in SY.keep_modules(spec))
    if hier and not keep:
        raise ValueError(f"{spec.name}: --hier needs the IP's own sub-modules; it has none")
    ys = "\n".join(ln for ln in [
        f"read_verilog -sv -I {set_dir} {srcs}",
        f"chparam {strs} {top}" if strs else "",
        f"hierarchy -top {top} {chp}",
        f"rename -top {top}" if spec.extra.get("synth_chparam") == "set" else "",
        *(SY.synth_lines(top, True, "default") if not hier else [
            "proc",
            "setattr -mod -set keep_hierarchy 1 " + keep,
            "flatten", *SY.synth_lines(top, False, "default")]),
        f"dfflibmap -liberty {lib}",
        f"abc -liberty {lib} -script {work / 'abc.script'}",
        "opt_clean",
        *(["setattr -mod -unset keep_hierarchy", "flatten", "opt_clean"] if hier else []),
        "hilomap -singleton -hicell LOGIC1_X1 Z -locell LOGIC0_X1 Z",
        "setundef -zero",
        "splitnets",
        "opt_clean -purge",
        "insbuf -buf BUF_X1 A Z",
        f"write_verilog -noexpr -noattr -nohex -nodec {out}",
    ] if ln) + "\n"
    (work / "synth.ys").write_text(ys)
    r = subprocess.run([SY.yosys_bin(), "-q", "-l", str(work / "yosys.log"), str(work / "synth.ys")],
                       capture_output=True, text=True)
    log = (work / "yosys.log").read_text() if (work / "yosys.log").exists() else ""
    if r.returncode != 0:
        raise RuntimeError(f"yosys failed ({work / 'yosys.log'}):\n{log[-2000:]}")
    # a mapped netlist has no arithmetic left, so `signed` on ports/wires means nothing, and
    # OpenSTA's Verilog reader rejects it
    out.write_text(re.sub(r"^(\s*(?:input|output|inout|wire|reg)\s+)signed\s+", r"\1",
                          out.read_text(), flags=re.M))
    delays = SY.parse_abc_delay(log)
    return str(out), max(delays) if delays else float("nan")


TCL = """\
read_lef {platform}/lef/NangateOpenCellLibrary.tech.lef
read_lef {platform}/lef/NangateOpenCellLibrary.macro.mod.lef
read_liberty {lib}
read_verilog {netlist}
link_design {top}
create_clock -name clk -period {period} [get_ports clk]
set_input_delay 0 -clock clk [delete_from_list [all_inputs] [get_ports clk]]
set_output_delay 0 -clock clk [all_outputs]
source {platform}/setRC.tcl
initialize_floorplan -utilization {util} -aspect_ratio 1 -core_space 2 -site {site}
source {platform}/make_tracks.tcl
place_pins -hor_layers metal5 -ver_layers metal6
global_placement -density {density}
estimate_parasitics -placement
repair_design
detailed_placement
estimate_parasitics -placement
puts "DSPIP placed_wns [sta::worst_slack -max]"
clock_tree_synthesis -root_buf BUF_X4 -buf_list {{BUF_X4 BUF_X8}} -sink_clustering_enable
set_propagated_clock [all_clocks]
{repair_timing}detailed_placement
set_routing_layers -signal metal2-metal10 -clock metal2-metal10
global_route -congestion_iterations 50
estimate_parasitics -global_routing
puts "DSPIP routed_wns [sta::worst_slack -max]"
puts "DSPIP routed_tns [sta::total_negative_slack -max]"
report_checks -path_delay max -format full_clock_expanded -digits 1
report_design_area
write_verilog {final}
puts "DSPIP done"
"""

# The same final netlist (after repair_design and CTS) timed again with no parasitics and an
# ideal clock: what the wires and the clock tree cost, with the delay engine and the gate
# sizes held equal. (ABC's number differs from it by both its own timing model and sizing.)
# --stop-after place: the same flow cut after detailed placement (no CTS, no global route),
# for designs whose global route does not fit in memory; the placed slack is then the result
_PLACED = 'puts "DSPIP placed_wns [sta::worst_slack -max]"\n'
TCL_PLACE = TCL[:TCL.index(_PLACED) + len(_PLACED)] + """\
report_checks -path_delay max -format full_clock_expanded -digits 1
report_design_area
write_verilog {final}
puts "DSPIP done"
"""
TCL_IDEAL = """\
read_lef {platform}/lef/NangateOpenCellLibrary.tech.lef
read_lef {platform}/lef/NangateOpenCellLibrary.macro.mod.lef
read_liberty {lib}
read_verilog {final}
link_design {top}
create_clock -name clk -period {period} [get_ports clk]
set_input_delay 0 -clock clk [delete_from_list [all_inputs] [get_ports clk]]
set_output_delay 0 -clock clk [all_outputs]
puts "DSPIP ideal_wns [sta::worst_slack -max]"
puts "DSPIP done"
"""


def run(ip: str, set_name: str, module: str | None, params: dict, period_ns: float,
        util: int, density: float, repair_timing: bool = False, hier: bool = False,
        stop_after: str | None = None) -> dict:
    spec = load_ipspec(IP_ROOT / ip)
    set_dir = spec.set_dir(set_name)
    top = module or spec.top
    if top == spec.top:
        params = {**SY.ip_synth_params(spec, set_dir), **params}
    ptag = "_".join(f"{k}{v}" for k, v in sorted(params.items()) if SY._is_int(v))
    work = RESULTS / "work" / ip / (f"{set_name}__{top}" + (f"__{ptag}" if ptag else "")
                                     + ("__rt" if repair_timing else "") + ("__hier" if hier else "")
                                     + (f"__{stop_after}" if stop_after else ""))
    t0 = time.time()
    nl, abc_ps = netlist(spec, set_dir, top, params, work, hier)
    lib = SY.LIBS["nangate45"]["path"]
    final = work / f"{top}_final.v"
    tcl = (TCL_PLACE if stop_after == "place" else TCL).format(platform=PLATFORM, lib=lib, netlist=nl, top=top, period=period_ns,
                     util=util, density=density, site=SITE, final=final,
                     repair_timing=("estimate_parasitics -placement\nrepair_timing -setup\n"
                                    if repair_timing else ""))
    (work / "pnr.tcl").write_text(tcl)
    r = subprocess.run([str(OPENROAD), "-no_init", "-exit", str(work / "pnr.tcl")],
                       capture_output=True, text=True, cwd=work)
    log = r.stdout + r.stderr
    (work / "openroad.log").write_text(log)
    if r.returncode != 0 or "DSPIP done" not in log:
        raise RuntimeError(f"openroad failed ({work / 'openroad.log'}):\n{log[-3000:]}")

    (work / "ideal.tcl").write_text(TCL_IDEAL.format(platform=PLATFORM, lib=lib, final=final,
                                                    top=top, period=period_ns))
    r2 = subprocess.run([str(OPENROAD), "-no_init", "-exit", str(work / "ideal.tcl")],
                        capture_output=True, text=True, cwd=work)
    (work / "ideal.log").write_text(r2.stdout + r2.stderr)
    if r2.returncode != 0 or "DSPIP done" not in r2.stdout:
        raise RuntimeError(f"openroad (ideal) failed ({work / 'ideal.log'})")
    log2 = r2.stdout

    def num(tag, text=None):
        m = re.search(rf"DSPIP {tag} (\S+)", text if text is not None else log)
        return float(m.group(1)) if m else float("nan")

    unit_ns = 1.0          # OpenSTA reports in the liberty's time unit (NanGate45: ns)
    placed, routed = num("placed_wns") * unit_ns, num("routed_wns") * unit_ns
    ideal = num("ideal_wns", log2) * unit_ns
    area = re.search(r"Design area (\S+) u\^2 (\S+)% utilization", log)
    ff = SY.ff_overhead_ps(lib, SY.LIBS["nangate45"]["dff"])
    rep = {
        "kind": "estimate", "ip": ip, "set": set_name, "module": top,
        "params": {k: v for k, v in params.items() if SY._is_int(v)},
        "tool": {"openroad": subprocess.run([str(OPENROAD), "-version"], capture_output=True,
                                            text=True).stdout.strip(),
                 "yosys": SY.yosys_version(), "abc": SY.DEFAULT_ABC,
                 "platform": "OpenROAD-flow-scripts@e5cc6e7 nangate45"},
        "period_ns": period_ns, "utilization_pct": util, "place_density": density,
        "repair_timing": repair_timing, "synth": "hier" if hier else "flat",
        "abc_delay_ps": abc_ps,
        "abc_f_est_mhz": round(1e6 / (abc_ps + ff["total_ps"]), 1),
        "ideal_wns_ns": ideal, "placed_wns_ns": placed, "routed_wns_ns": routed,
        "ideal_f_est_mhz": round(1e3 / (period_ns - ideal), 1),
        "routed_tns_ns": num("routed_tns"),
        "placed_f_est_mhz": round(1e3 / (period_ns - placed), 1),
        "routed_f_est_mhz": round(1e3 / (period_ns - routed), 1),
        "area_um2": float(area.group(1)) if area else None,
        "runtime_s": round(time.time() - t0, 1),
        "method": ("yosys (synth.py flow, sopb) -> OpenROAD floorplan / place / repair_design / "
                   "CTS / global_route; worst slack with global-route parasitics (setRC.tcl), "
                   "no repair_timing, no detailed route; f_est = 1 / (period - WNS)"),
    }
    # wire + clock-tree penalty on the same netlist and the same timer: ideal / routed f
    rep["wire_penalty"] = round(rep["ideal_f_est_mhz"] / rep["routed_f_est_mhz"] - 1, 4) \
        if not math.isnan(rep["routed_f_est_mhz"]) else None
    if stop_after == "place":
        rep["stopped_after"] = "place"
        rep["placed_penalty"] = round(rep["ideal_f_est_mhz"] / rep["placed_f_est_mhz"] - 1, 4)
        rep["method"] = ("yosys (synth.py flow, sopb) -> OpenROAD floorplan / place / repair_design "
                         "/ detailed placement, stopped there (no CTS, no global route); worst "
                         "slack with placement parasitics (setRC.tcl), no repair_timing; "
                         "f_est = 1 / (period - WNS)")
        for k in ("routed_wns_ns", "routed_tns_ns", "routed_f_est_mhz", "wire_penalty"):
            rep[k] = None
        m = re.search(r"Startpoint: (\S+).*?Endpoint: (\S+)", log, flags=re.S)
        rep["critical_path"] = {"start": m.group(1), "end": m.group(2)} if m else None
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ip", required=True)
    ap.add_argument("--set", required=True, dest="set_name")
    ap.add_argument("--module", help="a leaf module instead of the IP's top")
    ap.add_argument("--param", action="append", default=[], metavar="K=V")
    ap.add_argument("--period", type=float, default=1.5625, help="clock period in ns (640 MHz)")
    ap.add_argument("--util", type=int, default=40, help="core utilization, percent")
    ap.add_argument("--density", type=float, default=0.6, help="global placement density")
    ap.add_argument("--repair-timing", action="store_true",
                    help="also run repair_timing -setup after CTS (timing-driven sizing/buffering)")
    ap.add_argument("--hier", action="store_true",
                    help="map the IP's own modules separately (synth.py --mode hier), then "
                         "flatten the mapped netlist; for designs too big for flat ABC")
    ap.add_argument("--stop-after", choices=["place"],
                    help="cut the flow after detailed placement (when global route does not fit "
                         "in memory); the JSON then has no routed numbers")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    if not OPENROAD.exists():
        print("openroad not installed: run tools/get_openroad.sh", file=sys.stderr)
        return 2
    params = dict(kv.split("=", 1) for kv in args.param)
    rep = run(args.ip, args.set_name, args.module, params, args.period, args.util, args.density,
              args.repair_timing, args.hier, args.stop_after)
    RESULTS.mkdir(parents=True, exist_ok=True)
    ptag = "_".join(f"{k}{v}" for k, v in sorted(rep["params"].items()))
    out = args.out or RESULTS / (f"{args.ip}__{rep['module']}{'__' + ptag if ptag else ''}"
                                 + ("__rt" if args.repair_timing else "")
                                 + ("__hier" if args.hier else "")
                                 + (f"__{args.stop_after}" if args.stop_after else "") + ".json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1))
    routed = (f"routed WNS {rep['routed_wns_ns']:.3f} ns -> {rep['routed_f_est_mhz']} MHz "
              f"(wire penalty {100 * rep['wire_penalty']:.1f} %)") if not args.stop_after else \
        f"stopped after placement (placement penalty {100 * rep['placed_penalty']:.1f} %)"
    print(f"[estimate] {args.ip}/{rep['module']}: ABC {rep['abc_delay_ps']:.0f} ps -> "
          f"{rep['abc_f_est_mhz']} MHz; final netlist, ideal wires -> {rep['ideal_f_est_mhz']} MHz; "
          f"placed WNS {rep['placed_wns_ns']:.3f} ns -> {rep['placed_f_est_mhz']} MHz; {routed}; "
          f"area {rep['area_um2']} um^2  [{rep['runtime_s']}s]\n"
          f"  -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
