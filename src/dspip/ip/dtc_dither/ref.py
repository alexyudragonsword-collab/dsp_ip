"""Reference side of ``ip/dtc_dither``: polar_tx's ``efm1_int_golden`` (vendored verbatim,
``dspip.vendor.polartx.rtl``) applied to a committed set's input words."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from dspip.vendor.polartx.rtl import efm1_int_golden


def load_set(set_dir: Path) -> tuple[int, int, np.ndarray]:
    meta = json.loads((Path(set_dir) / "dtc_meta.json").read_text())
    x = np.loadtxt(Path(set_dir) / "phase_w.txt", dtype=np.int64)
    return int(meta["n_bits"]), int(meta["frac_bits"]), x


def reference_codes(set_dir: Path) -> np.ndarray:
    n_bits, frac_bits, x = load_set(set_dir)
    return efm1_int_golden(x, n_bits, frac_bits)


def probe(set_dir: Path, sample: int) -> str:
    """The carried error before ``sample`` and the sum it forms."""
    n_bits, frac_bits, x = load_set(set_dir)
    mask = (1 << frac_bits) - 1
    err = 0
    for v in x[:sample].tolist():
        err = (v + err) & mask
    s = int(x[sample]) + err
    return (f"x={int(x[sample])} err_in={err} s={s} code={(s >> frac_bits) & ((1 << n_bits) - 1)} "
            f"err_out={s & mask}")
