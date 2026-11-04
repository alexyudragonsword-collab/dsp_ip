"""Known simulator bugs that an ip.yaml ``sims:`` restriction works around (none right
now: the one IP that hit this bug was fixed upstream, Halo_Serdes#142; Verilator 5.053
fixes the bug itself; the probe stays to track the installed Verilator).

Each probe is a tiny .sv under tools/quirks/. The test pins the bug's *current* behaviour
on the installed simulator: when a newer simulator fixes it, the test fails with the IPs
whose restriction can now be lifted — so a workaround never outlives its reason.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from dspip.ipspec import IP_ROOT, all_ips

REPO = Path(__file__).resolve().parents[1]
QUIRK = REPO / "tools" / "quirks" / "verilator_longint_shift.sv"


def _run(sim, tmp_path):
    if sim == "verilator":
        obj = tmp_path / "obj"
        subprocess.run(["verilator", "--binary", "--timing", "-Wno-WIDTH", "--top-module", "t",
                        "--Mdir", str(obj), str(QUIRK)], check=True, capture_output=True, text=True)
        out = subprocess.run([str(obj / "Vt")], capture_output=True, text=True).stdout
    else:
        vvp = tmp_path / "q.vvp"
        subprocess.run(["iverilog", "-g2012", "-o", str(vvp), str(QUIRK)], check=True,
                       capture_output=True, text=True)
        out = subprocess.run(["vvp", "-n", str(vvp)], capture_output=True, text=True).stdout
    m = re.search(r"QUIRK a>>>SH_longint=(-?\d+) a>>>SH_int=(-?\d+) a>>SH_longint=(-?\d+) a>>>4=(-?\d+)", out)
    assert m, out
    return tuple(int(x) for x in m.groups())


def _restricted_to_iverilog():
    return sorted(s.name for s in all_ips(IP_ROOT) if "verilator" not in s.sims)


@pytest.mark.skipif(not shutil.which("iverilog"), reason="no iverilog")
def test_iverilog_longint_shift_is_right(tmp_path):
    assert _run("iverilog", tmp_path) == (16384, 16384, 16384, 16384)


@pytest.mark.skipif(not shutil.which("verilator"), reason="no verilator")
def test_verilator_longint_shift_quirk(tmp_path):
    """Verilator 5.020: `longint >>> longint-localparam` folds to 0; the rest is right."""
    got = _run("verilator", tmp_path)
    assert got[1:] == (16384, 16384, 16384), got
    restricted = _restricted_to_iverilog()
    ver = subprocess.run(["verilator", "--version"], capture_output=True, text=True).stdout.strip()
    if got[0] == 16384:
        pytest.fail(f"{ver} no longer has the longint-shift bug: drop `sims: [iverilog]` from "
                    f"{restricted} and re-run tools/lockstep.py --all --sim verilator")
    assert got[0] == 0, f"{ver}: unexpected value {got[0]} (bug changed shape?)"
    # No IP needs the restriction any more: Halo_Serdes#142 emits shift amounts as
    # `localparam int`, which sidesteps the fold (halo_adc_dsp_loop: Verilator 5/5 sets).


def test_sims_restriction_carries_a_reason():
    for s in all_ips(IP_ROOT):
        if set(s.sims) != {"verilator", "iverilog"}:
            assert s.extra.get("sims_reason"), f"{s.name}: ip.yaml sims: needs a sims_reason"
