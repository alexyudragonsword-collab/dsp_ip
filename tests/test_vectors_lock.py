"""Rule 3 guards: the committed upstream export hashes what EXPORT.md says, every generated
vector set reproduces exactly what vectors.lock.json pins, and the re-export comparison
accepts LAPACK-level noise but nothing else."""

import importlib.util
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

from dspip import vectors as V
from dspip.ipspec import IP_ROOT, all_ips, load_ipspec

REPO = Path(__file__).resolve().parents[1]
UP = REPO / "ip" / "dpd_poly" / "upstream" / "DPA_160MHz"


def test_upstream_export_hashes():
    """Every committed upstream file is pinned by sha256 in the dpd_poly lock."""
    lock = V.load_lock(load_ipspec(IP_ROOT / "dpd_poly").lock_path)
    entry = lock.get("upstream", {})
    assert entry, "no 'upstream' entry in ip/dpd_poly/vectors/vectors.lock.json"
    actual = V.hash_dir(UP)
    for name, h in entry["files"].items():
        assert actual.get(name) == h, f"{name} changed since it was pinned"
    for name in actual:
        if name != "EXPORT.md":
            assert name in entry["files"], f"{name} not pinned"
    assert re.search(r"08b9725595748b290c76d1b70355f7e6014a709e", (UP / "EXPORT.md").read_text())


@pytest.mark.parametrize("ip", [s.name for s in all_ips(IP_ROOT)])
def test_vectors_lock_regenerates_identical(ip, tmp_path):
    spec = load_ipspec(IP_ROOT / ip)
    lock = V.load_lock(spec.lock_path)
    gen = spec.load_callable(spec.generator)
    for vs in spec.vector_sets:
        if vs.source != "generated":
            continue
        d = tmp_path / vs.name
        gen(vs.name, d)
        probs = V.verify_set(lock, vs.name, d)
        assert not probs, f"{ip}/{vs.name}: " + "; ".join(probs)
        assert lock["sets"][vs.name]["command"]


def test_committed_sets_are_tracked():
    """A `source: committed` set is only worth its lock if git carries the files: the
    .gitignore rule for generated sets must not swallow it (the milestone-2 pilot shipped
    its lock without its vectors for a day)."""
    import subprocess

    tracked = set(subprocess.run(["git", "ls-files", "ip"], capture_output=True, text=True,
                                 cwd=REPO, check=True).stdout.split())
    if not tracked:
        pytest.skip("not a git checkout")
    missing = []
    for spec in all_ips(IP_ROOT):
        lock = V.load_lock(spec.lock_path)
        for vs in spec.vector_sets:
            if vs.source != "committed":
                continue
            assert vs.name in lock["sets"], f"{spec.name}/{vs.name}: not in the lock"
            for name in lock["sets"][vs.name]["files"]:
                rel = (spec.root / vs.dir / name).relative_to(REPO).as_posix()
                if rel not in tracked:
                    missing.append(rel)
    assert not missing, "committed vector files not tracked by git (check .gitignore):\n" + "\n".join(missing)


@pytest.fixture(scope="module")
def chk():
    spec = importlib.util.spec_from_file_location(
        "check_upstream_export", REPO / "tools" / "check_upstream_export.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_upstream_export"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_reexport_comparison_policy(chk, tmp_path):
    a = json.loads((UP / "ddr_r1_w16_coeffs.json").read_text())
    b = json.loads(json.dumps(a))
    assert chk.compare_coeffs(a, b) == []
    b["coeffs_real"][3] += 1                       # LAPACK-level noise: accepted
    assert chk.compare_coeffs(a, b) == []
    b["coeffs_real"][3] += 1                       # 2 LSB: drift
    assert any("delta code" in p for p in chk.compare_coeffs(a, b))
    b = json.loads(json.dumps(a))
    b["coeff_scale_exp"] -= 1                      # exponent: exact
    assert any("coeff_scale_exp" in p for p in chk.compare_coeffs(a, b))
    v = np.loadtxt(UP / "ddr_r1_w16_refvec.csv", delimiter=",", skiprows=1)[:50]
    assert chk.compare_refvec(v, v.copy()) == []
    w = v.copy()
    w[0, 0] += 1e-12
    assert chk.compare_refvec(v, w) == ["i_in/q_in differ (must be exact)"]
    w = v.copy()
    w[0, 2] *= 1.01
    assert any("i_out/q_out" in p for p in chk.compare_refvec(v, w))
    # a whole-directory check against itself is clean
    assert chk.check_dir(UP, UP) == []
