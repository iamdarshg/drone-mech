#!/usr/bin/env bash
set -u
ulimit -c 0
export WM_PROJECT_DIR=/workspace/openfoam-deb/usr/share/openfoam
export FOAM_LIBBIN=/workspace/openfoam-deb/usr/lib
export FOAM_APPBIN=/workspace/openfoam-deb/usr/bin
export LD_LIBRARY_PATH=/workspace/openfoam-deb/usr/lib
case_dir=/workspace/drone-mech-transonic/highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/centerline_halfwing_ias/transonic_ias900_lowerCo_20261031/ias900
cd "$case_dir" || exit 111
printf 'started_utc=%s\n' "$(date -u +%FT%TZ)" > ../status.txt
set +e
nice -n 10 timeout --signal=INT --kill-after=30s 1800s /workspace/openfoam-deb/usr/bin/rhoPimpleFoam -case "$case_dir" > ../rhoPimpleFoam_ias900.log 2>&1
rc=$?
printf 'exit_code=%s\nfinished_utc=%s\n' "$rc" "$(date -u +%FT%TZ)" >> ../status.txt
exit "$rc"
