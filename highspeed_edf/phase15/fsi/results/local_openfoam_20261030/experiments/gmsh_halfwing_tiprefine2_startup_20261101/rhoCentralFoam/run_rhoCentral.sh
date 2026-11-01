#!/usr/bin/env bash
set -u
ulimit -c 0
export FOAMROOT=/workspace/openfoam-deb
export WM_PROJECT_DIR=/workspace/openfoam-deb/usr/share/openfoam
export FOAM_LIBBIN=/workspace/openfoam-deb/usr/lib
export FOAM_APPBIN=/workspace/openfoam-deb/usr/bin
export LD_LIBRARY_PATH=/workspace/openfoam-deb/usr/lib:/tmp/scotch-libs/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}
case_dir=/tmp/gmsh_halfwing_fluid/rhoCentral_case
root=/tmp/gmsh_halfwing_fluid
cd "$case_dir" || exit 111
printf 'started_utc=%s\n' "$(date -u +%FT%TZ)" > "$root/rhoCentral.status"
set +e
/workspace/openfoam-deb/usr/bin/rhoCentralFoam -case "$case_dir" > "$root/rhoCentralFoam.log" 2>&1
rc=$?
printf 'exit_code=%s\nfinished_utc=%s\n' "$rc" "$(date -u +%FT%TZ)" >> "$root/rhoCentral.status"
exit "$rc"
