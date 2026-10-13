"""Rule 2/3 guard: the term table reproduces PA_DPD's basis column order exactly."""

import numpy as np
import pytest

from dspip.ip.dpd_poly import terms as T
from dspip.vendor.padpd.pa.presets import ddr_volterra_default, gmp_opendpd_510


@pytest.mark.parametrize("basis", ["ddr", "gmp"])
def test_terms_match_upstream_basis(basis):
    rng = np.random.default_rng(7)
    x = rng.standard_normal(400) + 1j * rng.standard_normal(400)
    if basis == "ddr":
        model, tbl = ddr_volterra_default(), T.ddr_terms(5, 15, 1)
        assert len(tbl) == 140
    else:
        model, tbl = gmp_opendpd_510(), T.gmp_terms(5, 15, 4, 15, 2, 4, 15, 1)
        assert len(tbl) == 255
    phi_up = model.basis_matrix(x)
    phi_tb = T.basis_matrix_from_terms(x, tbl)
    assert phi_up.shape == phi_tb.shape
    assert np.array_equal(phi_up, phi_tb)   # column for column, bit for bit in float
    assert [t.col for t in tbl] == list(range(len(tbl)))


def test_ddr_two_factor_columns_present():
    tbl = T.ddr_terms(5, 15, 1)
    two = [t for t in tbl if len(t.env) == 2]
    assert len(two) == 15 * 3           # m=1..15, k=1..3 (k=0 collapses to one factor)
    assert all(t.x_delay == 0 for t in two)
    assert T.max_k(tbl) == 4 and T.lead_of(tbl) == 0 and T.depths(tbl) == (0, 16, 16)


def test_gmp_lead_and_depths():
    tbl = T.gmp_terms()
    assert T.lead_of(tbl) == 1
    lead, xd, ed = T.depths(tbl)
    assert (lead, xd, ed) == (1, 16, 18)       # lag env delay up to 14+2 -> idx 17
    leads = [t for t in tbl if any(d < 0 for d, _ in t.env)]
    assert len(leads) == 4                     # only m=0 of the leading block looks ahead
    assert all(T.line_index(d, lead) == 0 for t in leads for d, _ in t.env)


def test_terms_from_model_and_unsupported():
    assert len(T.terms_from_model("GMPModel", gmp_opendpd_510().get_config())) == 255
    with pytest.raises(NotImplementedError):
        T.ddr_terms(5, 3, 2)
    with pytest.raises(ValueError):
        T.terms_from_model("MemoryPolynomialModel", {})
    with pytest.raises(ValueError):
        T.line_index(-2, 1)
