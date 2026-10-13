"""Rule 2: the fixed-point reference answers to floating point (dpd_poly).

- the vendored upstream fixed-point emulation reproduces the export's i_out/q_out;
- the integer reference tracks it to a documented NMSE at every bit width;
- with torch + the OpenDPD dataset + the PA_DPD checkout, PA_DPD's four ACLR numbers are
  reproduced (|Δ| <= 0.1 dB) with upstream's own code, and the integer reference's ACLR is
  within the acceptance of the upstream W16 numbers. Set DSPIP_REQUIRE_TORCH=1 to turn the
  skip into a failure (the fixed-vs-float CI job does).
"""

import json
import os

import numpy as np
import pytest

from dspip.ip.dpd_poly import floatref as fr
from dspip.ip.dpd_poly.config import DpdPolyConfig

# integer reference vs upstream float emulation on the exported block, NMSE must be below:
NMSE_BOUND_DB = {16: -55.0, 12: -33.0}


@pytest.mark.parametrize("basis", ["ddr_r1", "gmp510"])
@pytest.mark.parametrize("w", [16, 12])
def test_vendored_upstream_reproduces_export(basis, w):
    up = fr.load_upstream(basis, w)
    y = fr.upstream_fixed_output(up.coeffs, up.x)
    assert np.abs(y - up.y_upstream).max() / np.abs(up.y_upstream).max() < 1e-9


@pytest.mark.parametrize("basis", ["ddr_r1", "gmp510"])
@pytest.mark.parametrize("w", [16, 12])
def test_ref_vs_upstream_float_nmse(basis, w):
    up = fr.load_upstream(basis, w)
    cfg = DpdPolyConfig.derive(up.coeffs, up.x, basis=basis)
    y = fr.int_ref_output(cfg, up.x)
    n = fr.nmse_db(up.y_upstream, y)
    assert n < NMSE_BOUND_DB[w], f"{basis} W{w}: NMSE {n:.1f} dB"


def test_wider_power_word_does_not_hurt():
    up = fr.load_upstream("ddr_r1", 16)
    base = fr.nmse_db(up.y_upstream, fr.int_ref_output(
        DpdPolyConfig.derive(up.coeffs, up.x, basis="ddr_r1"), up.x))
    wide = fr.nmse_db(up.y_upstream, fr.int_ref_output(
        DpdPolyConfig.derive(up.coeffs, up.x, basis="ddr_r1", w_pw=24), up.x))
    assert wide <= base + 0.5


def _surrogate_or_skip():
    if not fr.surrogate_available():
        if os.environ.get("DSPIP_REQUIRE_TORCH"):
            pytest.fail("DSPIP_REQUIRE_TORCH set but torch / dataset / PA_DPD checkout missing")
        pytest.skip("torch, OpenDPD dataset or PA_DPD checkout not available")


@pytest.fixture(scope="module")
def table():
    """The ACLR table as produced by examples/01_bitwidth_aclr.py (results/aclr_table.json)
    — recomputed here if absent so the test never trusts a stale file blindly."""
    _surrogate_or_skip()
    path = fr.REPO / "results" / "aclr_table.json"
    if path.exists():
        return json.loads(path.read_text())
    return fr.build_aclr_table()


@pytest.mark.parametrize("basis", ["ddr_r1", "gmp510"])
def test_aclr_table_reproduced(table, basis):
    """PA_DPD docs/03_roadmap.md numbers, recomputed with upstream's own code."""
    row = table[basis]["upstream_recomputed"]
    for key, doc in fr.UPSTREAM_TABLE[basis].items():
        got = row[str(key)]
        assert abs(got - doc) <= 0.1, f"{basis} {key}: recomputed {got:.2f} vs doc {doc}"


@pytest.mark.parametrize("basis", ["ddr_r1", "gmp510"])
def test_int_ref_aclr_at_w16_matches_upstream(table, basis):
    """The integer datapath at W16 is within 0.1 dB ACLR of upstream's W16 number."""
    got = table[basis]["int_ref"]["16"]["default"]
    assert abs(got - fr.UPSTREAM_TABLE[basis][16]) <= 0.1, f"{basis}: {got:.2f}"
