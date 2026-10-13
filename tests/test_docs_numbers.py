"""Rule 5 guard: documented numbers come from recorded results, and no throughput is claimed
without a synthesis result behind it."""

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def rt():
    spec = importlib.util.spec_from_file_location("render_tables", REPO / "tools" / "render_tables.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["render_tables"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_docs_tables_generated_from_json(rt):
    """docs/results.md must equal a fresh render of results/*.json."""
    out = REPO / "docs" / "results.md"
    if not out.exists():
        pytest.skip("docs/results.md not rendered yet")
    assert out.read_text() == rt.render(), "docs/results.md is stale or hand-edited"


def test_throughput_claim_needs_synth():
    """Any line in README/docs/cairn that states a throughput in MSPS must point at the
    synthesis estimate (results/synth, docs/results.md or 'estimate'); the only exception is
    the *target* (640 MSPS) and generated tables."""
    synth_json = list((REPO / "results" / "synth").glob("dpd_poly*.json"))
    offenders = []
    for md in [REPO / "README.md", *(REPO / "docs").glob("*.md"), *(REPO / "cairn").glob("*.md")]:
        if md.name == "results.md":
            continue
        for ln in md.read_text().splitlines():
            if not re.search(r"\d\s*MSPS", ln):
                continue
            nums = {int(n) for n in re.findall(r"(\d+)\s*MSPS", ln)}
            if nums <= {640}:
                continue            # the target, not a claim
            if re.search(r"estimate|results/synth|docs/results\.md|yosys", ln, re.I):
                if synth_json:
                    continue
            offenders.append(f"{md.relative_to(REPO)}: {ln.strip()[:100]}")
    assert not offenders, "throughput stated without a synthesis estimate:\n" + "\n".join(offenders)
