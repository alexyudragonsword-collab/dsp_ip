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
