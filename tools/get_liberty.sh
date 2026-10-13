#!/usr/bin/env bash
# Fetch the public standard-cell library the synthesis estimates are quoted against
# (rule 5: open flow, a public generic library, numbers labelled "estimate").
#
#   tools/get_liberty.sh            # NanGate45 (FreePDK45) typical — CI default, ~7 MB
#   tools/get_liberty.sh sky130     # sky130_fd_sc_hd tt_025C_1v80 — alternative, larger
#
# Each library is a sparse, shallow git checkout pinned to a commit, and the .lib file's
# sha256 is verified so the quoted numbers always refer to one known file.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TP="$HERE/third_party"
mkdir -p "$TP"

which=${1:-nangate45}
case "$which" in
  nangate45)
    REPO=https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts
    SHA=e5cc6e799f5ddf36e6bdf2d8c5db73373b88f52c
    DIR="$TP/orfs"
    SPARSE=flow/platforms/nangate45/lib
    LIB="$DIR/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
    SUM=8d540a4d4cf6d09d27c87ad067857a9c0c2eeb023ab7a56e058cd3113db4e9b1
    ;;
  sky130)
    REPO=https://github.com/google/skywater-pdk-libs-sky130_fd_sc_hd
    SHA=28c101fc5db17bb6cadefa4c2a146693c685f1dc
    DIR="$TP/sky130_fd_sc_hd"
    SPARSE=timing
    LIB="$DIR/timing/sky130_fd_sc_hd__tt_025C_1v80.lib"
    SUM=""   # filled in on first verified fetch (see docs/synthesis.md)
    ;;
  *) echo "unknown library $which" >&2; exit 2;;
esac

if [ ! -f "$LIB" ]; then
  rm -rf "$DIR"
  GIT_LFS_SKIP_SMUDGE=1 git clone --filter=blob:none --sparse --depth 1 "$REPO" "$DIR"
  git -C "$DIR" sparse-checkout set "$SPARSE"
  have=$(git -C "$DIR" rev-parse HEAD)
  if [ "$have" != "$SHA" ]; then
    git -C "$DIR" fetch --depth 1 origin "$SHA" && git -C "$DIR" checkout -q "$SHA"
  fi
fi
got=$(sha256sum "$LIB" | cut -d' ' -f1)
if [ -n "$SUM" ] && [ "$got" != "$SUM" ]; then
  echo "sha256 mismatch for $LIB: $got != $SUM" >&2
  exit 1
fi
echo "$LIB"
echo "sha256 $got" >&2
