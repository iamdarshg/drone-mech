#!/bin/bash
# Re-run the prepared transient cases with a per-case wall cap.
set -uo pipefail
PKG_DIR="$(cd "$(dirname "$0")" && pwd)"
OPENFOAM_ROOT="${OPENFOAM_ROOT:?Set OPENFOAM_ROOT to the root containing usr/bin, usr/lib, usr/share/openfoam}"
MAX_SECONDS="${MAX_SECONDS:-45}"
export WM_PROJECT_DIR="$OPENFOAM_ROOT/usr/share/openfoam"
export FOAM_LIBBIN="$OPENFOAM_ROOT/usr/lib"
export FOAM_APPBIN="$OPENFOAM_ROOT/usr/bin"
export LD_LIBRARY_PATH="$FOAM_LIBBIN${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
mkdir -p "$PKG_DIR/rerun_logs"
for speed in 700 900; do
  case_dir="$PKG_DIR/cases/pimple/ias${speed}"
  echo "COMMAND: checkMesh -case $case_dir"
  "$FOAM_APPBIN/checkMesh" -case "$case_dir" > "$PKG_DIR/rerun_logs/checkMesh_ias${speed}.log" 2>&1 || exit $?
  echo "COMMAND: timeout --signal=INT --kill-after=10s ${MAX_SECONDS}s rhoPimpleFoam -case $case_dir"
  timeout --signal=INT --kill-after=10s "${MAX_SECONDS}s" "$FOAM_APPBIN/rhoPimpleFoam" -case "$case_dir" > "$PKG_DIR/rerun_logs/rhoPimpleFoam_ias${speed}.log" 2>&1
  status=$?
  echo "exit=$status speed=$speed" | tee -a "$PKG_DIR/rerun_logs/status.txt"
done
