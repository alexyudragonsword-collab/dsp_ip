"""Reference side of ``ip/polar_datapath``: polar_tx's ``datapath_golden`` (vendored, in
``dspip.vendor.polartx.rtl_vectors``) on a committed set's inputs and ROM images."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from dspip.vendor.polartx.rtl_vectors import datapath_golden


def _memh(path: Path) -> np.ndarray:
    return np.array([int(v, 16) for v in Path(path).read_text().split()], dtype=np.int64)


def load_set(set_dir: Path) -> dict:
    d = Path(set_dir)
    dims = {k: int(v) for k, v in re.findall(r"localparam int (\w+)\s*=\s*(-?\d+);",
                                             (d / "datapath_dims.svh").read_text())}
    ph = _memh(d / "dpd_ph.memh")
    half = 1 << (dims["PH_BITS"] - 1)
    return {"dims": dims, "meta": json.loads((d / "datapath_meta.json").read_text()),
            "env": np.loadtxt(d / "env.txt", dtype=np.int64),
            "finc": np.loadtxt(d / "finc.txt", dtype=np.int64),
            "amp_rom": _memh(d / "dpd_amp.memh"), "ph_rom": np.where(ph >= half, ph - 2 * half, ph)}


def reference(set_dir: Path) -> dict:
    s = load_set(set_dir)
    k = s["dims"]
    return datapath_golden(s["env"], s["finc"], s["amp_rom"], s["ph_rom"],
                           threshold=k["THRESHOLD"], env_bits=k["ENV_BITS"],
                           addr_bits=k["ADDR_BITS"], amp_bits=k["AMP_BITS"],
                           dpa_bits=k["DPA_BITS"], n_thermo=k["N_THERMO"], ph_bits=k["PH_BITS"],
                           acc_w=k["ACC_W"], dtc_bits=k["DTC_BITS"])


def probe(set_dir: Path, sample: int) -> str:
    g = reference(set_dir)
    keys = ("env_clip", "addr", "dpa_code", "acc", "phase_w", "dtc_code")
    return "  ".join(f"{k}={int(g[k][sample])}" for k in keys)
