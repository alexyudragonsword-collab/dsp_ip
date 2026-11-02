"""The workflow file must parse: an unquoted ``name: a (b: c)`` step name made GitHub reject
the whole workflow for eight pushes (runs 7-14, "0 jobs, failure") before anyone noticed."""

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]


def test_ci_workflow_parses_and_has_every_job():
    d = yaml.safe_load((REPO / ".github/workflows/ci.yml").read_text())
    assert set(d["jobs"]) == {"lint", "test", "lockstep", "synth", "vendor-drift", "fixed-vs-float"}
    for job in d["jobs"].values():
        for step in job["steps"]:
            assert isinstance(step, dict) and ("run" in step or "uses" in step), step
