"""Where the simulators come from.

Two toolchains run lockstep in CI: the distro packages (Verilator 5.020 / Icarus 12 on
ubuntu-latest) and the pinned OSS CAD Suite bundle (``tools/get_yosys.sh``: Verilator
5.053 / Icarus 14). ``DSPIP_SIM_BIN=<dir>`` (or ``tools/lockstep.py --sim-bin <dir>``)
selects the binaries in that directory; unset, the bare names on PATH are used. The
bundle is never put on PATH, so it cannot shadow the distro simulators by accident.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from dspip.ipspec import SIMS

__all__ = ["SIMS", "SIM_BIN_ENV", "exe", "installed", "sim_bin", "version", "which"]
SIM_BIN_ENV = "DSPIP_SIM_BIN"
_VERSION_ARGS = {"verilator": ["--version"], "iverilog": ["-V"]}


def sim_bin() -> Path | None:
    d = os.environ.get(SIM_BIN_ENV)
    return Path(d).resolve() if d else None


def exe(name: str) -> str:
    """Command for ``verilator`` / ``iverilog`` / ``vvp``: the binary in $DSPIP_SIM_BIN
    if set, else the bare name (PATH)."""
    d = sim_bin()
    return str(d / name) if d else name


def which(name: str) -> str | None:
    return shutil.which(exe(name))


def installed() -> list[str]:
    """Simulators available under the current selection, in preference order."""
    return [s for s in SIMS if which(s) and (s != "iverilog" or which("vvp"))]


def version(sim: str) -> str | None:
    """First line of the simulator's version banner (recorded in lockstep reports)."""
    if not which(sim):
        return None
    r = subprocess.run([exe(sim)] + _VERSION_ARGS[sim], capture_output=True, text=True)
    out = (r.stdout or r.stderr).strip()
    return out.splitlines()[0] if out else None
