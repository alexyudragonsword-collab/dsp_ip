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
    for job in d["jobs"].values():
        for step in job["steps"]:
            assert isinstance(step, dict) and ("run" in step or "uses" in step), step
