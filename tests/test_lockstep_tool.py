"""Rule 4 guard: tools/lockstep.py — the comparison reports the first mismatching sample and
the reference's registers, the lock catches a changed vector, --all enumerates every IP.
These tests need no simulator; tests/test_rtl_lockstep.py runs the real thing."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from dspip import vectors as V
from dspip.ipspec import IP_ROOT, all_ips, load_ipspec

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def ls():
    spec = importlib.util.spec_from_file_location("lockstep", REPO / "tools" / "lockstep.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["lockstep"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_compare_reports_first_mismatch(ls, tmp_path):
    g, r = tmp_path / "g.txt", tmp_path / "r.txt"
    V.write_ints(g, [1, 2, 3, 4, 5])
    V.write_ints(r, [1, 2, 3, 4, 5, 0])        # drain samples beyond the golden are fine
    c = ls.compare_files(g, r)
    assert c["mismatches"] == 0 and c["first"] is None and c["n"] == 5
    V.write_ints(r, [1, 2, -3, 4, 9])
    c = ls.compare_files(g, r)
    assert c["mismatches"] == 2 and c["first"] == 2 and c["golden"] == 3 and c["rtl"] == -3
    V.write_ints(r, [1, 2])
    c = ls.compare_files(g, r)
    assert c["mismatches"] == 3 and "RTL wrote 2 < 5" in c["detail"]
    c = ls.compare_files(g, tmp_path / "missing.txt")
    assert c["mismatches"] == 5 and c["first"] == 0


def test_lock_detects_changed_vector(tmp_path):
    d = tmp_path / "s"
    V.write_ints(d / "x.txt", [1, 2, 3])
    lock = {"sets": {"s": V.lock_entry(d, "cmd")}}
    assert V.verify_set(lock, "s", d) == []
    V.write_ints(d / "x.txt", [1, 2, 4])
    probs = V.verify_set(lock, "s", d)
    assert len(probs) == 1 and "x.txt" in probs[0] and "sha256" in probs[0]
    V.write_ints(d / "rtl_y.txt", [0])          # tb outputs are not part of the lock
    V.write_ints(d / "x.txt", [1, 2, 3])
    assert V.verify_set(lock, "s", d) == []
    assert V.verify_set(lock, "other", d) == ["other: not in lock"]


def test_param_points_cartesian(ls, tmp_path):
    spec = load_ipspec(IP_ROOT / "sat_shift")
    assert ls.param_points(spec, None) == [{}]
    assert ls.param_points(spec, {"P": ["1", "2"]}) == [{"P": "1"}, {"P": "2"}]
    assert ls.param_points(spec, {"P": ["1"], "W": ["8", "9"]}) == [
        {"P": "1", "W": "8"}, {"P": "1", "W": "9"}]


def test_all_enumerates_every_ip(ls):
    names = {s.name for s in all_ips()}
    assert names == {p.parent.name for p in IP_ROOT.glob("*/ip.yaml")}
    assert "sat_shift" in names


def test_sat_shift_lock_matches_regeneration(tmp_path):
    """Rule 3: the generated set hashes exactly what the lock pins."""
    from dspip.ip.sat_shift.ref import generate

    spec = load_ipspec(IP_ROOT / "sat_shift")
    lock = V.load_lock(spec.lock_path)
    for vs in spec.vector_sets:
        d = tmp_path / vs.name
        generate(vs.name, d)
        assert V.verify_set(lock, vs.name, d) == [], vs.name
    assert spec.lock_path.exists()
    json.loads(spec.lock_path.read_text())


def test_format_report_shows_probe(ls):
    rep = {"status": "FAIL", "ip": "x", "set": "s", "sim": "iverilog", "params": {"P": "2"},
           "mismatches": 3, "first_mismatch": {"sample": 17, "file": "y.txt", "golden": 5,
                                               "rtl": 6}, "probe": "acc=123\ny=5"}
    txt = ls.format_report(rep)
    assert "sample 17" in txt and "rtl=6 golden=5" in txt and "acc=123" in txt and "P=2" in txt
