#!/usr/bin/env bash
set -u
ulimit -c 0
export FOAMROOT=/workspace/openfoam-deb
export WM_PROJECT_DIR=/workspace/openfoam-deb/usr/share/openfoam
export FOAM_LIBBIN=/workspace/openfoam-deb/usr/lib
export FOAM_APPBIN=/workspace/openfoam-deb/usr/bin
export LD_LIBRARY_PATH=/workspace/openfoam-deb/usr/lib:/tmp/scotch-libs/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}
case_dir=/workspace/cfd-run-900ias-20261101/case
root=/workspace/cfd-run-900ias-20261101
cd "$case_dir" || exit 111
printf 'started_utc=%s\n' "$(date -u +%FT%TZ)" > "$root/rhoCentralFoam.attempt2.status"
set +e
/workspace/openfoam-deb/usr/bin/rhoCentralFoam -case "$case_dir" > "$root/rhoCentralFoam.attempt2.log" 2>&1
rc=$?
printf 'exit_code=%s\nfinished_utc=%s\n' "$rc" "$(date -u +%FT%TZ)" >> "$root/rhoCentralFoam.attempt2.status"
exit "$rc"
