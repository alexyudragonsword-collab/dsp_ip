"""Rule 3 guard: the vendored tree matches pinned upstream (tools/vendor_check.py).

Skips the sibling-dependent checks when PA_DPD is not checked out next to this
repo; the ``vendor-drift`` CI job checks it out at the pinned SHA and passes
``--strict`` so that there, a skip is red. Adapted from Halo_Serdes@6e79c4a
tests/test_vendor_check.py.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "vendor_check", REPO / "tools" / "vendor_check.py")
vc = importlib.util.module_from_spec(_spec)
sys.modules["vendor_check"] = vc
_spec.loader.exec_module(vc)


def _siblings():
    return vc.Siblings({})


def _have(sib):
    return sib.path("PA_DPD") is not None


def test_vendor_no_drift():
    sib = _siblings()
    if not _have(sib):
        pytest.skip("sibling repo PA_DPD not present")
    manifest = vc.json.loads(vc.MANIFEST.read_text())
    results = vc.check(sib, manifest)
    drift = [r for r in results if r.status == "DRIFT"]
    assert not drift, "vendor drift:\n" + "\n".join(f"  {r.rel}: {r.detail}" for r in drift)
    assert len(results) >= 12  # the padpd files; non-vacuous


def test_every_vendored_file_has_header():
    """Every vendored .py (bar __init__) and every attributed .sv carries the
    header — needs no sibling checkout."""
    bad = []
    for f in vc.vendored_files():
        first = f.read_text().splitlines()[0]
        if not vc.HEADER.match(first):
            bad.append(str(f.relative_to(REPO)))
    assert not bad, "vendored files missing attribution header: " + ", ".join(bad)
    py = [f for f in vc.vendored_files() if f.suffix == ".py"]
    assert len(py) >= 12


def test_header_regex_accepts_sv_comment_prefix():
    m = vc.HEADER.match("// Vendored from Halo_Serdes@6e79c4a: rtl/ffe_dfe_datapath.sv")
    assert m and m["cmt"] == "//" and m["repo"] == "Halo_Serdes" and m["sha"] == "6e79c4a"
    assert vc._strip_header(["// Vendored from X@1: a.sv", "// policy", "module m;"], "//") == "module m;"


def test_manifest_files_exist():
    declared = vc.json.loads(vc.MANIFEST.read_text()).get("files", {})
    missing = [rel for rel in declared
               if not (REPO / "src/dspip/vendor" / rel).exists() and not (REPO / rel).exists()]
    assert not missing, "stale manifest entries: " + ", ".join(missing)


def test_vendor_detects_injected_drift():
    """A non-import edit to a verbatim file is reported as DRIFT."""
    sib = _siblings()
    if not _have(sib):
        pytest.skip("sibling repo PA_DPD not present")
    target = REPO / "src/dspip/vendor/padpd/pa/gmp.py"
    original = target.read_text()
    try:
        target.write_text(original + "\nINJECTED_DRIFT = 1\n")
        results = vc.check(sib, vc.json.loads(vc.MANIFEST.read_text()))
        drift = [r for r in results if r.status == "DRIFT"]
        assert any("gmp.py" in r.rel for r in drift)
    finally:
        target.write_text(original)
