#!/usr/bin/env bash
# Pinned OpenROAD for the place-and-route estimates (rule 5: open flow only, numbers labelled
# "estimate"). Prints the wrapper to call; idempotent.
#
#   tools/get_openroad.sh          # -> third_party/openroad-env/bin/openroad-dspip
#
# OpenROAD is the litex-hub conda build openroad-2.0_12381_g01bba3695 (2024-02-23, py310),
# sha256-checked against the channel index. Its conda dependencies (Boost 1.73, Qt 5.9,
# spdlog 1.9 / fmt 8, CPython 3.10) are not installable as one conda-forge environment
# any more, and the libboost 1.73 it names lives only in Anaconda's `defaults` channel
# (separate terms of service, not used here). The same shared libraries come from two
# conda-forge prefixes instead, created with a sha256-pinned micromamba:
#   openroad-env : boost-cpp 1.73, qt 5.9, spdlog 1.9, fmt 8, zlib < 1.3  (+ the openroad binary)
#   openroad-py  : CPython 3.10 (libpython3.10.so)
# and the wrapper puts both lib/ dirs on LD_LIBRARY_PATH. The platform files (NanGate45 LEF,
# setRC, tracks) come from the pinned OpenROAD-flow-scripts checkout (tools/get_liberty.sh).
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TP="$HERE/third_party"
ENV="$TP/openroad-env"
PY="$TP/openroad-py"
DL="$TP/dl"
WRAP="$ENV/bin/openroad-dspip"
WANT="2.0-12381-g01bba3695"

MM_FILE=micromamba-2.10.0-0.tar.bz2
MM_SUM=9a97976244929bbae28fb1fae504e74a3e7e6d1932870e3a03321f01b7fbd07b
OR_FILE=openroad-2.0_12381_g01bba3695-20240223_100318_py310.tar.bz2
OR_SUM=5f591c092468e4787b2e8683c51a149058ad83e446eae78c2b19e78f539c6322

if [ -x "$WRAP" ] && [ "$("$WRAP" -version 2>/dev/null | tr -d ' ')" = "$WANT" ]; then
  echo "$WRAP"; exit 0
fi

fetch() {  # url file sha256 -> $DL/file, verified
  mkdir -p "$DL"
  [ -f "$DL/$2" ] || curl -sSfL -m 600 -o "$DL/$2" "$1"
  echo "$3  $DL/$2" | sha256sum -c --quiet - || { rm -f "$DL/$2"; echo "sha256 mismatch: $2" >&2; exit 1; }
}
fetch "https://conda.anaconda.org/conda-forge/linux-64/$MM_FILE" "$MM_FILE" "$MM_SUM"
fetch "https://conda.anaconda.org/litex-hub/linux-64/$OR_FILE" "$OR_FILE" "$OR_SUM"

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/mm" "$WORK/or"
tar -xjf "$DL/$MM_FILE" -C "$WORK/mm" bin/micromamba
tar -xjf "$DL/$OR_FILE" -C "$WORK/or"
MM="$WORK/mm/bin/micromamba"
export MAMBA_ROOT_PREFIX="$WORK/root"

rm -rf "$ENV" "$PY"
"$MM" create -y -q -p "$ENV" --override-channels -c conda-forge \
  "boost-cpp=1.73" "qt=5.9" "spdlog=1.9" "fmt=8" "zlib<1.3"
"$MM" create -y -q -p "$PY" --override-channels -c conda-forge "python=3.10.*=*_cpython"
cp -a "$WORK/or/bin/openroad" "$WORK/or/bin/sta" "$ENV/bin/"
cp -an "$WORK/or/lib/." "$ENV/lib/" 2>/dev/null || true
cp -an "$WORK/or/share/." "$ENV/share/" 2>/dev/null || true

cat > "$WRAP" <<EOF
#!/usr/bin/env bash
export LD_LIBRARY_PATH="$ENV/lib:$PY/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
export QT_QPA_PLATFORM=offscreen
exec "$ENV/bin/openroad" "\$@"
EOF
chmod +x "$WRAP"
got="$("$WRAP" -version | tr -d ' ')"
[ "$got" = "$WANT" ] || { echo "openroad reports $got, expected $WANT" >&2; exit 1; }
echo "$WRAP"
