"""DpdPolyConfig: widths are configuration, exponents are consistent, dims round-trip."""

import json
import math

import numpy as np
import pytest

from dspip.ip.dpd_poly import datapath as dp
from dspip.ip.dpd_poly.config import DpdPolyConfig, ceil_log2_ratio, quantize_input
from dspip.ip.dpd_poly.floatref import UPSTREAM_DIR, load_upstream
from dspip.vendor.padpd.deploy.fixed_point import _pow2_step, quantize_symmetric
from dspip.vendor.padpd.pa.presets import ddr_volterra_default, gmp_opendpd_510


@pytest.fixture(scope="module")
def ddr16():
    return load_upstream("ddr_r1", 16)


@pytest.fixture(scope="module")
def cfg_ddr16(ddr16):
    return DpdPolyConfig.derive(ddr16.coeffs, ddr16.x, basis="ddr_r1")


def test_upstream_files_present():
    for b in ("ddr_r1", "gmp510"):
        for w in (16, 12):
            assert (UPSTREAM_DIR / f"{b}_w{w}_coeffs.json").exists()
            assert (UPSTREAM_DIR / f"{b}_w{w}_refvec.csv").exists()


@pytest.mark.parametrize("peak,qmax", [(1, 32767), (32767, 32767), (32768, 32767),
                                       (65534, 32767), (65535, 32767), (100, 2047), (5, 7)])
def test_ceil_log2_ratio_matches_float_rule(peak, qmax):
    assert ceil_log2_ratio(peak, qmax) == math.ceil(math.log2(peak / qmax))


def test_input_quantization_matches_upstream(ddr16):
    cfg = DpdPolyConfig.derive(ddr16.coeffs, ddr16.x, basis="ddr_r1")
    xi, xq = quantize_input(ddr16.x, cfg.e_in, cfg.w_in)
    xq_up = quantize_symmetric(ddr16.x, 16)
    assert np.array_equal(xi * 2.0 ** cfg.e_in + 1j * xq * 2.0 ** cfg.e_in, xq_up)
    assert cfg.e_in == int(math.log2(_pow2_step(
        max(abs(ddr16.x.real).max(), abs(ddr16.x.imag).max()), 16)))


@pytest.mark.parametrize("basis,factory", [("ddr_r1", ddr_volterra_default),
                                           ("gmp510", gmp_opendpd_510)])
def test_column_scales_match_upstream_pow2_step(basis, factory):
    """e_c chosen on the integer path equals upstream's per-column step on the float
    path (the two paths differ only by isqrt truncation / power pre-shift)."""
    up = load_upstream(basis, 16)
    cfg = DpdPolyConfig.derive(up.coeffs, up.x, basis=basis)
    phi = factory().basis_matrix(quantize_symmetric(up.x, 16))
    e_up = [int(math.log2(_pow2_step(max(abs(phi[:, c].real).max(), abs(phi[:, c].imag).max()),
                                     16))) for c in range(phi.shape[1])]
    diff = [c for c in range(len(e_up)) if e_up[c] != cfg.e_c[c]]
    assert not diff, f"{len(diff)} columns differ from upstream step, e.g. {diff[:5]}"


def test_exponent_bookkeeping_identities(cfg_ddr16):
    cfg = cfg_ddr16
    assert cfg.exp_a == cfg.e_in                       # F = 0
    for t in cfg.terms:
        if len(t.env) == 1:
            k = t.env[0][1]
            assert cfg.exp_phi(t) == (k + 1) * cfg.e_in + cfg.q_k[k - 1]
        elif not t.env:
            assert cfg.exp_phi(t) == cfg.e_in
        assert cfg.e_c[t.col] == cfg.exp_phi(t) + cfg.s_c[t.col]
        assert cfg.al_c[t.col] == cfg.e_c[t.col] - cfg.e_min >= 0
        assert cfg.s_c[t.col] >= 0
    assert cfg.s_out == cfg.e_out - (cfg.e_w + cfg.e_min) >= 0
    assert cfg.w_acc <= 63 and cfg.check_int64()


def test_bitwidth_is_config(ddr16):
    """Changing a width changes the derived datapath and the emitted dims — nothing is
    a hard-coded constant."""
    a = DpdPolyConfig.derive(ddr16.coeffs, ddr16.x, basis="ddr_r1")
    b = DpdPolyConfig.derive(ddr16.coeffs, ddr16.x, basis="ddr_r1", w_pw=20, env_frac=2,
                             w_phi=18)
    assert (a.w_pw, a.env_frac, a.w_phi) == (16, 0, 16)
    assert (b.w_pw, b.env_frac, b.w_phi) == (20, 2, 18)
    assert b.q_k != a.q_k and b.s_c != a.s_c and b.w_acc != a.w_acc
    assert "W_PW      = 20" in b.to_svh(10) and "W_PW      = 16" in a.to_svh(10)
    assert "ENV_FRAC  = 2" in b.to_svh(10)


def test_w12_export_gives_w12_config():
    up = load_upstream("gmp510", 12)
    cfg = DpdPolyConfig.derive(up.coeffs, up.x, basis="gmp510")
    assert cfg.w_in == cfg.w_coef == cfg.w_phi == cfg.w_out == 12
    assert max(max(map(abs, cfg.coef_re)), max(map(abs, cfg.coef_im))) <= 2048


def test_negative_column_shift_is_clamped():
    """A column whose peak needs fewer than w_phi bits would get s_c < 0; the config
    clamps it to 0 (no left shift in RTL) and moves e_c accordingly."""
    coeffs = {"model_class": "GMPModel", "w_bits": 16, "coeff_scale_exp": -13,
              "config": {"order": 2, "memory_depth": 2, "lag_order": 0, "lag_memory": 0,
                         "lag_span": 0, "lead_order": 0, "lead_memory": 0, "lead_span": 0},
              "coeffs_real": [1000, 0, 0, 0], "coeffs_imag": [0, 0, 0, 0]}
    x = np.array([0.01 + 0.0j, -0.02 + 0.01j, 0.005j, 0.0, 0.0])   # tiny vs full scale
    cfg = DpdPolyConfig.derive(coeffs, x, basis="t", w_phi=24)   # w_phi > what x·a needs
    assert any(cfg.s_c[t.col] == 0 and cfg.e_c[t.col] == cfg.exp_phi(t) for t in cfg.terms)
    assert all(s >= 0 for s in cfg.s_c)


def test_pair_shift_tracks_actual_product_bound():
    a_max = dp.envelope_max(16, 0)
    pw1 = dp.power(a_max, 1, dp.power_shift(a_max, 1, 24), 24)
    pw3 = dp.power(a_max, 3, dp.power_shift(a_max, 3, 24), 24)
    assert pw1.bit_length() == 16                       # pw_1 does not fill 24 bits
    q = dp.pair_shift(pw1, pw3, 24)
    assert (pw1 * pw3) >> q < (1 << 24) and (pw1 * pw3) >> (q - 1) >= (1 << 24)


def test_json_round_trip_and_svh(cfg_ddr16, tmp_path):
    cfg = cfg_ddr16
    assert DpdPolyConfig.from_json(cfg.to_json()) == cfg
    json.loads(cfg.to_json())
    svh = cfg.to_svh(4096)
    assert "localparam int N_TERMS   = 140;" in svh
    assert "localparam int N_SAMPLES = 4096;" in svh
    assert "localparam logic [1119:0] T_SH" in svh  # 140 * 8 - 1
    assert "localparam int" in svh and "'{" not in svh   # no unpacked-array localparams


def test_coefficient_count_mismatch_rejected(ddr16):
    bad = dict(ddr16.coeffs)
    bad["coeffs_real"] = bad["coeffs_real"][:-1]
    with pytest.raises(ValueError):
        DpdPolyConfig.derive(bad, ddr16.x)
