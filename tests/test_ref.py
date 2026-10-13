"""The integer reference: pure-int truth and int64 twin agree, streaming semantics equal
upstream's zero-padded delays, traces expose the probes, int64 overflow is refused."""

import numpy as np
import pytest

from dspip.ip.dpd_poly import datapath as dp
from dspip.ip.dpd_poly.config import DpdPolyConfig, quantize_input
from dspip.ip.dpd_poly.floatref import load_upstream
from dspip.ip.dpd_poly.ref import DpdPolyRef, _isqrt_vec


@pytest.fixture(scope="module", params=["ddr_r1", "gmp510"])
def setup(request):
    up = load_upstream(request.param, 16)
    cfg = DpdPolyConfig.derive(up.coeffs, up.x, basis=request.param)
    xi, xq = quantize_input(up.x[:600], cfg.e_in, cfg.w_in)
    return cfg, xi, xq


def test_ref_scalar_vs_vectorized(setup):
    cfg, xi, xq = setup
    ref = DpdPolyRef(cfg)
    r = ref.run(xi.tolist(), xq.tolist())
    vr, vi = ref.run_vec(xi, xq)
    assert len(r.y_re) == len(xi)
    assert np.array_equal(vr, np.array(r.y_re)) and np.array_equal(vi, np.array(r.y_im))


def test_streaming_lead_matches_block_semantics(setup):
    """Running the stream on two halves is NOT the same as one block (history resets),
    but one block of N equals the N-sample output: the lead/drain bookkeeping is right."""
    cfg, xi, xq = setup
    ref = DpdPolyRef(cfg)
    full = ref.run(xi.tolist(), xq.tolist())
    head = ref.run(xi[:300].tolist(), xq[:300].tolist())
    # samples that never see the block end (lead look-ahead) are identical
    n_same = 300 - cfg.lead
    assert full.y_re[:n_same] == head.y_re[:n_same]
    if cfg.lead:
        assert full.y_re[299] != head.y_re[299] or full.y_im[299] != head.y_im[299]


def test_trace_exposes_probes(setup):
    cfg, xi, xq = setup
    r = DpdPolyRef(cfg).run(xi[:40].tolist(), xq[:40].tolist(), trace_samples=[17])
    t = r.traces[17]
    assert t.n == 17 and len(t.code_re) == cfg.n_terms and len(t.pw) == cfg.max_k + 1
    # the accumulator the trace reports produces the reported output
    assert dp.output(t.acc_re, cfg.s_out, cfg.w_out) == t.y_re == r.y_re[17]
    assert t.a == dp.envelope(int(xi[17 + cfg.lead]) if 17 + cfg.lead < 40 else 0,
                              int(xq[17 + cfg.lead]) if 17 + cfg.lead < 40 else 0, 0)


def test_int64_ref_refuses_overflow():
    up = load_upstream("gmp510", 16)
    cfg = DpdPolyConfig.derive(up.coeffs, up.x, basis="gmp510", env_frac=4)
    assert not cfg.check_int64()
    with pytest.raises(OverflowError):
        DpdPolyRef(cfg).run_vec(np.zeros(4, np.int64), np.zeros(4, np.int64))
    # the pure-int reference has no such limit
    r = DpdPolyRef(cfg).run([1000, -2000, 30000], [0, 500, -30000])
    assert len(r.y_re) == 3


def test_isqrt_vec_exact():
    n = np.array([0, 1, 2, 3, 4, 15, 16, 17, 2**31, 2**31 - 1, 4294967295, 2**62 - 1, 2**62],
                 dtype=np.int64)
    r = _isqrt_vec(n)
    import math
    assert list(r) == [math.isqrt(int(v)) for v in n]


def test_output_saturates(setup):
    cfg, xi, xq = setup
    big = DpdPolyConfig.from_dict({**cfg.to_dict(), "w_out": 8})
    r = DpdPolyRef(big).run(xi[:50].tolist(), xq[:50].tolist())
    assert max(r.y_re) == 127 or min(r.y_re) == -128
