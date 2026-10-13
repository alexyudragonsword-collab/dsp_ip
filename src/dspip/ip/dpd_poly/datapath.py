"""Pure-integer datapath primitives of dpd_poly (shared by the reference and the config
derivation, so a scale exponent is computed by exactly the code that produces the value).

Every quantity is an unbounded Python ``int`` with an attached scale exponent ``exp``
(value = int · 2^exp). The RTL implements each function below with the widths the config
chose; ``ref.py`` strings them together per sample.
"""

from __future__ import annotations

import math

from dspip.fixed import rshift_round_py, saturate_py, saturate_u_py


def envelope(i: int, q: int, env_frac: int) -> int:
    """|x| as an unsigned integer with ``env_frac`` extra fractional bits:
    isqrt((I^2 + Q^2) << 2F). Truncating (floor) sqrt — the one deliberate deviation from
    upstream's float ``np.abs``; exp = e_in - env_frac."""
    return math.isqrt((i * i + q * q) << (2 * env_frac))


def envelope_max(w_in: int, env_frac: int) -> int:
    """Largest envelope a full-scale code pair can produce (both I and Q at -2^(W-1))."""
    full = 1 << (w_in - 1)
    return envelope(-full, -full, env_frac)


def power(a: int, k: int, q_k: int, w_pw: int) -> int:
    """pw_k = sat_u(w_pw, rshift_round(a^k, q_k)); exp = k·exp(a) + q_k."""
    return saturate_u_py(rshift_round_py(a ** k, q_k), w_pw)


def power_shift(a_max: int, k: int, w_pw: int) -> int:
    """q_k such that a_max^k >> q_k fits in ``w_pw`` unsigned bits."""
    return max(0, (a_max ** k).bit_length() - w_pw)


def pair_shift(pw0_max: int, pw1_max: int, w_pw: int) -> int:
    """q_pair such that pw0_max·pw1_max >> q_pair fits in ``w_pw`` unsigned bits."""
    return max(0, (pw0_max * pw1_max).bit_length() - w_pw)


def env_product(pw0: int, pw1: int, q_pair: int, w_pw: int) -> int:
    """Two envelope factors (DDR r=1 envelope terms): sat_u(w_pw, rshift_round(pw0·pw1, q_pair))."""
    return saturate_u_py(rshift_round_py(pw0 * pw1, q_pair), w_pw)


def term_phi(x_re: int, x_im: int, envp: int) -> tuple[int, int]:
    """phi = x · (envelope product); exp = e_in + exp(envp)."""
    return x_re * envp, x_im * envp


def quantize_phi(phi: int, s_c: int, w_phi: int) -> int:
    """code_phi = sat(w_phi, rshift_round(phi, s_c)); exp = exp(phi) + s_c = e_c."""
    return saturate_py(rshift_round_py(phi, s_c), w_phi)


def cmul(ar: int, ai: int, br: int, bi: int) -> tuple[int, int]:
    """Complex multiply, four real products (what the RTL instantiates)."""
    return ar * br - ai * bi, ar * bi + ai * br


def output(acc: int, s_out: int, w_out: int) -> int:
    """y = sat(w_out, rshift_round(acc, s_out))."""
    return saturate_py(rshift_round_py(acc, s_out), w_out)
