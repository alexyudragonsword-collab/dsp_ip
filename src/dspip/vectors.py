"""Vector files and the hash lock.

Vector files follow Halo's convention: plain text, one decimal integer per line, read by the
testbench with ``$fscanf("%d")``. ``vectors.lock.json`` pins every file of every set by
sha256 (rule 3): generated sets are rebuilt by ``tools/lockstep.py`` and must hash the same;
committed sets must still hash the same.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


def write_ints(path: Path, values) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for v in values:
            f.write(f"{int(v)}\n")


def read_ints(path: Path) -> list[int]:
    out = []
    with open(path) as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                out.append(int(ln))
    return out


def read_ints_np(path: Path) -> np.ndarray:
    return np.array(read_ints(path), dtype=np.int64)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_dir(d: Path) -> dict[str, str]:
    """{relative file name: sha256} of every regular file in ``d`` (not recursive)."""
    return {p.name: sha256_file(p) for p in sorted(d.iterdir()) if p.is_file()}


def load_lock(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {"sets": {}}


def save_lock(path: Path, lock: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lock, indent=1, sort_keys=True) + "\n")


def verify_set(lock: dict, set_name: str, d: Path) -> list[str]:
    """Problems (empty = OK) comparing directory ``d`` with the lock entry."""
    entry = lock.get("sets", {}).get(set_name)
    if entry is None:
        return [f"{set_name}: not in lock"]
    actual = hash_dir(d)
    problems = []
    for name, h in entry["files"].items():
        if name not in actual:
            problems.append(f"{set_name}/{name}: missing")
        elif actual[name] != h:
            problems.append(f"{set_name}/{name}: sha256 {actual[name][:12]} != lock {h[:12]}")
    for name in actual:
        if name not in entry["files"] and not name.startswith("rtl_"):
            problems.append(f"{set_name}/{name}: not in lock")
    return problems


def lock_entry(d: Path, command: str) -> dict:
    return {"files": hash_dir(d), "command": command}
