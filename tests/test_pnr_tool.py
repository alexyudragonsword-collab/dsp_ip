"""Rule 5 guard for tools/pnr.py (OpenROAD place-and-route estimates): the committed results
are labelled estimates from the pinned tools, the flow script does what its docstring says,
and (when OpenROAD is installed) a small block runs end to end and reproduces its JSON."""
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results" / "pnr"


@pytest.fixture(scope="module")
def pnr():
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("pnr", REPO / "tools" / "pnr.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_flow_script_steps_in_order(pnr):
    t = pnr.TCL
    steps = ["link_design", "create_clock", "setRC.tcl", "initialize_floorplan", "place_pins",
             "global_placement", "repair_design", "detailed_placement", "clock_tree_synthesis",
             "set_propagated_clock", "global_route", "estimate_parasitics -global_routing",
             "write_verilog"]
    pos = [t.index(s) for s in steps]
    assert pos == sorted(pos)
    assert "{repair_timing}" in t and "repair_timing" not in t.replace("{repair_timing}", "")
    assert "estimate_parasitics" not in pnr.TCL_IDEAL     # the ideal-wire run has no wires


def test_committed_results_are_estimates_from_the_pinned_tools(pnr):
    files = sorted(RESULTS.glob("*.json"))
    assert files, "no committed P&R results"
    sy = sys.modules.get("synth")
    for f in files:
        r = json.loads(f.read_text())
        assert r["kind"] == "estimate" and "no detailed route" in r["method"], f.name
        assert r["tool"]["openroad"] == "2.0-12381-g01bba3695", f.name
        assert r["tool"]["yosys"] == sy.YOSYS_PIN_VERSION and r["tool"]["abc"] == "sopb"
        for k in ("ideal", "placed", "routed"):
            f_mhz = 1e3 / (r["period_ns"] - r[f"{k}_wns_ns"])
            assert abs(f_mhz - r[f"{k}_f_est_mhz"]) < 0.1, (f.name, k)
        assert abs(r["ideal_f_est_mhz"] / r["routed_f_est_mhz"] - 1 - r["wire_penalty"]) < 1e-3


def test_p1_conclusion_recorded_in_docs():
    """The P&R section states the measured dpd_term penalty and the P = 1 verdict."""
    doc = (REPO / "docs" / "synthesis.md").read_text()
    m = json.loads((RESULTS / "dpd_poly__dpd_term__K11_Q_PAIR15_SH14.json").read_text())
    assert f"{m['routed_f_est_mhz']:.0f} MHz" in doc
    assert re.search(r"P = 1 .*edge", doc)


@pytest.mark.skipif(not (REPO / "third_party/openroad-env/bin/openroad-dspip").exists(),
                    reason="openroad not installed (tools/get_openroad.sh)")
def test_small_block_reproduces(pnr):
    rep = pnr.run("dtc_dither", "ramp", None, {}, 1.5625, 40, 0.6)
    ref = json.loads((RESULTS / "dtc_dither__dtc_efm1.json").read_text())
    for k in ("abc_delay_ps", "ideal_wns_ns", "placed_wns_ns", "routed_wns_ns", "area_um2"):
        assert rep[k] == ref[k], k
