"""Reference side of ``ip/polar_dpd_lut``: the lookup of the committed ROM images (polar_tx's
``quantize_dpd_luts`` codes, exported as ``dpd_amp.memh`` / ``dpd_ph.memh``)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def _memh(path: Path) -> np.ndarray:
    return np.array([int(ln, 16) for ln in Path(path).read_text().split()], dtype=np.int64)


def load_set(set_dir: Path) -> dict:
    d = Path(set_dir)
    meta = json.loads((d / "dpd_meta.json").read_text())
    ph_raw = _memh(d / "dpd_ph.memh")
    half = 1 << (meta["ph_bits"] - 1)
    ph = np.where(ph_raw >= half, ph_raw - 2 * half, ph_raw)        # two's complement
    return {"meta": meta, "amp_rom": _memh(d / "dpd_amp.memh"), "ph_rom": ph,
            "addr": np.loadtxt(d / "addr.txt", dtype=np.int64)}


def reference_outputs(set_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    s = load_set(set_dir)
    return s["amp_rom"][s["addr"]], s["ph_rom"][s["addr"]]


def probe(set_dir: Path, sample: int) -> str:
    s = load_set(set_dir)
    a = int(s["addr"][sample])
    return f"addr={a} rom_amp[addr]={int(s['amp_rom'][a])} rom_ph[addr]={int(s['ph_rom'][a])}"
