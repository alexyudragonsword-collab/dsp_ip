#!/usr/bin/env bash
# Fetch the pinned yosys (+ its ABC) the synthesis estimates are quoted against (rule 5).
#
# Why pinned: the GitHub runner's apt yosys moved from 0.33 to 0.52 between two runs of the
# same RTL and the critical path moved by ~9 % (cairn/LOG.md 2026-11-03). Every number in
# docs/results.md must come from this one binary; tests/test_synth_tool.py checks the
# recorded version string. The OSS CAD Suite tarball is a dated, self-contained build.
#
#   tools/get_yosys.sh        # prints the bin dir; add it to PATH (CI: $GITHUB_PATH)
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TP="$HERE/third_party"
DATE=2026-10-25
TGZ="oss-cad-suite-linux-x64-${DATE//-/}.tgz"
URL="https://github.com/YosysHQ/oss-cad-suite-build/releases/download/$DATE/$TGZ"
SUM=4de9b4fe89a368f765aa7fc25b9f71ec9b337a54d76166eafd9e810da90f781e
VERSION="Yosys 0.70+219 (git sha1 5053d0e26, Release, Clang /usr/bin/clang++ 21.1.8)"
DIR="$TP/oss-cad-suite"
BIN="$DIR/bin"

if [ -x "$BIN/yosys" ] && [ "$("$BIN/yosys" -V)" = "$VERSION" ]; then
  echo "$BIN"
  exit 0
fi
mkdir -p "$TP/dl"
if [ ! -f "$TP/dl/$TGZ" ]; then
  curl -sSfL --retry 4 -o "$TP/dl/$TGZ.part" "$URL"
  mv "$TP/dl/$TGZ.part" "$TP/dl/$TGZ"
fi
got=$(sha256sum "$TP/dl/$TGZ" | cut -d' ' -f1)
if [ "$got" != "$SUM" ]; then
  echo "sha256 mismatch for $TGZ: $got != $SUM" >&2
  exit 1
fi
rm -rf "$DIR"
tar -xzf "$TP/dl/$TGZ" -C "$TP"
have=$("$BIN/yosys" -V)
if [ "$have" != "$VERSION" ]; then
  echo "unexpected yosys in $TGZ: $have (expected $VERSION)" >&2
  exit 1
fi
echo "$BIN"
