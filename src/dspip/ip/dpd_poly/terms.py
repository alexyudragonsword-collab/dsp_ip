"""Basis term table for the polynomial DPD bases.

A term is ``x(n - x_delay) * prod_i |x(n - d_i)|^{k_i}`` — one signal factor and up to two
envelope factors. The table reproduces, column for column, the basis order of PA_DPD's
``DDRVolterraModel.basis_matrix`` (``pa/ddr.py``) and ``GMPModel.basis_matrix``
(``pa/gmp.py``) so the consumer's exported coefficient vector indexes it directly;
``tests/test_terms.py`` asserts this against the vendored upstream code.

Delays may be negative (GMP's *leading* envelope ``|x(n-m+l)|`` looks one sample into the
future). The datapath handles that by delaying everything by ``lead_of(terms)`` samples;
``line_index`` gives the non-negative history-window index each tap then uses.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Term:
    col: int
    x_delay: int
    env: tuple[tuple[int, int], ...]  # ((delay, k), ...) with k >= 1; () for the linear term

    @property
    def k_total(self) -> int:
        return sum(k for _, k in self.env)


def _env(*factors: tuple[int, int]) -> tuple[tuple[int, int], ...]:
    """Drop k == 0 factors (``a**0 == 1``) so the table carries only real multiplies."""
    return tuple((d, k) for d, k in factors if k > 0)


def ddr_terms(order: int = 5, memory_depth: int = 15, dynamic_order: int = 1) -> tuple[Term, ...]:
    """Column order of ``DDRVolterraModel.basis_matrix`` (PA_DPD pa/ddr.py:54-84)."""
    if dynamic_order != 1:
        raise NotImplementedError(
            "dynamic_order 2 has terms with three envelope factors; dpd_poly supports r <= 1")
    K, M = order, memory_depth
    terms: list[Term] = []
    for k in range(K):                       # r = 0 : x(n) a(n)^k
        terms.append(Term(len(terms), 0, _env((0, k))))
    for m in range(1, M + 1):                # r = 1
        for k in range(K):                   #   x(n-m) a(n)^k
            terms.append(Term(len(terms), m, _env((0, k))))
        for k in range(K - 1):               #   x(n) a(n-m) a(n)^k
            terms.append(Term(len(terms), 0, _env((m, 1), (0, k))))
    return tuple(terms)


def gmp_terms(order: int = 5, memory_depth: int = 15, lag_order: int = 4, lag_memory: int = 15,
              lag_span: int = 2, lead_order: int = 4, lead_memory: int = 15,
              lead_span: int = 1) -> tuple[Term, ...]:
    """Column order of ``GMPModel.basis_matrix`` (PA_DPD pa/gmp.py:49-69)."""
    terms: list[Term] = []
    for m in range(memory_depth):            # aligned: x(n-m) a(n-m)^k
        for k in range(order):
            terms.append(Term(len(terms), m, _env((m, k))))
    for m in range(lag_memory):              # lagging: x(n-m) a(n-m-l)^k
        for lag in range(1, lag_span + 1):
            for k in range(1, lag_order + 1):
                terms.append(Term(len(terms), m, _env((m + lag, k))))
    for m in range(lead_memory):             # leading: x(n-m) a(n-m+l)^k
        for lead in range(1, lead_span + 1):
            for k in range(1, lead_order + 1):
                terms.append(Term(len(terms), m, _env((m - lead, k))))
    return tuple(terms)


def terms_from_model(model_class: str, config: dict) -> tuple[Term, ...]:
    """Term table for the ``model_class``/``config`` fields of an exported coeffs JSON."""
    if model_class == "DDRVolterraModel":
        return ddr_terms(**config)
    if model_class == "GMPModel":
        return gmp_terms(**config)
    raise ValueError(f"unsupported model_class {model_class!r}")


def lead_of(terms: tuple[Term, ...]) -> int:
    """Samples of look-ahead the table needs (0 for DDR, 1 for GMP-510)."""
    delays = [t.x_delay for t in terms] + [d for t in terms for d, _ in t.env]
    return max(0, -min(delays))


def line_index(delay: int, lead: int) -> int:
    """History-window index of ``x(n - delay)`` once the pipeline runs ``lead`` samples late:
    index 0 is the newest sample in the window (= ``x(n + lead)``)."""
    idx = delay + lead
    if idx < 0:
        raise ValueError(f"delay {delay} exceeds lead {lead}")
    return idx


def depths(terms: tuple[Term, ...]) -> tuple[int, int, int]:
    """(lead, x_depth, env_depth): window lengths the datapath needs."""
    lead = lead_of(terms)
    xd = max(line_index(t.x_delay, lead) for t in terms) + 1
    ed = max([line_index(d, lead) for t in terms for d, _ in t.env] + [0]) + 1
    return lead, xd, ed


def max_k(terms: tuple[Term, ...]) -> int:
    return max([k for t in terms for _, k in t.env] + [0])


def basis_matrix_from_terms(x: np.ndarray, terms: tuple[Term, ...]) -> np.ndarray:
    """Float basis matrix built from the term table with the same zero-padded ``delayed``
    convention as upstream — the oracle ``tests/test_terms.py`` compares to upstream."""
    from dspip.vendor.padpd.pa.memory_polynomial import delayed

    x = np.asarray(x, dtype=complex)
    a = np.abs(x)
    cols = []
    for t in terms:
        c = delayed(x, t.x_delay).copy()
        for d, k in t.env:
            c = c * delayed(a, d) ** k
        cols.append(c)
    return np.stack(cols, axis=1)
