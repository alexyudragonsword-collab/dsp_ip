"""The workflow file must parse: an unquoted ``name: a (b: c)`` step name made GitHub reject
the whole workflow for eight pushes (runs 7-14, "0 jobs, failure") before anyone noticed."""

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]


def test_ci_workflow_parses_and_has_every_job():
    d = yaml.safe_load((REPO / ".github/workflows/ci.yml").read_text())
    assert set(d["jobs"]) == {"lint", "test", "lockstep", "synth", "synth-long", "vendor-drift",
                              "fixed-vs-float"}
    assert d["jobs"]["synth-long"]["if"] == "github.event_name == 'workflow_dispatch'"
    assert d["jobs"]["synth-long"]["strategy"]["matrix"] == {"set": ["ddr_r1_w16", "gmp510_w16"], "P": [1, 2, 4]}
    assert d[True].get("workflow_dispatch", "missing") is None or isinstance(d[True]["workflow_dispatch"], dict)
    for name in ("synth", "synth-long"):   # pinned yosys, never the runner's apt one
        runs = [st.get("run", "") for st in d["jobs"][name]["steps"]]
        assert "tools/get_yosys.sh" in runs, name
        assert not any("install -y yosys" in r for r in runs), name
    for job in d["jobs"].values():
        for step in job["steps"]:
            assert isinstance(step, dict) and ("run" in step or "uses" in step), step


# Node 20 is deprecated on the runners; these majors run on node24 (each tag's action.yml,
# `runs.using`, checked 2026-11-05).
NODE24 = {"actions/checkout": "v7", "actions/setup-python": "v7", "actions/cache": "v6",
          "actions/upload-artifact": "v7"}


def test_actions_are_node24_versions():
    d = yaml.safe_load((REPO / ".github/workflows/ci.yml").read_text())
    used = [st["uses"] for job in d["jobs"].values() for st in job["steps"] if "uses" in st]
    assert used
    for u in used:
        action, ver = u.split("@")
        assert action in NODE24, f"{u}: unknown action, check its node runtime and add it"
        assert ver == NODE24[action], u


def test_lockstep_runs_both_toolchains():
    """Distro simulators (5.020 / 12) and the pinned bundle's (5.053 / 14), every IP."""
    d = yaml.safe_load((REPO / ".github/workflows/ci.yml").read_text())
    job = d["jobs"]["lockstep"]
    assert job["strategy"]["matrix"]["toolchain"] == ["distro", "bundle"]
    runs = "\n".join(st.get("run", "") for st in job["steps"])
    assert "tools/get_yosys.sh" in runs and "DSPIP_SIM_BIN=" in runs
    assert "--all --sim verilator" in runs and "--all --sim iverilog" in runs
    assert "tests/test_sim_quirks.py" in runs
