"""Reference side of ``ip/dtc_phase_acc``: polar_tx's ``phase_acc_golden`` (vendored)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from dspip.vendor.polartx.rtl import phase_acc_golden


def load_set(set_dir: Path) -> tuple[int, np.ndarray]:
    meta = json.loads((Path(set_dir) / "acc_meta.json").read_text())
    return int(meta["w"]), np.loadtxt(Path(set_dir) / "finc.txt", dtype=np.int64)


def reference_phase(set_dir: Path) -> np.ndarray:
    w, finc = load_set(set_dir)
    return phase_acc_golden(finc, w)


def probe(set_dir: Path, sample: int) -> str:
    w, finc = load_set(set_dir)
    acc = phase_acc_golden(finc[: sample + 1], w)
    prev = int(acc[-2]) if sample else 0
    return f"acc_in={prev} finc={int(finc[sample])} acc_out={int(acc[-1])} (mod 2^{w})"
