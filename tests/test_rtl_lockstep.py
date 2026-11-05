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
import sys
from pathlib import Path

import pytest

from dspip import sims as S
from dspip import vectors as V
from dspip.ipspec import IP_ROOT, all_ips

REPO = Path(__file__).resolve().parents[1]

_HAVE_SIM = bool(S.installed())
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
    return S.installed()  # $DSPIP_SIM_BIN (pinned bundle) or PATH


def _points():
    pts = []
    for spec in all_ips(IP_ROOT):
        for vs in spec.vector_sets:
            pts.append((spec.name, vs.name))
    return pts


def _ip_sims(spec):
    """Installed simulators this IP runs under (ip.yaml ``sims:``); at least one must be
    installed, otherwise the IP would be silently unverified."""
    sims = [s for s in _sims() if s in spec.sims]
    assert sims, f"{spec.name}: none of its simulators {list(spec.sims)} is installed"
    return sims


@pytest.mark.parametrize("sim", _sims())
@pytest.mark.parametrize("ip,vset", _points())
def test_rtl_lockstep(ls, ip, vset, sim):
    """Every vector set, every parameter point: zero mismatches."""
    from dspip.ipspec import load_ipspec

    spec = load_ipspec(IP_ROOT / ip)
    if sim not in spec.sims:
        _ip_sims(spec)  # the other simulator must be there to cover this IP
        pytest.skip(f"{ip}: ip.yaml sims={list(spec.sims)} ({spec.extra.get('sims_reason', '')})")
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
    sim = _ip_sims(spec)[-1]  # the cheaper one to compile (iverilog if present)
    params = ls.param_points(spec, None)[0]
    monkeypatch.setattr(ls, "RESULTS", tmp_path)
    # a clean pass first (regenerates + verifies the lock)
    rep = ls.run_point(spec, vs.name, sim, params)
    assert rep["status"] == "PASS", ls.format_report(rep)
    if spec.check == "python":
        golden = spec.set_dir(vs.name) / spec.compare[0].golden
    else:
        # a self-checking (Halo-style) tb: corrupt the golden file ip.yaml names
        golden = spec.set_dir(vs.name) / spec.extra["mutation_file"]
    original = golden.read_text()
    lines = V.read_ints(golden)
    k = len(lines) // 2
    lines[k] = lines[k] + 1 if lines[k] < 0 else lines[k] - 1
    V.write_ints(golden, lines)
    try:
        rep2 = ls.run_point(spec, vs.name, sim, params, generate=False, verify_lock=False)
    finally:
        golden.write_text(original)
    assert rep2["status"] == "FAIL", ls.format_report(rep2)
    if spec.check == "python":
        assert rep2["mismatches"] == 1
        assert rep2["first_mismatch"]["sample"] == k
        if spec.probe:
            assert rep2.get("probe"), "probe text missing"
    else:
        assert rep2["sim_rc"] != 0 and "FAIL" in rep2["sim_tail"]
    # and the lock catches the corruption too
    V.write_ints(golden, lines)
    try:
        rep3 = ls.run_point(spec, vs.name, sim, params, generate=False)
        assert rep3["status"] == "LOCK"
    finally:
        golden.write_text(original)
    assert golden.read_text() == original
