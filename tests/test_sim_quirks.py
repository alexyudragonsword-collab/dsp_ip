"""Known simulator bugs, pinned per simulator version.

Each probe is a tiny .sv under tools/quirks/. CI runs it on both toolchains
(``$DSPIP_SIM_BIN``: distro Verilator 5.020 and the pinned OSS CAD Suite Verilator 5.053),
and the test asserts the behaviour each version is known to have: 5.020 folds
``longint >>> longint-localparam`` to 0, 5.053 gets it right. An unknown version must
match one of the two shapes; a version that has the bug is a reason to keep IPs off it
(ip.yaml ``sims:``), which no IP needs today (Halo_Serdes#142 emits ``localparam int``
shift amounts, which sidestep the fold).
"""
import re
import subprocess
from pathlib import Path

import pytest

from dspip import sims as S
from dspip.ipspec import IP_ROOT, all_ips

REPO = Path(__file__).resolve().parents[1]
QUIRK = REPO / "tools" / "quirks" / "verilator_longint_shift.sv"


def _run(sim, tmp_path):
    if sim == "verilator":
        obj = tmp_path / "obj"
        subprocess.run([S.exe("verilator"), "--binary", "--timing", "-Wno-WIDTH", "--top-module",
                        "t", "--Mdir", str(obj), str(QUIRK)], check=True, capture_output=True,
                       text=True)
        out = subprocess.run([str(obj / "Vt")], capture_output=True, text=True).stdout
    else:
        vvp = tmp_path / "q.vvp"
        subprocess.run([S.exe("iverilog"), "-g2012", "-o", str(vvp), str(QUIRK)], check=True,
                       capture_output=True, text=True)
        out = subprocess.run([S.exe("vvp"), "-n", str(vvp)], capture_output=True, text=True).stdout
    m = re.search(r"QUIRK a>>>SH_longint=(-?\d+) a>>>SH_int=(-?\d+) a>>SH_longint=(-?\d+) a>>>4=(-?\d+)", out)
    assert m, out
    return tuple(int(x) for x in m.groups())


RIGHT = 16384
# Verilator version -> value of `a >>> SH_longint` (the other three probes are always right)
VERILATOR_LONGINT_SHIFT = {"5.020": 0, "5.053": RIGHT}


@pytest.mark.skipif(not S.which("iverilog"), reason="no iverilog")
def test_iverilog_longint_shift_is_right(tmp_path):
    assert _run("iverilog", tmp_path) == (RIGHT,) * 4


@pytest.mark.skipif(not S.which("verilator"), reason="no verilator")
def test_verilator_longint_shift_per_version(tmp_path):
    got = _run("verilator", tmp_path)
    assert got[1:] == (RIGHT,) * 3, got
    banner = S.version("verilator") or ""
    m = re.match(r"Verilator (\d+\.\d+)", banner)
    assert m, banner
    if m.group(1) in VERILATOR_LONGINT_SHIFT:
        assert got[0] == VERILATOR_LONGINT_SHIFT[m.group(1)], (banner, got)
    else:  # a version not seen before: one of the two known shapes, record it above
        assert got[0] in (0, RIGHT), (banner, got)
    # Whether any IP trips over the fold is the lockstep job's call: it runs every IP on
    # 5.020 too, so a new `longint >>> longint-localparam` in RTL/tb shows up as a mismatch.


def test_sims_restriction_carries_a_reason():
    for s in all_ips(IP_ROOT):
        if set(s.sims) != {"verilator", "iverilog"}:
            assert s.extra.get("sims_reason"), f"{s.name}: ip.yaml sims: needs a sims_reason"
