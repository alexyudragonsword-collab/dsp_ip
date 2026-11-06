"""cfr_clip, dtc_phase_acc, dpa_thermo_decode and polar_datapath: the reference side.

Rule 3: each committed set is polar_tx's export and the vendored goldens reproduce its outputs.
Rule 2: the integer outputs against the float quantities they stand for:

* CFR: the clip only touches samples above the threshold, and on the WiFi-20 burst it takes
  the envelope PAPR from 9.20 to 6.73 dB with 0.84 % of samples clipped;
* phase accumulator: exact modulo arithmetic, equal to the float phase sum;
* DPA decoder: unary + binary cell weights add back to the code, and adjacent codes switch at
  most one thermometer segment (no major-carry glitch in the unary part);
* datapath: the DPA code within -0.88..+0.12 LSB of the float predistorted amplitude (the
  bias -0.37 LSB is taking the top 10 of 12 bits) and the DTC code within +-1.04 LSB of the
  float phase minus the float AM-PM correction, mean -0.0006 LSB.
"""
from pathlib import Path

import numpy as np
import pytest

from dspip.ip.cfr_clip.ref import load_set as cfr_set, reference_outputs as cfr_ref
from dspip.ip.dpa_thermo_decode.ref import load_set as dec_set, reference_outputs as dec_ref
from dspip.ip.dtc_phase_acc.ref import load_set as acc_set, reference_phase
from dspip.ip.polar_datapath.ref import load_set as dp_set, probe as dp_probe, reference as dp_ref
from dspip.ip.polar_dpd_lut.ref import load_set as lut_set

REPO = Path(__file__).resolve().parents[1]
IP = REPO / "ip"
CFR = IP / "cfr_clip/vectors/mixed"
ACC = IP / "dtc_phase_acc/vectors/random"
DEC = IP / "dpa_thermo_decode/vectors/all_codes"
DP = IP / "polar_datapath/vectors/wifi20"


def _ints(p):
    return [int(v) for v in Path(p).read_text().split()]


def test_cfr_reproduces_and_reduces_papr():
    clip, flag = cfr_ref(CFR)
    assert np.array_equal(clip, _ints(CFR / "env_clip.txt"))
    assert np.array_equal(flag, _ints(CFR / "clipped.txt"))
    meta, env = cfr_set(CFR)
    keep = env <= meta["threshold"]
    assert np.array_equal(clip[keep], env[keep]) and clip.max() == meta["threshold"]
    burst, burst_clip = env[1024:].astype(float), clip[1024:].astype(float)

    def papr(x):
        return 10 * np.log10((x ** 2).max() / np.mean(x ** 2))

    assert papr(burst) - papr(burst_clip) > 2.0               # measured 9.20 -> 6.73 dB
    assert 0.002 < np.mean(burst > meta["threshold"]) < 0.02  # measured 0.84 %


def test_phase_acc_reproduces_and_equals_the_float_sum():
    phase = reference_phase(ACC)
    assert np.array_equal(phase, _ints(ACC / "phase.txt"))
    w, finc = acc_set(ACC)
    turns = np.cumsum(finc / 2.0 ** w) % 1.0                    # float64 is exact here
    assert np.array_equal(phase, np.rint(turns * 2 ** w).astype(np.int64) % (1 << w))


def test_thermo_decoder_reproduces_and_is_monotone():
    thermo, binw = dec_ref(DEC)
    assert thermo == _ints(DEC / "thermo.txt") and list(binw) == _ints(DEC / "bin.txt")
    meta, codes = dec_set(DEC)
    n_bin = meta["n_bits"] - meta["n_thermo"]
    weights = [bin(t).count("1") * (1 << n_bin) + int(b) for t, b in zip(thermo, binw)]
    assert weights == codes
    seg = [bin(t).count("1") for t in thermo]
    assert all(0 <= b - a <= 1 for a, b in zip(seg, seg[1:]))
    assert all((t & (t + 1)) == 0 for t in thermo)              # contiguous ones from bit 0


@pytest.fixture(scope="module")
def dp():
    return dp_set(DP), dp_ref(DP)


def test_datapath_reproduces(dp):
    _, g = dp
    assert g["thermo"] == _ints(DP / "thermo.txt")
    assert list(g["bin"]) == _ints(DP / "bin.txt")
    assert list(g["dtc_code"]) == _ints(DP / "dtc_code.txt")


def test_datapath_vs_float(dp):
    s, g = dp
    lut = lut_set(IP / "polar_dpd_lut/vectors/wifi20")
    # the datapath reads the same ROM the LUT IP checks, whose meta carries the float LUT
    assert np.array_equal(s["amp_rom"], lut["amp_rom"]) and np.array_equal(s["ph_rom"], lut["ph_rom"])
    amp_f = np.array(lut["meta"]["amp_float"])
    ph_f = np.array(lut["meta"]["ph_float_rad"])
    k = s["dims"]
    a = g["addr"]
    ideal_code = amp_f[a] * ((1 << k["AMP_BITS"]) - 1) / (1 << (k["AMP_BITS"] - k["DPA_BITS"]))
    e_amp = g["dpa_code"] - ideal_code
    assert -1.0 < e_amp.min() and e_amp.max() < 0.5             # measured -0.88 .. +0.12
    turns = g["acc"] / 2.0 ** k["ACC_W"] - ph_f[a] / (2 * np.pi)
    e_ph = g["dtc_code"] - turns * 2 ** k["DTC_BITS"]
    e_ph = (e_ph + 2 ** (k["DTC_BITS"] - 1)) % 2 ** k["DTC_BITS"] - 2 ** (k["DTC_BITS"] - 1)
    assert abs(e_ph.mean()) < 0.01 and np.abs(e_ph).max() < 1.1  # measured -0.0006, +-1.04
    # the correction is not idle: it moves the phase word on the burst
    assert np.mean(g["phase_w"] != g["acc"]) > 0.5


def test_datapath_widths_are_config(dp):
    """Narrower DPA code or DTC word: same chain, coarser outputs, errors grow by the LSB."""
    from dspip.vendor.polartx.rtl_vectors import datapath_golden

    s, g = dp
    g8 = datapath_golden(s["env"], s["finc"], s["amp_rom"], s["ph_rom"], dpa_bits=8, n_thermo=5,
                         dtc_bits=9)
    assert np.array_equal(g8["dpa_code"], g["dpa_code"] >> 2)
    assert np.array_equal(g8["acc"], g["acc"])
    assert g8["dtc_code"].max() < (1 << 9)


def test_probes():
    assert "dtc_code=" in dp_probe(DP, 4000)
