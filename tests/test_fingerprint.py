"""Rule 6 guard: tools/fingerprint.py compare catches a moved value anywhere in the tree,
lists raised entries, and record produces a stable digest of the reference outputs.
Adapted from Halo_Serdes@6e79c4a tests/test_fingerprint.py."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def fp():
    spec = importlib.util.spec_from_file_location("fingerprint", REPO / "tools" / "fingerprint.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_compare_finds_every_kind_of_difference(fp):
    a = {"dpd_poly": {"p": {"y_re": "abc", "n": 4}}, "sat_shift": {"x": ["1", "2"]}}
    assert fp.compare(a, json.loads(json.dumps(a))) == (3, [])
    b = {"dpd_poly": {"p": {"y_re": "abd", "n": 4, "new": "1"}}, "sat_shift": {"x": ["1", "3"]}}
    n, diffs = fp.compare(a, b)
    assert n == 4
    assert diffs == ["dpd_poly / p / new: None -> '1'",
                     "dpd_poly / p / y_re: 'abc' -> 'abd'",
                     "sat_shift / x: ['1', '2'] -> ['1', '3']"]


def test_compare_cli_exit_codes(fp, tmp_path, capsys):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps({"k": "1"}))
    b.write_text(json.dumps({"k": "1"}))
    assert fp.main(["compare", str(a), str(b)]) == 0
    b.write_text(json.dumps({"k": "2"}))
    assert fp.main(["compare", str(a), str(b)]) == 1
    assert "k: '1' -> '2'" in capsys.readouterr().out


def test_raised_entries_are_listed_not_hidden(fp, tmp_path, capsys):
    side = {"dpd_poly": {"p": {"error": "TypeError: bad call"}, "q": {"y_re": "0"}}}
    assert fp.raised(side) == ["dpd_poly / p: TypeError: bad call"]
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps(side))
    b.write_text(json.dumps(side))
    assert fp.main(["compare", str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "bit-identical" in out and "1 entries raised" in out and "TypeError" in out


def test_digest_is_dtype_and_order_sensitive(fp):
    assert fp.digest([1, 2, 3]) == fp.digest(np.array([1, 2, 3], dtype=np.int64))
    assert fp.digest([1, 2, 3]) != fp.digest([1, 3, 2])


def test_record_dpd_poly_is_deterministic(fp):
    a = fp.record_dpd_poly()
    b = fp.record_dpd_poly()
    assert fp.compare(a, b)[1] == [] and not fp.raised(a)
    assert a["ddr_r1/w16/pw16/f0"]["n"] == 4096
