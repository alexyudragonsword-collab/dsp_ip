#!/usr/bin/env bash
# Probe / install the open-source toolchain dsp_ip needs:
#   simulator: verilator (preferred) or iverilog; synthesis: yosys.
# Vendor tools (Vivado/Quartus/DC) are never assumed. If apt is unavailable,
# record "lockstep simulator" under ROADMAP "被外部阻塞" rather than faking RTL in Python.
set -euo pipefail

have() { command -v "$1" >/dev/null 2>&1; }

if [ "${1:-}" = "--install" ]; then
  if have apt-get; then
    SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO=sudo
    export DEBIAN_FRONTEND=noninteractive
    $SUDO apt-get update -qq
    $SUDO apt-get install -y -qq iverilog verilator yosys
  else
    echo "no apt-get: install verilator/iverilog/yosys manually" >&2
    exit 2
  fi
fi

echo "== dsp_ip toolchain =="
for t in verilator iverilog vvp yosys python3; do
  if have "$t"; then
    case $t in
      verilator) v=$(verilator --version | head -1);;
      iverilog)  v=$(iverilog -V 2>&1 | head -1);;
      vvp)       v=$(vvp -V 2>&1 | head -1);;
      yosys)     v=$(yosys -V);;
      python3)   v=$(python3 --version);;
    esac
    printf "  %-10s %s\n" "$t" "$v"
  else
    printf "  %-10s MISSING\n" "$t"
  fi
done
if ! have verilator && ! have iverilog; then
  echo "no simulator: lockstep cannot run (see ROADMAP 被外部阻塞)" >&2
  exit 1
fi
