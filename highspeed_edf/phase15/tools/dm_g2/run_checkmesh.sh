#!/bin/bash
# Runs inside the VM: gmshToFoam + strict checkMesh in the OpenFOAM v2406 container.
set -u
C=$HOME/dmg2c; rm -rf $C; mkdir -p $C/system $C/constant
cp "$1" $C/mesh.msh
cat > $C/system/controlDict <<'CD'
FoamFile { version 2.0; format ascii; class dictionary; object controlDict; }
application simpleFoam; startFrom startTime; startTime 0; stopAt endTime; endTime 1; deltaT 1;
writeControl timeStep; writeInterval 1; writeFormat ascii; writePrecision 12; writeCompression off;
timeFormat general; timePrecision 6; runTimeModifiable false;
CD
cat > $C/system/fvSchemes <<'FS'
FoamFile { version 2.0; format ascii; class dictionary; object fvSchemes; }
ddtSchemes { default steadyState; } gradSchemes { default Gauss linear; }
divSchemes { default none; } laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; } snGradSchemes { default corrected; }
FS
cat > $C/system/fvSolution <<'FV'
FoamFile { version 2.0; format ascii; class dictionary; object fvSolution; }
FV
cat > $C/system/meshQualityDict <<'MQ'
FoamFile { version 2.0; format ascii; class dictionary; object meshQualityDict; }
maxNonOrtho 65; maxBoundarySkewness 20; maxInternalSkewness 4; maxConcave 80;
minVol 1e-13; minTetQuality 1e-9; minArea -1; minTwist 0.02; minDeterminant 0.001;
minFaceWeight 0.05; minVolRatio 0.01; minTriangleTwist -1; nSmoothScale 4; errorReduction 0.75;
MQ
docker run --rm -v $C:/case -w /case opencfd/openfoam-default:2406 bash -lc 'cd /case; 
  echo "== WM_PROJECT_VERSION=$WM_PROJECT_VERSION"
  gmshToFoam mesh.msh > log.gmshToFoam 2>&1; echo "gmshToFoam exit $?"
  perl -0pi -e "s/(aircraft\s*\{\s*type\s+)patch;/\$1wall;/" constant/polyMesh/boundary
  grep -A3 aircraft constant/polyMesh/boundary | head -4
  checkMesh -allTopology -allGeometry > log.checkMesh 2>&1; echo "checkMesh exit $?"
  checkMesh -allTopology -allGeometry -meshQuality -writeSets vtk > log.checkMesh.quality 2>&1; echo "checkMesh -meshQuality exit $?"' 1>&2
tar -C $C -czf - log.gmshToFoam log.checkMesh log.checkMesh.quality constant/polyMesh system
