#!/usr/bin/env bash
set -u
ulimit -c 0
export FOAMROOT=/workspace/openfoam-deb
export WM_PROJECT_DIR=/workspace/openfoam-deb/usr/share/openfoam
export FOAM_LIBBIN=/workspace/openfoam-deb/usr/lib
export FOAM_APPBIN=/workspace/openfoam-deb/usr/bin
export LD_LIBRARY_PATH=/workspace/openfoam-deb/usr/lib:/tmp/scotch-libs/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}
case_dir=/tmp/gmsh_halfwing_fluid/ias900_case
root=/tmp/gmsh_halfwing_fluid
cd "$case_dir" || exit 111
printf 'started_utc=%s\n' "$(date -u +%FT%TZ)" > "$root/status.txt"
set +e
nice -n 10 timeout --signal=INT --kill-after=30s 1800s /workspace/openfoam-deb/usr/bin/rhoPimpleFoam -case "$case_dir" > "$root/rhoPimpleFoam.log" 2>&1
rc=$?
printf 'exit_code=%s\nfinished_utc=%s\n' "$rc" "$(date -u +%FT%TZ)" >> "$root/status.txt"
exit "$rc"
