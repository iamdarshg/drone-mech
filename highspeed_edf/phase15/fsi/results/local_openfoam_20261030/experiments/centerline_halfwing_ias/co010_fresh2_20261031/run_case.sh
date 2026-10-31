#!/usr/bin/env bash
set -u
root="$(cd "$(dirname "$0")" && pwd)"
speed="$1"
case_dir="$root/ias${speed}"
export WM_PROJECT_DIR=/workspace/openfoam-deb/usr/share/openfoam
export FOAM_LIBBIN=/workspace/openfoam-deb/usr/lib
export FOAM_APPBIN=/workspace/openfoam-deb/usr/bin
export LD_LIBRARY_PATH=/workspace/openfoam-deb/usr/lib
cd "$case_dir" || exit 111
printf 'started_utc=%s\n' "$(date -u +%FT%TZ)" > "$root/status_ias${speed}.txt"
timeout --signal=INT --kill-after=30s 1800s /workspace/openfoam-deb/usr/bin/rhoPimpleFoam -case "$case_dir" > "$root/rhoPimpleFoam_ias${speed}.log" 2>&1
rc=$?
printf 'exit_code=%s\nfinished_utc=%s\n' "$rc" "$(date -u +%FT%TZ)" >> "$root/status_ias${speed}.txt"
exit "$rc"
