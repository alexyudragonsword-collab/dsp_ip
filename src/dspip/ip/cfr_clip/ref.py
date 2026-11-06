"""Reference side of ``ip/cfr_clip``: polar_tx's ``cfr_clip_golden`` (vendored)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from dspip.vendor.polartx.rtl import cfr_clip_golden


def load_set(set_dir: Path) -> tuple[dict, np.ndarray]:
    meta = json.loads((Path(set_dir) / "cfr_meta.json").read_text())
    return meta, np.loadtxt(Path(set_dir) / "env.txt", dtype=np.int64)


def reference_outputs(set_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    meta, env = load_set(set_dir)
    return cfr_clip_golden(env, meta["threshold"]), (env > meta["threshold"]).astype(np.int64)


def probe(set_dir: Path, sample: int) -> str:
    meta, env = load_set(set_dir)
    e = int(env[sample])
    return f"env={e} threshold={meta['threshold']} -> {min(e, meta['threshold'])}"
