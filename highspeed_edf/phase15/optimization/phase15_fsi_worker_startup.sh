#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=/opt/phase15-fsi
LOG=/var/log/phase15-fsi-worker.log
mkdir -p "$ROOT" /var/log
exec > >(tee -a "$LOG") 2>&1

MD='Metadata-Flavor: Google'
ATTR='http://metadata.google.internal/computeMetadata/v1/instance/attributes'
META='http://metadata.google.internal/computeMetadata/v1'
TOKEN_URL="$META/instance/service-accounts/default/token"
attr() { curl -fsS --max-time 5 -H "$MD" "$ATTR/$1"; }
urlencode() { python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1],safe=""))' "$1"; }
token() { curl -fsS --max-time 8 -H "$MD" "$TOKEN_URL" | python3 -c 'import json,sys;print(json.load(sys.stdin)["access_token"])'; }
gcs_get() {
  local object="$1" target="$2" tok
  object="$(urlencode "$object")"
  tok="$(token)"
  curl -fsS --max-time 120 -H "Authorization: Bearer $tok" \
    "https://storage.googleapis.com/storage/v1/b/${BUCKET}/o/${object}?alt=media" -o "$target"
}
gcs_put() {
  local file="$1" name="$2" object tok
  [ -f "$file" ] || return 0
  object="$(urlencode "$name")"
  tok="$(token)"
  curl -fsS --max-time 120 -X POST --data-binary "@$file" \
    -H "Authorization: Bearer $tok" -H 'Content-Type: application/octet-stream' \
    "https://storage.googleapis.com/upload/storage/v1/b/${BUCKET}/o?uploadType=media&name=${object}" >/dev/null
}

BUCKET="$(attr BUCKET)"
BUNDLE_OBJECT="$(attr BUNDLE_OBJECT)"
RESULT_OBJECT="$(attr RESULT_OBJECT)"
LOG_OBJECT="$(attr LOG_OBJECT)"
FINISH_OBJECT="$(attr FINISH_OBJECT)"
MAX_ARTIFACT_BYTES="$(attr MAX_ARTIFACT_BYTES)"
INSTANCE_NAME="$(curl -fsS --max-time 5 -H "$MD" "$META/instance/name")"

finish() {
  local rc=$?
  set +e
  mkdir -p "$ROOT/output"
  cp "$LOG" "$ROOT/output/worker_startup.log" 2>/dev/null
  tar -czf "$ROOT/phase15-fsi-output.tar.gz" -C "$ROOT/output" . 2>/dev/null
  local size
  size="$(stat -c '%s' "$ROOT/phase15-fsi-output.tar.gz" 2>/dev/null || echo 999999999)"
  if [ "$size" -le "$MAX_ARTIFACT_BYTES" ]; then
    gcs_put "$ROOT/phase15-fsi-output.tar.gz" "$RESULT_OBJECT"
  else
    echo "PHASE15_FSI_ARTIFACT_LIMIT_EXCEEDED bytes=$size cap=$MAX_ARTIFACT_BYTES"
  fi
  gcs_put "$LOG" "$LOG_OBJECT"
  printf '{"instance":"%s","exitCode":%s,"finishedAtUtc":"%s","artifactBytes":%s}\n' \
    "$INSTANCE_NAME" "$rc" "$(date -u +%FT%TZ)" "$size" > "$ROOT/finish.json"
  gcs_put "$ROOT/finish.json" "$FINISH_OBJECT"
  echo "PHASE15_FSI_WORKER_FINISH rc=$rc utc=$(date -u +%FT%TZ)"
  shutdown -h now >/dev/null 2>&1 || true
}
trap finish EXIT

echo "PHASE15_FSI_WORKER_START instance=$INSTANCE_NAME utc=$(date -u +%FT%TZ)"
gcs_get "$BUNDLE_OBJECT" "$ROOT/input.tar.gz"
tar -xzf "$ROOT/input.tar.gz" -C "$ROOT"

export DEBIAN_FRONTEND=noninteractive
echo "STEP install OpenFOAM and adapter build dependencies"
timeout 900 apt-get -o Acquire::ForceIPv4=true update -qq
timeout 1200 apt-get -o Acquire::ForceIPv4=true install -y -qq git ca-certificates curl wget tar gnupg \
  build-essential cmake make pkg-config python3

echo "STEP install OpenCFD OpenFOAM (provides wmake + headers)"
curl -fsSL --max-time 90 https://dl.openfoam.com/add-debian-repo.sh -o "$ROOT/add-openfoam-repo.sh"
bash "$ROOT/add-openfoam-repo.sh" || true
timeout 900 apt-get -o Acquire::ForceIPv4=true update -qq
OF_PKG=""
for candidate in openfoam2606-dev openfoam2512-dev openfoam2412-dev openfoam2312-dev; do
  if apt-cache show "$candidate" >/dev/null 2>&1; then OF_PKG="$candidate"; break; fi
done
if [ -z "$OF_PKG" ]; then
  echo "PHASE15_FSI_FAIL no OpenCFD openfoam*-dev package available"
  apt-cache search '^openfoam' | head -20
  exit 5
fi
echo "OF_PKG=$OF_PKG"
timeout 1800 apt-get -o Acquire::ForceIPv4=true install -y -qq "$OF_PKG"

echo "STEP install pinned preCICE/CalculiX packages"
curl -fsSL --max-time 90 \
  https://github.com/precice/precice/releases/download/v3.4.1/libprecice3_3.4.1_jammy.deb \
  -o "$ROOT/libprecice3.deb"
echo '56253637bdfa9b2641c880aa329915a06911bf93268121463fa9c26a854d895b  /opt/phase15-fsi/libprecice3.deb' | sha256sum -c -
timeout 180 apt-get install -y "$ROOT/libprecice3.deb"
curl -fsSL --max-time 90 \
  https://github.com/precice/calculix-adapter/releases/download/v2.20.2/calculix-precice3_2.20.2-1_amd64_jammy.deb \
  -o "$ROOT/calculix-precice3.deb"
echo '9942fa30ccead41a3322b9b3b4ba646c9a91b31300d477a5ef73b76fe49d9cc4  /opt/phase15-fsi/calculix-precice3.deb' | sha256sum -c -
timeout 180 apt-get install -y "$ROOT/calculix-precice3.deb"

# Ubuntu's OpenFOAM 1912 package installs the commands in /usr/bin.
export WM_PROJECT=OpenFOAM
export WM_PROJECT_VERSION=1912
export WM_PROJECT_DIR=/usr/share/openfoam
export WM_PROJECT_INST_DIR=/usr/share/openfoam
export FOAM_APPBIN=/usr/bin
export FOAM_LIBBIN=/usr/lib
export FOAM_ETC=/usr/share/openfoam/etc
export FOAM_TUTORIALS=/usr/share/openfoam/tutorials
export FOAM_USER_APPBIN="$ROOT/user-bin"
export FOAM_USER_LIBBIN="$ROOT/user-lib"
export PRECICE_OPENFOAM_TARGET_DIR="$FOAM_USER_LIBBIN"
export LD_LIBRARY_PATH="/usr/lib:/usr/lib/openmpi-system:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
mkdir -p "$FOAM_USER_APPBIN" "$FOAM_USER_LIBBIN"

echo "STEP locate and source the OpenFOAM environment (provides wmake)"
FOAM_BASHRC=""
for candidate in /usr/lib/openfoam/*/etc/bashrc /usr/share/openfoam/etc/bashrc \
                 /opt/openfoam*/etc/bashrc /usr/lib/openfoam/etc/bashrc; do
  if [ -f "$candidate" ]; then FOAM_BASHRC="$candidate"; break; fi
done
if [ -z "$FOAM_BASHRC" ]; then
  echo "PHASE15_FSI_FAIL openfoam etc/bashrc not found"
  find / -name bashrc -path '*openfoam*' -print 2>/dev/null | head -20
  exit 3
fi
echo "FOAM_BASHRC=$FOAM_BASHRC"
# OpenFOAM's bashrc is not nounset-clean; relax -u only while sourcing it.
set +u
# shellcheck disable=SC1090
source "$FOAM_BASHRC" || true
set -u
# OpenFOAM's bashrc resets the user dirs; keep our adapter lib/app dirs and make
# them runtime-discoverable (the case loads libpreciceAdapterFunctionObject.so).
export FOAM_USER_LIBBIN="$ROOT/user-lib"
export FOAM_USER_APPBIN="$ROOT/user-bin"
export PRECICE_OPENFOAM_TARGET_DIR="$ROOT/user-lib"
export LD_LIBRARY_PATH="$ROOT/user-lib:$ROOT/user-bin:/usr/lib:${LD_LIBRARY_PATH:-}"
mkdir -p "$FOAM_USER_LIBBIN" "$FOAM_USER_APPBIN"
if ! command -v wmake >/dev/null; then
  echo "PHASE15_FSI_FAIL wmake still unavailable after sourcing $FOAM_BASHRC"
  echo "PATH=$PATH"
  exit 4
fi
echo "wmake=$(command -v wmake) FOAM_APPBIN=${FOAM_APPBIN:-none} FOAM_USER_LIBBIN=${FOAM_USER_LIBBIN:-none}"

echo "STEP build pinned OpenFOAM-preCICE adapter v1.4.0"
curl -fsSL --max-time 90 \
  https://github.com/precice/openfoam-adapter/releases/download/v1.4.0/openfoam-adapter-1.4.0-OpenFOAMv1812-v2606-newer.tar.gz \
  -o "$ROOT/openfoam-adapter.tar.gz"
echo '399c89ab0fc5dfcff87f77433dddb60d4de0b2071de9b78b0e756e4079fd6a21  /opt/phase15-fsi/openfoam-adapter.tar.gz' | sha256sum -c -
mkdir -p "$ROOT/openfoam-adapter"
tar -xzf "$ROOT/openfoam-adapter.tar.gz" --strip-components=1 -C "$ROOT/openfoam-adapter"
cd "$ROOT/openfoam-adapter"
export WM_NCOMPPROCS=2
timeout 600 ./Allwmake
test -s "$ROOT/user-lib/libpreciceAdapterFunctionObject.so"
ldd "$ROOT/user-lib/libpreciceAdapterFunctionObject.so"

echo "STEP verify solver binaries (diagnostic; the worker performs the hard gate)"
for exe in gmshToFoam checkMesh rhoPimpleFoam ccx_preCICE gmsh; do
  printf '%s -> %s\n' "$exe" "$(command -v "$exe" || echo MISSING)"
done
(precice-tools version 2>/dev/null || precice-version 2>/dev/null || echo 'precice tool version probe unavailable') || true

echo "STEP run coupled wing candidates"
python3 "$ROOT/phase15/optimization/phase15_fsi_worker.py" \
  --case-root "$ROOT/phase15/fsi/cases" --output "$ROOT/output" \
  --candidate-timeout-seconds 300
