"""Rule 1: the RTL equals the Python reference bit for bit on every vector of every IP —
and the check is not vacuous: corrupt one golden sample and it must FAIL.

Runs the real tools/lockstep.py against every ``ip/*/ip.yaml`` (so a new IP is covered by
adding its ip.yaml) with whichever simulator is installed; set DSPIP_REQUIRE_SIM=1 to make a
missing simulator a failure (the lockstep CI job does). Adapted from Halo_Serdes@6e79c4a
tests/test_rtl_lockstep.py (mutation step: change one golden line, re-run the compare).
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path

import pytest

from dspip import vectors as V
from dspip.ipspec import IP_ROOT, all_ips

REPO = Path(__file__).resolve().parents[1]

_HAVE_SIM = bool(shutil.which("verilator") or shutil.which("iverilog"))
if not _HAVE_SIM and os.environ.get("DSPIP_REQUIRE_SIM"):
    raise RuntimeError("DSPIP_REQUIRE_SIM set but neither verilator nor iverilog is installed")
pytestmark = pytest.mark.skipif(not _HAVE_SIM, reason="no simulator (verilator/iverilog)")


@pytest.fixture(scope="module")
def ls():
    spec = importlib.util.spec_from_file_location("lockstep", REPO / "tools" / "lockstep.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["lockstep"] = mod
    spec.loader.exec_module(mod)
    return mod


def _sims():
    return [s for s in ("verilator", "iverilog") if shutil.which(s)]


def _points():
    pts = []
    for spec in all_ips(IP_ROOT):
        for vs in spec.vector_sets:
            pts.append((spec.name, vs.name))
    return pts


@pytest.mark.parametrize("sim", _sims())
@pytest.mark.parametrize("ip,vset", _points())
def test_rtl_lockstep(ls, ip, vset, sim):
    """Every vector set, every parameter point: zero mismatches."""
    from dspip.ipspec import load_ipspec

    spec = load_ipspec(IP_ROOT / ip)
    reps = ls.run_ip(spec, sim, sets=[vset])
    assert reps, "no points ran"
    for rep in reps:
        assert rep["status"] == "PASS", ls.format_report(rep)
        assert rep["mismatches"] == 0
        if spec.check == "python":
            assert rep["n"] > 100


@pytest.mark.parametrize("ip", sorted({p[0] for p in _points()}))
def test_lockstep_mutation_fails(ls, ip, tmp_path, monkeypatch):
    """Non-vacuous: one corrupted golden line -> FAIL, naming the sample."""
    from dspip.ipspec import load_ipspec

    spec = load_ipspec(IP_ROOT / ip)
    vs = spec.vector_sets[0]
    sim = _sims()[-1]  # the cheaper one to compile (iverilog if present)
    params = ls.param_points(spec, None)[0]
    monkeypatch.setattr(ls, "RESULTS", tmp_path)
    # a clean pass first (regenerates + verifies the lock)
    rep = ls.run_point(spec, vs.name, sim, params)
    assert rep["status"] == "PASS", ls.format_report(rep)
    if spec.check != "python":
        pytest.skip("tb self-check IPs are mutated by their own tb test")
    golden = spec.set_dir(vs.name) / spec.compare[0].golden
    lines = V.read_ints(golden)
    k = len(lines) // 2
    lines[k] = lines[k] + 1 if lines[k] < 0 else lines[k] - 1
    V.write_ints(golden, lines)
    try:
        rep2 = ls.run_point(spec, vs.name, sim, params, generate=False, verify_lock=False)
    finally:
        # restore by regenerating the set
        ls.ensure_vectors(spec, vs.name, generate=True)
    assert rep2["status"] == "FAIL"
    assert rep2["mismatches"] == 1
    assert rep2["first_mismatch"]["sample"] == k
    if spec.probe:
        assert rep2.get("probe"), "probe text missing"
    # and the lock catches the corruption too
    V.write_ints(golden, lines)
    try:
        rep3 = ls.run_point(spec, vs.name, sim, params, generate=False)
        assert rep3["status"] == "LOCK"
    finally:
        ls.ensure_vectors(spec, vs.name, generate=True)
