#!/bin/bash
# DM-G4 campaign driver (host). Meshes each elevon-deflection variant once (gmsh, host), then runs
# each case in the VM container and copies logs + postProcessing back. Resumable: a case with
# runs/<case>/postProcessing is skipped. Order = value order.
set -u
WS=$HOME/Desktop/engineering-program-v2; T=$WS/repos/drone-mech/highspeed_edf/phase15/tools/dm_g2
G=$WS/evidence/drone-mech/DM-G4/geom; R=$WS/evidence/drone-mech/DM-G4/runs; mkdir -p $R
export LIMA_HOME=$WS/tools/lima-home; L="$WS/tools/lima/bin/limactl"
NU=1.8627e-5; RHO=0.9093; NP=${NP:-12}; IT=${IT:-2000}
utas() { case $1 in 50) echo 16.120;; 60) echo 19.345;; esac; }   # bash 3.2: no assoc arrays
dl() { case $1 in d0) echo 0;; s+10) echo 10;; s-10) echo -10;; diff) echo 10;; s+20) echo 20;; esac; }
dr() { case $1 in d0) echo 0;; s+10) echo 10;; s-10) echo -10;; diff) echo -10;; s+20) echo 20;; esac; }
CASES=${CASES:-"d0:50:0 d0:50:4 s+10:50:0 s-10:50:0 diff:50:0 d0:50:8 d0:50:-4 d0:50:12 d0:60:0 d0:60:4 d0:60:8 d0:60:-4 d0:60:12 s+10:60:0 s-10:60:0 diff:60:0 s+20:50:0 s+10:50:4 s-10:50:4"}
mesh() { local v=$1 d=$R/mesh_$1; [ -s $d/dm_g4_tet.msh ] && return 0; mkdir -p $d
  NETGEN_PASSES=2 $WS/tools/envs/eng/bin/python3 $T/dm_g4_tetmesh.py $G/oml_cove_shell0_m.stl,$G/oml_cove_shell1_m.stl \
    $G/deflect/elevon_L_d$(dl $v)_m.stl $G/deflect/elevon_R_d$(dr $v)_m.stl $d 0.003 0.25 0.0007 > $d/mesh.log 2>&1 || return 1
  mkdir -p $d/check; $L shell foam -- bash $T/run_checkmesh.sh $d/dm_g4_tet.msh 2>/dev/null | tar -xzf - -C $d/check
  echo "mesh $1: $(grep -E 'cells:' $d/check/log.checkMesh | head -1) | $(grep -E '\*\*\*|Mesh OK' $d/check/log.checkMesh.quality | tr '\n' ' ')"; }
for c in $CASES; do
  IFS=: read v ias a <<< "$c"; name="IAS${ias}_a${a}_${v}"; out=$R/$name
  [ -d $out/postProcessing ] && { echo "skip $name"; continue; }
  mesh $v || { echo "mesh fail $v"; continue; }
  echo "$(date +%H:%M) run $name"; mkdir -p $out
  python3 -c "import json;json.dump({'U':$(utas $ias),'alpha':$a,'rho':$RHO,'nu':$NU,'IAS_kmh':$ias,'variant':'$v','dL':$(dl $v),'dR':$(dr $v),'Se':0.11775*0.04071,'ce':0.04071,'np':$NP,'iters':$IT},open('$out/case.json','w'),indent=1)"
  $L shell foam -- bash $T/run_dm_g4_case.sh $R/mesh_$v/dm_g4_tet.msh $name $(utas $ias) $a $NU $RHO 0,0.12762 0,0.12762 $NP $IT > $out/vm_stdout.txt 2>&1
  $L shell foam -- bash -c "cd ~/dmg4/$name && tar -czf - log.* postProcessing system constant/turbulenceProperties constant/polyMesh/boundary" | tar -xzf - -C $out
  echo "$(date +%H:%M) done $name"
done
