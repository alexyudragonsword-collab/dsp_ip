"""Rule 2 for ``dp_cal_lms``: the fixed-point reference against float, open loop.

The closed-loop answer (gain error slewed out, EVM) is polar_tx's to measure and is
recorded in the vector set's ``dp_cal_meta.json`` (fixed tail 0.99842 / EVM 3.178 %
against float 0.99887 / 3.076 %, polar_tx ``tests/test_dp_cal_fixed.py``). Here the
recorded input streams are replayed open loop through

* ``float_trace`` — the float sign-sign LMS update (polar_tx's vendored
  ``SignSignLMS``: means updated first, ``value += mu * sgn(e - m_e) * sgn(r - m_r)``),
  fed the de-quantized codes; ``mu`` / ``ema`` are arguments, so it runs both at the
  fixed point's nominal values (2^-16, 2^-10) and at the float calibrator's (2e-5, 1e-3);
* ``narrow_trace`` — the vendored integer reference with fewer input bits (the codes
  re-quantized by dropping LSBs, round half up), the bit-width sweep.
"""

from __future__ import annotations

import numpy as np

from dspip.vendor.polartx.dp_cal_fixed import DpCalFixedConfig, golden_trace


def float_trace(e_codes, r_codes, cfg: DpCalFixedConfig, v0: float, *, mu: float,
                ema: float) -> np.ndarray:
    e = np.asarray(e_codes, dtype=float) * 2.0 ** -cfg.e_frac
    r = np.asarray(r_codes, dtype=float) * cfg.reg_lsb_hz
    v, me, mr = float(v0), 0.0, 0.0
    out = np.empty(e.size)
    for i in range(e.size):
        mr += ema * (r[i] - mr)
        me += ema * (e[i] - me)
        v += mu * np.sign(e[i] - me) * np.sign(r[i] - mr)
        out[i] = v
    return out


def _drop(codes: np.ndarray, s: int) -> np.ndarray:
    return codes if s == 0 else (codes + (1 << (s - 1))) >> s


def narrow_trace(e_codes, r_codes, cfg: DpCalFixedConfig, v0: int, *, drop_e: int = 0,
                 drop_r: int = 0) -> np.ndarray:
    """Value trace (as gain) with ``drop_e`` / ``drop_r`` input LSBs removed."""
    c = DpCalFixedConfig(e_bits=cfg.e_bits - drop_e, e_frac=cfg.e_frac - drop_e,
                         reg_bits=cfg.reg_bits - drop_r,
                         reg_lsb_hz=cfg.reg_lsb_hz * 2 ** drop_r, k=cfg.k,
                         v_bits=cfg.v_bits, v_frac=cfg.v_frac)
    e = np.clip(_drop(np.asarray(e_codes, dtype=np.int64), drop_e),
                -(1 << (c.e_bits - 1)), (1 << (c.e_bits - 1)) - 1)
    r = np.clip(_drop(np.asarray(r_codes, dtype=np.int64), drop_r),
                -(1 << (c.reg_bits - 1)), (1 << (c.reg_bits - 1)) - 1)
    return golden_trace(e, r, v0, c) / 2.0 ** cfg.v_frac


def tail(trace) -> float:
    t = np.asarray(trace, dtype=float)
    return float(t[-t.size // 10:].mean())
