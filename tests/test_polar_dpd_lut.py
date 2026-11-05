"""polar_dpd_lut: the reference side (rules 2 and 3).

* rule 3: the ROM images and the expected reads are polar_tx's export; the lookup of the ROM
  images reproduces the expected reads exactly;
* rule 2: the codes against the float LUT (polar_tx ``PolarDPD.predistort``, carried in the
  meta): within half an LSB in amplitude and phase. Widths are configuration: re-quantizing
  the float LUT at other widths shrinks the worst error by 2x per bit.
"""
from pathlib import Path

import numpy as np
import pytest

from dspip.ip.polar_dpd_lut.ref import load_set, probe, reference_outputs

REPO = Path(__file__).resolve().parents[1]
SET = REPO / "ip" / "polar_dpd_lut" / "vectors" / "wifi20"


@pytest.fixture(scope="module")
def s():
    return load_set(SET)


def test_lookup_reproduces_the_exported_reads(s):
    amp, ph = reference_outputs(SET)
    assert np.array_equal(amp, np.loadtxt(SET / "amp.txt", dtype=np.int64))
    assert np.array_equal(ph, np.loadtxt(SET / "ph.txt", dtype=np.int64))
    n = 1 << s["meta"]["addr_bits"]
    assert np.array_equal(s["addr"][:n], np.arange(n)) and s["addr"].size > 8 * n


def test_codes_vs_float_lut_within_half_lsb(s):
    """Measured: max amplitude error 0.50 LSB of 12 bits (1.2e-4 of full scale), max phase
    error 0.50 LSB of 14 bits (1.9e-4 rad)."""
    m = s["meta"]
    amp_f, ph_f = np.array(m["amp_float"]), np.array(m["ph_float_rad"])
    fs_a, half = (1 << m["amp_bits"]) - 1, 1 << (m["ph_bits"] - 1)
    assert np.max(np.abs(s["amp_rom"] / fs_a - amp_f)) <= 0.5 / fs_a + 1e-12
    assert np.max(np.abs(s["ph_rom"] * np.pi / half - ph_f)) <= 0.5 * np.pi / half + 1e-12
    # the LUT does work: a non-trivial inverse (not the identity) and a real AM-PM correction
    x = np.arange(amp_f.size) / (amp_f.size - 1)
    assert np.max(np.abs(amp_f - x)) > 0.02 and np.max(np.abs(ph_f)) > 0.01


@pytest.mark.parametrize("bits", [8, 10, 12, 14])
def test_width_sweep(s, bits):
    """Quantize the float LUT at other widths: worst error = half an LSB at every width."""
    m = s["meta"]
    amp_f, ph_f = np.array(m["amp_float"]), np.array(m["ph_float_rad"])
    fs_a, half = (1 << bits) - 1, 1 << (bits - 1)
    a = np.clip(np.rint(amp_f * fs_a), 0, fs_a) / fs_a
    p = np.clip(np.rint(ph_f / np.pi * half), -half, half - 1) * np.pi / half
    assert np.max(np.abs(a - amp_f)) <= 0.5 / fs_a + 1e-12
    assert np.max(np.abs(p - ph_f)) <= 0.5 * np.pi / half + 1e-12


def test_probe(s):
    assert "rom_amp[addr]=" in probe(SET, 300)
