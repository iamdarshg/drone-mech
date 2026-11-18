#!/bin/bash
# DM-G4 low-speed case, run inside the VM (OpenFOAM v2406 container).
# usage: run_dm_g4_case.sh <mesh.msh> <case_name> <U_TAS_m_s> <alpha_deg> <nu> <rho> <hingeL_y,z_m> <hingeR_y,z_m> <np> <iters>
# Flow along +z (nose at -z); alpha > 0 tilts the freestream to come from below: U = U (0, sin a, cos a).
set -u
MSH=$1; NAME=$2; U=$3; A=$4; NU=$5; RHO=$6; HL=$7; HR=$8; NP=$9; IT=${10}
C=$HOME/dmg4/$NAME; rm -rf $C; mkdir -p $C/system $C/constant $C/0
cp "$MSH" $C/mesh.msh
read UY UZ LY LZ DY DZ < <(python3 -c "import math;a=math.radians($A);print($U*math.sin(a),$U*math.cos(a),math.cos(a),-math.sin(a),math.sin(a),math.cos(a))")
IFS=, read HLY HLZ <<< "$HL"; IFS=, read HRY HRZ <<< "$HR"
K=$(python3 -c "print(1.5*($U*0.005)**2)"); OM=$(python3 -c "k=1.5*($U*0.005)**2;print(k**0.5/(0.09**0.25*0.01))")
cat > $C/system/controlDict <<CD
FoamFile { version 2.0; format ascii; class dictionary; object controlDict; }
application simpleFoam; startFrom latestTime; startTime 0; stopAt endTime; endTime $IT; deltaT 1;
writeControl timeStep; writeInterval $IT; purgeWrite 1; writeFormat binary; writePrecision 10; writeCompression off;
timeFormat general; timePrecision 6; runTimeModifiable false;
functions {
  forcesAll { type forces; libs (forces); writeControl timeStep; writeInterval 1;
    patches (aircraft elevon_L elevon_R); rho rhoInf; rhoInf $RHO; CofR (0 0 0); }
  forcesBody { type forces; libs (forces); writeControl timeStep; writeInterval 1;
    patches (aircraft); rho rhoInf; rhoInf $RHO; CofR (0 0 0); }
  hingeL { type forces; libs (forces); writeControl timeStep; writeInterval 1;
    patches (elevon_L); rho rhoInf; rhoInf $RHO; CofR (0 $HLY $HLZ); }
  hingeR { type forces; libs (forces); writeControl timeStep; writeInterval 1;
    patches (elevon_R); rho rhoInf; rhoInf $RHO; CofR (0 $HRY $HRZ); }
  yPlus1 { type yPlus; libs (fieldFunctionObjects); writeControl writeTime; }
  residuals { type solverInfo; libs (utilityFunctionObjects); fields (U p k omega); }
}
CD
cat > $C/system/fvSchemes <<'FS'
FoamFile { version 2.0; format ascii; class dictionary; object fvSchemes; }
ddtSchemes { default steadyState; }
gradSchemes { default cellLimited Gauss linear 1; grad(U) cellLimited Gauss linear 1; }
divSchemes { default none; div(phi,U) bounded Gauss linearUpwind grad(U);
  div(phi,k) bounded Gauss upwind; div(phi,omega) bounded Gauss upwind;
  div((nuEff*dev2(T(grad(U))))) Gauss linear; }
laplacianSchemes { default Gauss linear limited 0.5; }
interpolationSchemes { default linear; }
snGradSchemes { default limited 0.5; }
wallDist { method meshWave; }
FS
cat > $C/system/fvSolution <<'FV'
FoamFile { version 2.0; format ascii; class dictionary; object fvSolution; }
solvers {
  p { solver GAMG; smoother GaussSeidel; tolerance 1e-7; relTol 0.05; }
  "(U|k|omega)" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-8; relTol 0.1; }
}
SIMPLE { nNonOrthogonalCorrectors 1; consistent yes;
  residualControl { p 1e-5; U 1e-6; "(k|omega)" 1e-6; } }
relaxationFactors { equations { U 0.7; "(k|omega)" 0.6; } fields { p 0.3; } }
FV
cat > $C/system/decomposeParDict <<DP
FoamFile { version 2.0; format ascii; class dictionary; object decomposeParDict; }
numberOfSubdomains $NP; method scotch;
DP
cat > $C/constant/transportProperties <<TP
FoamFile { version 2.0; format ascii; class dictionary; object transportProperties; }
transportModel Newtonian; nu $NU;
TP
cat > $C/constant/turbulenceProperties <<'MT'
FoamFile { version 2.0; format ascii; class dictionary; object turbulenceProperties; }
simulationType RAS; RAS { RASModel kOmegaSST; turbulence on; printCoeffs on; }
MT
FF="inlet|outlet|farfield"; WALL="aircraft|elevon_L|elevon_R"
cat > $C/0/U <<EU
FoamFile { version 2.0; format ascii; class volVectorField; object U; }
dimensions [0 1 -1 0 0 0 0]; internalField uniform (0 $UY $UZ);
boundaryField { "($FF)" { type freestreamVelocity; freestreamValue uniform (0 $UY $UZ); }
  "($WALL)" { type noSlip; } }
EU
cat > $C/0/p <<EP
FoamFile { version 2.0; format ascii; class volScalarField; object p; }
dimensions [0 2 -2 0 0 0 0]; internalField uniform 0;
boundaryField { "($FF)" { type freestreamPressure; freestreamValue uniform 0; }
  "($WALL)" { type zeroGradient; } }
EP
cat > $C/0/k <<EK
FoamFile { version 2.0; format ascii; class volScalarField; object k; }
dimensions [0 2 -2 0 0 0 0]; internalField uniform $K;
boundaryField { "($FF)" { type inletOutlet; inletValue uniform $K; value uniform $K; }
  "($WALL)" { type kqRWallFunction; value uniform $K; } }
EK
cat > $C/0/omega <<EO
FoamFile { version 2.0; format ascii; class volScalarField; object omega; }
dimensions [0 0 -1 0 0 0 0]; internalField uniform $OM;
boundaryField { "($FF)" { type inletOutlet; inletValue uniform $OM; value uniform $OM; }
  "($WALL)" { type omegaWallFunction; value uniform $OM; } }
EO
cat > $C/0/nut <<EN
FoamFile { version 2.0; format ascii; class volScalarField; object nut; }
dimensions [0 2 -1 0 0 0 0]; internalField uniform 0;
boundaryField { "($FF)" { type calculated; value uniform 0; }
  "($WALL)" { type nutkWallFunction; value uniform 0; } }
EN
docker run --rm --cpus $NP -v $C:/case -w /case opencfd/openfoam-default:2406 bash -lc "cd /case
  gmshToFoam mesh.msh > log.gmshToFoam 2>&1 || exit 11
  for w in aircraft elevon_L elevon_R; do perl -0pi -e \"s/(\$w\\s*\\{\\s*type\\s+)patch;/\\\$1wall;/\" constant/polyMesh/boundary; done
  checkMesh > log.checkMesh 2>&1
  decomposePar -force > log.decomposePar 2>&1 || exit 12
  mpirun --allow-run-as-root --oversubscribe -np $NP simpleFoam -parallel > log.simpleFoam 2>&1; echo simpleFoam exit \$?
  reconstructPar -latestTime > log.reconstructPar 2>&1
  postProcess -func yPlus -latestTime > /dev/null 2>&1; simpleFoam -postProcess -func yPlus -latestTime > log.yPlus 2>&1
  rm -rf processor* mesh.msh" 1>&2
echo done $NAME 1>&2
