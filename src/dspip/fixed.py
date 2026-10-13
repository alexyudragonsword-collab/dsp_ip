# Extracted from Halo_Serdes@6e79c4a: src/halo_serdes/core/fixed.py (rshift_round and
# saturate; the QFormat-based to_int/from_int/q_scale/q_limits are dropped, and pure-int
# scalar versions are added so the per-sample reference never touches numpy)
"""Fixed-point primitives with RTL-exact semantics.

Values live as integers scaled by 2^-exp; multiplies are integer multiplies and
rescaling is an arithmetic right shift whose rounding matches RTL:

- ``rounding="floor"``: plain arithmetic shift (Verilog ``>>>``);
- ``rounding="round"``: round-half-up via ``+2^(s-1)`` before the shift (the
  standard RTL rounding adder).

Saturation clips to the two's-complement range of ``wl`` bits. Two flavours:
the ``*_py`` functions are pure Python ints (unbounded, the truth), the
un-suffixed ones are numpy int64 vectorised (fast, must be proven identical).
"""

from __future__ import annotations

import numpy as np


def rshift_round(v: np.ndarray | int, shift: int, rounding: str = "round") -> np.ndarray:
    """Arithmetic right shift with RTL-matching rounding (vector int64).

    floor: v >> shift (arithmetic; numpy int64 >> is arithmetic).
    round: (v + 2^(shift-1)) >> shift (round-half-up, the RTL rounding adder).
    """
    v = np.asarray(v, dtype=np.int64)
    if shift <= 0:
        return v << (-shift)
    if rounding == "round":
        v = v + (np.int64(1) << (shift - 1))
    return v >> shift


def saturate(v: np.ndarray | int, wl: int) -> np.ndarray:
    lo = -(1 << (wl - 1))
    hi = (1 << (wl - 1)) - 1
    return np.clip(np.asarray(v, dtype=np.int64), lo, hi)


# --- pure-int scalar versions (dspip additions) ---------------------------------------


def rshift_round_py(v: int, shift: int, rounding: str = "round") -> int:
    """Scalar, unbounded-int twin of :func:`rshift_round`. Python ``>>`` on a
    negative int is an arithmetic (floor) shift, like SV ``>>>`` on a signed
    operand."""
    if shift <= 0:
        return v << (-shift)
    if rounding == "round":
        v = v + (1 << (shift - 1))
    return v >> shift


def saturate_py(v: int, wl: int) -> int:
    lo = -(1 << (wl - 1))
    hi = (1 << (wl - 1)) - 1
    return lo if v < lo else hi if v > hi else v


def saturate_u_py(v: int, wl: int) -> int:
    """Unsigned saturation to ``wl`` bits (envelope powers are unsigned)."""
    hi = (1 << wl) - 1
    return 0 if v < 0 else hi if v > hi else v


def bits_for_signed(v_max_abs: int) -> int:
    """Smallest signed word length that holds ±v_max_abs."""
    return int(v_max_abs).bit_length() + 1
