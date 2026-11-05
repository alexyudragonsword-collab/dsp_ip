"""dp_cal_lms: the reference side (rules 1-3).

* rule 3: the committed set is polar_tx's export, and the vendored polar_tx reference
  reproduces its value file from its input files exactly (so the golden file and the
  reference the RTL is held to are the same thing);
* rule 2: fixed against float, open loop on the recorded inputs, plus a width sweep;
  the closed-loop numbers (gain slewed out, EVM) are polar_tx's, recorded in the meta;
* the RTL's accumulator width argument (W + K + 1 bits) holds on saturating streams.
"""
import json
import re
from pathlib import Path

import numpy as np
import pytest

from dspip.ip.dp_cal_lms.floatref import float_trace, narrow_trace, tail
from dspip.ip.dp_cal_lms.ref import load_set, probe, reference_values
from dspip.vendor.polartx.dp_cal_fixed import DpCalFixedConfig, step_codes

REPO = Path(__file__).resolve().parents[1]
SET = REPO / "ip" / "dp_cal_lms" / "vectors" / "ble_5pct"


@pytest.fixture(scope="module")
def vec():
    cfg, v0, e, r = load_set(SET)
    golden = np.loadtxt(SET / "dp_cal_value.txt", dtype=np.int64)
    return cfg, v0, e, r, golden


SETS = ["ble_5pct", "ble_m5pct", "sat_top", "narrow"]


@pytest.mark.parametrize("name", SETS)
def test_vendored_reference_reproduces_the_committed_values(name):
    d = SET.parent / name
    golden = np.loadtxt(d / "dp_cal_value.txt", dtype=np.int64)
    assert golden.size > 100_000
    assert np.array_equal(reference_values(d), golden)


def test_sets_cover_both_directions_saturation_and_narrow_widths():
    """The four sets are not four copies: one slews down, one up, one sits on the value
    register's ceiling, one runs other widths and K through the same RTL."""
    cfgs = {n: load_set(SET.parent / n) for n in SETS}
    g = {n: np.loadtxt(SET.parent / n / "dp_cal_value.txt", dtype=np.int64) for n in SETS}
    assert g["ble_5pct"][-1] < cfgs["ble_5pct"][1] and g["ble_m5pct"][-1] > cfgs["ble_m5pct"][1]
    c, v0 = cfgs["sat_top"][0], cfgs["sat_top"][1]
    assert v0 == c.v_max and 0.1 < np.mean(g["sat_top"] == c.v_max) < 0.9
    n = cfgs["narrow"][0]
    assert (n.e_bits, n.reg_bits, n.k) != (cfgs["ble_5pct"][0].e_bits,
                                          cfgs["ble_5pct"][0].reg_bits, cfgs["ble_5pct"][0].k)


def test_dims_match_the_meta(vec):
    cfg, v0, e, _r, _g = vec
    dims = dict(re.findall(r"localparam int (\w+)\s*=\s*(-?\d+);",
                           (SET / "dp_cal_dims.svh").read_text()))
    assert {k: int(v) for k, v in dims.items()} == {
        "E_BITS": cfg.e_bits, "R_BITS": cfg.reg_bits, "K": cfg.k, "V_BITS": cfg.v_bits,
        "V_START": v0, "N_VEC": e.size}


def test_upstream_closed_loop_numbers_are_recorded():
    """The closed-loop rule-2 answer comes from polar_tx (measured: tail 0.99842, EVM
    3.178 %; float 0.99887 / 3.076 %); the meta must carry a converged, matched run."""
    meta = json.loads((SET / "dp_cal_meta.json").read_text())
    assert abs(meta["tail_mean"] - 1.0) < 0.01
    assert 2.5 < meta["evm_pct"] < 3.8
    assert meta["scenario"]["dp_gain"] == 1.05


def test_fixed_tracks_float_at_the_same_step(vec):
    """Same mu (2^-16) and ema (2^-10): only quantization separates the two.
    Measured: max |fixed - float| 4.4e-4 (29 LSB), tails 0.99842 vs 0.99862."""
    cfg, v0, e, r, golden = vec
    fx = golden / 2.0 ** cfg.v_frac
    fl = float_trace(e, r, cfg, v0 / 2.0 ** cfg.v_frac, mu=cfg.mu, ema=2.0 ** -cfg.k)
    assert np.abs(fx - fl).max() < 1e-3
    assert abs(tail(fx) - tail(fl)) < 5e-4


def test_width_sweep(vec):
    """Bit widths are configuration. Fewer phase-error bits move the open-loop trajectory
    further from float, monotonically (measured max deviation: 0 dropped 4.4e-4,
    2: 3.4e-3, 4: 1.7e-2, 6: 5.7e-2); the regressor barely matters to a sign-sign
    update (7 LSBs dropped, i.e. 5 bits at 64 kHz: 1.8e-3)."""
    cfg, v0, e, r, _g = vec
    fl = float_trace(e, r, cfg, v0 / 2.0 ** cfg.v_frac, mu=cfg.mu, ema=2.0 ** -cfg.k)
    dev = [np.abs(narrow_trace(e, r, cfg, v0, drop_e=d) - fl).max() for d in (0, 2, 4, 6)]
    assert all(a < b for a, b in zip(dev, dev[1:])), dev
    assert dev[0] < 1e-3
    assert np.abs(narrow_trace(e, r, cfg, v0, drop_r=7) - fl).max() < 3e-3


@pytest.mark.parametrize("w,k", [(10, 10), (12, 10), (4, 3), (8, 12)])
def test_accumulator_fits_w_plus_k_plus_1_bits(w, k):
    """dp_cal_lms.sv sizes each centering accumulator W + K + 1 bits on the claim
    |A| < 2^(W-1+K) + 2^K; drive both extremes, steps and alternation through it."""
    cfg = DpCalFixedConfig(e_bits=w, reg_bits=w, k=k)
    lo, hi = -(1 << (w - 1)), (1 << (w - 1)) - 1
    n = 40 << k
    rng = np.random.default_rng(w * 100 + k)
    streams = [np.full(n, lo), np.full(n, hi), np.r_[np.full(n // 2, hi), np.full(n // 2, lo)],
               np.where(np.arange(n) % 2, hi, lo), rng.integers(lo, hi + 1, n)]
    bound = (1 << (w - 1 + k)) + (1 << k)
    for x in streams:
        st = [0, 0, 0]
        worst = 0
        for v in x.tolist():
            step_codes(st, v, v, cfg)
            worst = max(worst, abs(st[1]), abs(st[2]))
        assert worst < bound and worst < (1 << (w + k))


def test_probe_reports_the_registers():
    out = probe(SET, 50_000)
    assert "before: V=" in out and "d_reg=" in out


def test_export_check_catches_a_changed_code(tmp_path):
    """tools/check_polartx_export.py (CI vendor-drift) is not vacuous: one changed value
    code or one changed float digit in the meta is reported."""
    import importlib.util
    import shutil

    spec = importlib.util.spec_from_file_location(
        "check_polartx_export", REPO / "tools" / "check_polartx_export.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fresh = tmp_path / "fresh"
    shutil.copytree(SET, fresh)
    assert mod.compare(fresh, SET) == []
    lines = (fresh / "dp_cal_value.txt").read_text().splitlines()
    lines[777] = str(int(lines[777]) + 1)
    (fresh / "dp_cal_value.txt").write_text("\n".join(lines) + "\n")
    meta = json.loads((fresh / "dp_cal_meta.json").read_text())
    meta["evm_pct"] *= 1.001
    (fresh / "dp_cal_meta.json").write_text(json.dumps(meta))
    probs = mod.compare(fresh, SET)
    assert any("dp_cal_value.txt" in p for p in probs) and any("evm_pct" in p for p in probs)
