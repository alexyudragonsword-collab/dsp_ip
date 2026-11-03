"""Rule 5 guard: tools/synth.py — log parsers, liberty flop overhead, and every result is
labelled an estimate with its method and library. Runs yosys only if it is installed."""

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def sy():
    spec = importlib.util.spec_from_file_location("synth", REPO / "tools" / "synth.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["synth"] = mod
    spec.loader.exec_module(mod)
    return mod


ABC_LOG = """
ABC: + topo
ABC: + stime -p
ABC: WireLoad = "none"  Gates =  17078 ( 14.6 %)   Cap =  3.7 ff (  0.0 %)   Area =    16753.21 (100.0 %)   Delay =  1293.66 ps  (  0.8 %)
ABC: Path  0 --     113 : 0   32 pi       A =   0.00  Df =   0.0
some other module
ABC: WireLoad = "none"  Gates =  100 ( 1.0 %)   Cap =  1.0 ff (  0.0 %)   Area =    10.0 (100.0 %)   Delay =  412.5 ps  (  0.8 %)
"""

STAT_LOG = """
10. Printing statistics.

=== dpd_term ===

   Number of wires:               1000
   Number of cells:              13014
     AOI21_X1                      500
     DFF_X1                        136
     SDFF_X1                        48
     XOR2_X1                      2879

   Chip area for module '\\dpd_term': 16753.210000
"""


def test_parse_abc_delay(sy):
    assert sy.parse_abc_delay(ABC_LOG) == [1293.66, 412.5]
    assert sy.parse_abc_delay("no abc here") == []


def test_parse_stat(sy):
    st = sy.parse_stat(STAT_LOG)
    assert st["area_um2"] == 16753.21 and st["cells"] == 13014 and st["flops"] == 184


def test_liberty_ff_overhead(sy):
    lib = sy.LIBS["nangate45"]["path"]
    if not lib.exists():
        pytest.skip("NanGate45 liberty not fetched (tools/get_liberty.sh)")
    ff = sy.ff_overhead_ps(lib, "DFF_X1")
    assert 50 < ff["t_cq_ps"] < 300 and 10 < ff["t_setup_ps"] < 150
    assert ff["total_ps"] == round(ff["t_cq_ps"] + ff["t_setup_ps"], 1)


def test_cell_block_extraction_is_brace_balanced(sy):
    text = 'cell (A) { pin (Q) { x : 1; } } cell (B) { pin (Q) { y : 2; } }'
    assert sy._cell_block(text, "B").strip().startswith("cell (B)")
    assert "y : 2" in sy._pin_block(sy._cell_block(text, "B"), "Q")
    with pytest.raises(ValueError):
        sy._cell_block(text, "C")


@pytest.mark.skipif(shutil.which("yosys") is None, reason="yosys not installed")
def test_synth_sat_shift_is_estimate(sy, tmp_path):
    lib = sy.LIBS["nangate45"]["path"]
    if not lib.exists():
        pytest.skip("NanGate45 liberty not fetched (tools/get_liberty.sh)")
    out = tmp_path / "r.json"
    assert sy.main(["--ip", "sat_shift", "--set", "signed_w16_s0_o12", "--out", str(out)]) == 0
    r = json.loads(out.read_text())
    assert r["kind"] == "estimate"
    for k in ("method", "liberty", "yosys", "abc_script", "delay_ps", "f_est_mhz", "area_um2",
              "p_for_640msps", "throughput_est_msps"):
        assert k in r, k
    assert r["liberty"]["sha256"] and len(r["liberty"]["sha256"]) == 64
    assert r["f_est_mhz"] > 100 and r["area_um2"] > 0


def test_committed_results_are_estimates():
    for p in (REPO / "results" / "synth").glob("*.json"):
        r = json.loads(p.read_text())
        assert r.get("kind") == "estimate", p
        assert "method" in r and "sha256" in r["liberty"], p


HIER_LOG = """
13.1. Extracting gate netlist of module `$paramod$118576aab\\dpd_acc' to `<abc-temp-dir>/input.blif'..
ABC: WireLoad = "none"  Gates =     92 (  9.8 %)   Area =      106.40 (100.0 %)   Delay =   853.69 ps  ( 42.4 %)
13.2. Extracting gate netlist of module `$paramod$3182646cf\\dpd_term' to `<abc-temp-dir>/input.blif'..
ABC: WireLoad = "none"  Gates =  11124 (  6.7 %)   Area =    12681.02 ( 99.8 %)   Delay =  1678.94 ps  (  2.5 %)
13.3. Extracting gate netlist of module `$paramod$495377c69\\dpd_term' to `<abc-temp-dir>/input.blif'..
ABC: WireLoad = "none"  Gates =   9837 (  6.9 %)   Area =    11184.50 ( 99.7 %)   Delay =  1733.54 ps  (  2.6 %)
13.4. Extracting gate netlist of module `\\dpd_poly' to `<abc-temp-dir>/input.blif'..
ABC: WireLoad = "none"  Gates =  54763 (  1.3 %)   Area =    71555.33 (100.0 %)   Delay =  1440.74 ps  ( 21.3 %)
"""


def test_parse_abc_modules_groups_parameterizations(sy):
    """Per-module worst delay by base name, sorted worst first: the field that says which
    pipeline stage sets f_est (the adder tree was blamed for a year on no evidence)."""
    m = sy.parse_abc_modules(HIER_LOG)
    assert list(m) == ["dpd_term", "dpd_poly", "dpd_acc"]
    assert m["dpd_term"] == {"delay_ps": 1733.54, "instances": 2}
    assert m["dpd_poly"]["instances"] == 1
    assert sy.parse_abc_modules("ABC: Delay = 12.0 ps\n") == {}   # no module context: ignored


def test_committed_hier_results_module_delays_consistent():
    """When a hier JSON carries per-module delays, the headline delay is their max."""
    for p in (REPO / "results" / "synth").glob("*__hier*.json"):
        d = json.loads(p.read_text())
        if "modules" not in d:
            continue
        worst = max(v["delay_ps"] for v in d["modules"].values())
        assert abs(worst - d["delay_ps"]) < 1e-6, p.name
        assert all(v["instances"] >= 1 for v in d["modules"].values())


def test_unit_mode_needs_module(sy):
    from dspip.ipspec import IP_ROOT, load_ipspec

    spec = load_ipspec(IP_ROOT / "dpd_poly")
    with pytest.raises(ValueError, match="--module"):
        sy.synth_point(spec, "ddr_r1_w16", "nangate45", 1, "unit", None, False)


@pytest.mark.skipif(not shutil.which("yosys"), reason="no yosys")
def test_unit_probe_is_estimate_and_stays_out_of_results(sy, tmp_path):
    """A stage probe (sat_shift alone is seconds) is labelled, carries its module, and the
    default output path is results/synth/units/ which render_tables never reads."""
    if not sy.LIBS["nangate45"]["path"].exists():
        pytest.skip("liberty not fetched (tools/get_liberty.sh)")
    from dspip.ipspec import IP_ROOT, load_ipspec

    spec = load_ipspec(IP_ROOT / "sat_shift")
    rep = sy.synth_point(spec, "signed_w40_s12_o16", "nangate45", 1, "unit", None, False,
                         module="sat_shift", params={"W_IN": "24"})
    assert rep["kind"] == "estimate" and rep["mode"] == "unit" and rep["module"] == "sat_shift"
    assert rep["module_params"] == {"W_IN": "24"} and rep["delay_ps"] > 0
    assert "never enters docs/results.md" in rep["method"]
    rc = sy.main(["--ip", "sat_shift", "--set", "signed_w40_s12_o16", "--mode", "unit",
                  "--module", "sat_shift", "--param", "W_IN=24", "--out", str(tmp_path / "u.json")])
    assert rc == 0 and json.loads((tmp_path / "u.json").read_text())["module"] == "sat_shift"
