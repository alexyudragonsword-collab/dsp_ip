"""dspip.fixed: RTL-exact rounding/saturation semantics, numpy and pure-int twins agree."""

import numpy as np
import pytest

from dspip import fixed


@pytest.mark.parametrize("v,shift,expect", [
    (5, 1, 3),      # 2.5 -> 3 (half-up)
    (-5, 1, -2),    # -2.5 -> -2 (half-up, i.e. toward +inf on ties)
    (-6, 2, -1),    # -1.5 -> -1
    (7, 2, 2),      # 1.75 -> 2
    (-7, 2, -2),    # -1.75 -> -2
    (3, 0, 3),
    (3, -2, 12),    # non-positive shift = left shift
])
def test_rshift_round_half_up(v, shift, expect):
    assert fixed.rshift_round_py(v, shift) == expect
    assert int(fixed.rshift_round(np.int64(v), shift)) == expect


def test_rshift_floor_is_arithmetic():
    assert fixed.rshift_round_py(-5, 1, "floor") == -3
    assert int(fixed.rshift_round(np.int64(-5), 1, "floor")) == -3


def test_saturate_both_ends():
    assert fixed.saturate_py(40000, 16) == 32767
    assert fixed.saturate_py(-40000, 16) == -32768
    assert fixed.saturate_py(-32768, 16) == -32768
    assert list(fixed.saturate(np.array([40000, -40000, 5]), 16)) == [32767, -32768, 5]
    assert fixed.saturate_u_py(70000, 16) == 65535 and fixed.saturate_u_py(-1, 16) == 0


def test_twins_agree_on_random_values():
    rng = np.random.default_rng(1)
    v = rng.integers(-(1 << 40), 1 << 40, size=2000)
    for s in (0, 1, 3, 17):
        a = fixed.rshift_round(v, s)
        b = np.array([fixed.rshift_round_py(int(x), s) for x in v])
        assert np.array_equal(a, b)


def test_bits_for_signed():
    assert fixed.bits_for_signed(32767) == 16 and fixed.bits_for_signed(32768) == 17
