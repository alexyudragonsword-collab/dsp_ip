"""Reference side of ``ip/dp_cal_lms``.

The integer reference is polar_tx's ``cal/dp_cal_fixed.py``, vendored verbatim
(``dspip.vendor.polartx.dp_cal_fixed``); this module only reads a committed vector set
into it: the configuration from ``dp_cal_meta.json``, the input codes, and — for the
lockstep probe — the reference's registers at a given sample.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from dspip.vendor.polartx.dp_cal_fixed import DpCalFixedConfig, golden_trace, step_codes


def load_set(set_dir: Path) -> tuple[DpCalFixedConfig, int, np.ndarray, np.ndarray]:
    """(config, v_start, error codes, regressor codes) of a committed set."""
    meta = json.loads((Path(set_dir) / "dp_cal_meta.json").read_text())
    cfg = DpCalFixedConfig(**meta["config"])
    e = np.loadtxt(Path(set_dir) / "dp_cal_err.txt", dtype=np.int64)
    r = np.loadtxt(Path(set_dir) / "dp_cal_reg.txt", dtype=np.int64)
    return cfg, int(meta["v_start"]), e, r


def reference_values(set_dir: Path) -> np.ndarray:
    """The value-register trace the vendored reference computes from the set's inputs."""
    cfg, v0, e, r = load_set(set_dir)
    return golden_trace(e, r, v0, cfg)


def probe(set_dir: Path, sample: int) -> str:
    """Reference registers just before and after ``sample``."""
    cfg, v0, e, r = load_set(set_dir)
    st = [v0, 0, 0]
    for i in range(sample):
        step_codes(st, int(e[i]), int(r[i]), cfg)
    before = list(st)
    step_codes(st, int(e[sample]), int(r[sample]), cfg)
    k = cfg.k
    return (f"in: e={int(e[sample])} r={int(r[sample])}\n"
            f"before: V={before[0]} A_reg={before[1]} A_err={before[2]}\n"
            f"after:  V={st[0]} A_reg={st[1]} A_err={st[2]} "
            f"d_reg={(int(r[sample]) << k) - st[1]} d_err={(int(e[sample]) << k) - st[2]}")
