"""Reference side of ``ip/dpa_thermo_decode``: polar_tx's ``thermo_decode_golden`` (vendored)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from dspip.vendor.polartx.rtl import thermo_decode_golden


def load_set(set_dir: Path) -> tuple[dict, list[int]]:
    meta = json.loads((Path(set_dir) / "thermo_meta.json").read_text())
    codes = [int(v) for v in (Path(set_dir) / "code.txt").read_text().split()]
    return meta, codes


def reference_outputs(set_dir: Path) -> tuple[list[int], np.ndarray]:
    meta, codes = load_set(set_dir)
    g = thermo_decode_golden(meta["n_bits"], meta["n_thermo"])
    return [g["thermo_int"][c] for c in codes], g["bin"][codes]


def probe(set_dir: Path, sample: int) -> str:
    meta, codes = load_set(set_dir)
    c = codes[sample]
    n_bin = meta["n_bits"] - meta["n_thermo"]
    return f"code={c} sel={c >> n_bin} -> {c >> n_bin} thermometer bits set, bin={c & ((1 << n_bin) - 1)}"
