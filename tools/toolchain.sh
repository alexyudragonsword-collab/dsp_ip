#!/usr/bin/env bash
# Probe / install the open-source toolchain dsp_ip needs:
#   simulator: verilator (preferred) or iverilog; synthesis: yosys.
# Vendor tools (Vivado/Quartus/DC) are never assumed. If apt is unavailable,
# record "lockstep simulator" under ROADMAP "被外部阻塞" rather than faking RTL in Python.
set -euo pipefail

# Simulators: $DSPIP_SIM_BIN/<name> when set (e.g. the pinned bundle's bin/, as the
# lockstep CI "bundle" leg does), else PATH — the same rule as src/dspip/sims.py.
sim() { if [ -n "${DSPIP_SIM_BIN:-}" ]; then echo "$DSPIP_SIM_BIN/$1"; else echo "$1"; fi; }
have() { command -v "$1" >/dev/null 2>&1; }

if [ "${1:-}" = "--install" ]; then
  if have apt-get; then
    SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO=sudo
    export DEBIAN_FRONTEND=noninteractive
    $SUDO apt-get update -qq
    $SUDO apt-get install -y -qq iverilog verilator
    "$(dirname "$0")/get_yosys.sh" >/dev/null   # pinned yosys (docs/synthesis.md)
  else
    echo "no apt-get: install verilator/iverilog/yosys manually" >&2
    exit 2
  fi
fi

# yosys comes from the pinned OSS CAD Suite (tools/synth.py looks there first). Its bin/
# also holds verilator and iverilog; they are used only via DSPIP_SIM_BIN, never via PATH.
PINNED_YOSYS="$(cd "$(dirname "$0")/.." && pwd)/third_party/oss-cad-suite/bin/yosys"

echo "== dsp_ip toolchain =="
[ -n "${DSPIP_SIM_BIN:-}" ] && echo "  (simulators from DSPIP_SIM_BIN=$DSPIP_SIM_BIN)"
for t in verilator iverilog vvp yosys python3; do
  case $t in verilator|iverilog|vvp) b=$(sim $t);; *) b=$t;; esac
  if [ "$t" = yosys ] && [ -x "$PINNED_YOSYS" ]; then
    printf "  %-10s %s [pinned: tools/get_yosys.sh]\n" yosys "$("$PINNED_YOSYS" -V)"
  elif have "$b"; then
    case $t in
      verilator) v=$("$b" --version 2>&1 | sed -n 1p);;
      iverilog)  v=$("$b" -V 2>&1 | sed -n 1p);;
      vvp)       v=$("$b" -V 2>&1 | sed -n 1p);;
      yosys)     v="$(yosys -V) [NOT the pinned build: run tools/get_yosys.sh]";;
      python3)   v=$(python3 --version);;
    esac
    printf "  %-10s %s\n" "$t" "$v"
  else
    printf "  %-10s MISSING\n" "$t"
  fi
done
if ! have "$(sim verilator)" && ! have "$(sim iverilog)"; then
  echo "no simulator: lockstep cannot run (see ROADMAP 被外部阻塞)" >&2
  exit 1
fi
