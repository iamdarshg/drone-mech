#!/bin/bash
source /usr/lib/openfoam/openfoam2406/etc/bashrc
set -e
SRC=/work/cfd_duct_prisms_20261105
DST=/work/cfd_duct_prisms_flow_diagnostic
if [ -e "$DST" ]; then echo 'Refusing to overwrite existing case'; exit 1; fi
cp -R "$SRC" "$DST"
foamDictionary "$DST/system/controlDict" -entry endTime -set 100
foamDictionary "$DST/system/controlDict" -entry writeInterval -set 100
timeout 180s simpleFoam -case "$DST" > "$DST/diagnostic_solver.log" 2>&1
