"""dtc_dither: the reference side (rules 1-3).

* rule 3: the committed sets are polar_tx's export, and the vendored ``efm1_int_golden``
  reproduces their code files from their phase words;
* rule 2: the dither against the float phase it quantizes. EFM1 exists to make the code's
  time average exact and to push the quantization error out of band: on the phase-ramp set,
  compared with plain truncation of the same words, the mean error goes to ~0 and the
  low-frequency error (64-sample moving average) drops by an order of magnitude. The fraction
  width is configuration: the sweep re-quantizes the same ideal ramp at other widths.
"""
import json
from pathlib import Path

import numpy as np
import pytest

from dspip.ip.dtc_dither.ref import load_set, probe, reference_codes
from dspip.vendor.polartx.rtl import efm1_int_golden

REPO = Path(__file__).resolve().parents[1]
VEC = REPO / "ip" / "dtc_dither" / "vectors"


@pytest.mark.parametrize("name", ["random", "ramp"])
def test_vendored_reference_reproduces_the_committed_codes(name):
    golden = np.loadtxt(VEC / name / "code.txt", dtype=np.int64)
    assert golden.size >= 2048
    assert np.array_equal(reference_codes(VEC / name), golden)


def _errors(x, code, n_bits, frac_bits):
    """Code minus ideal phase in code LSB, with the modulo-2^n wrap undone sample by sample."""
    ideal = x / (1 << frac_bits)
    e = code - ideal
    m = 1 << n_bits
    return (e + m / 2) % m - m / 2


def _lowpass(e, n=64):
    return np.convolve(e, np.ones(n) / n, mode="valid")


def test_efm1_vs_truncation_on_the_ramp():
    """Measured on the committed ramp (4096 words, 11-bit code): EFM1 mean error 0.000 LSB vs
    truncation -0.498; 64-sample moving-average rms 0.0065 vs 0.499 LSB."""
    n_bits, frac_bits, x = load_set(VEC / "ramp")
    code = np.loadtxt(VEC / "ramp" / "code.txt", dtype=np.int64)
    trunc = (x >> frac_bits) & ((1 << n_bits) - 1)
    e_d = _errors(x, code, n_bits, frac_bits)
    e_t = _errors(x, trunc, n_bits, frac_bits)
    assert abs(e_d.mean()) < 0.01 and abs(e_t.mean() + 0.5) < 0.05
    lp_d, lp_t = np.sqrt(np.mean(_lowpass(e_d) ** 2)), np.sqrt(np.mean(_lowpass(e_t) ** 2))
    assert lp_d < 0.05 and lp_t > 10 * lp_d
    assert np.abs(e_d).max() < 1.0 + 1e-9          # never more than one code from the ideal


@pytest.mark.parametrize("frac_bits", [2, 4, 8, 12])
def test_frac_width_sweep(frac_bits):
    """Fraction width is configuration: the same ideal ramp (the committed set's frequency
    word, as a fraction of a code) re-quantized at other widths. The in-band error stays
    small at every width; with too few fraction bits the residual frequency error of the
    quantized word itself shows up (bounded by 2^-frac per sample)."""
    meta = json.loads((VEC / "ramp" / "dtc_meta.json").read_text())
    n_bits = meta["n_bits"]
    fcw = 0.0123456789 * (1 << n_bits)                 # codes per sample (polar_tx DTC_RAMP_FCW)
    w = n_bits + frac_bits
    finc = int(round(fcw * (1 << frac_bits)))
    x = (np.arange(1, 4097, dtype=np.int64) * finc) & ((1 << w) - 1)
    code = efm1_int_golden(x, n_bits, frac_bits)
    e = _errors(x, code, n_bits, frac_bits)
    assert abs(e.mean()) < 0.02
    assert np.sqrt(np.mean(_lowpass(e) ** 2)) < 0.05
    # against the unquantized ramp: drift bounded by the word's own rounding of fcw
    ideal = (np.arange(1, 4097) * fcw) % (1 << n_bits)
    drift = (code - ideal + (1 << n_bits) / 2) % (1 << n_bits) - (1 << n_bits) / 2
    assert np.abs(drift).max() < 1.0 + 4096 * 2.0 ** -(frac_bits + 1) + 1e-9


def test_probe_reports_the_error_register():
    assert "err_in=" in probe(VEC / "ramp", 1000)
