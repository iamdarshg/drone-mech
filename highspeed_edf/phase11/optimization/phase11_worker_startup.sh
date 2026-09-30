#!/usr/bin/env bash
set -Ee -o pipefail

LOG=/var/log/phase11-openfoam-worker.log
mkdir -p /var/log /opt/phase11
exec > >(tee -a "$LOG") 2>&1
MD='Metadata-Flavor: Google'
ATTR='http://metadata.google.internal/computeMetadata/v1/instance/attributes'
TOKEN_URL='http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token'
attr() { curl -fsS -H "$MD" "$ATTR/$1"; }
urlencode() { python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1],safe=""))' "$1"; }
token() { curl -fsS -H "$MD" "$TOKEN_URL" | python3 -c 'import json,sys;print(json.load(sys.stdin)["access_token"])'; }
gcs_get() {
  local obj tok
  obj="$(urlencode "$1")"; tok="$(token)"
  curl -fsS -H "Authorization: Bearer $tok" \
    "https://storage.googleapis.com/storage/v1/b/${BUCKET}/o/${obj}?alt=media" -o "$2"
}
gcs_put() {
  local file="$1" name="$2" obj tok
  [ -f "$file" ] || return 0
  obj="$(urlencode "$name")"; tok="$(token)"
  curl -fsS -X POST --data-binary "@$file" -H "Authorization: Bearer $tok" \
    -H 'Content-Type: application/octet-stream' \
    "https://storage.googleapis.com/upload/storage/v1/b/${BUCKET}/o?uploadType=media&name=${obj}" >/dev/null
}

BUCKET="$(attr BUCKET)"
BUNDLE_OBJECT="$(attr BUNDLE_OBJECT)"
RESULT_OBJECT="$(attr RESULT_OBJECT)"
LOG_OBJECT="$(attr LOG_OBJECT)"
FAILURE_OBJECT="$(attr FAILURE_OBJECT)"
INSTANCE_NAME="$(attr INSTANCE_NAME)"
FINISH_OBJECT="${RESULT_OBJECT%.tar.gz}-finish.json"
RUNNER_RC=1

finish() {
  local rc=$?
  set +e
  if [ -d /opt/phase11/output ]; then
    tar -czf /opt/phase11/phase11-output.tar.gz -C /opt/phase11/output .
    gcs_put /opt/phase11/phase11-output.tar.gz "$RESULT_OBJECT"
  fi
  gcs_put "$LOG" "$LOG_OBJECT"
  printf '{"instance":"%s","exitCode":%s,"finishedAtUtc":"%s"}\n' \
    "$INSTANCE_NAME" "$rc" "$(date -u +%FT%TZ)" >/opt/phase11/finish.json
  gcs_put /opt/phase11/finish.json "$FINISH_OBJECT"
  if [ "$rc" -ne 0 ]; then gcs_put "$LOG" "$FAILURE_OBJECT"; fi
  echo "PHASE11_WORKER_FINISH rc=$rc utc=$(date -u +%FT%TZ)"
  shutdown -h now || true
}
trap finish EXIT

echo "PHASE11_WORKER_START instance=$INSTANCE_NAME utc=$(date -u +%FT%TZ)"
gcs_get "$BUNDLE_OBJECT" /opt/phase11/input.tar.gz
tar -xzf /opt/phase11/input.tar.gz -C /opt/phase11
export DEBIAN_FRONTEND=noninteractive
timeout 90 apt-get update -qq
timeout 180 apt-get install -y -qq openfoam

# Ubuntu's OpenFOAM 1912 binaries and shared libraries are installed in /usr/bin
# and /usr/lib; set the package layout explicitly instead of relying on the
# upstream bashrc's absent helper scripts.
export WM_PROJECT=OpenFOAM
export WM_PROJECT_VERSION=1912
export WM_PROJECT_DIR=/usr/share/openfoam
export WM_PROJECT_INST_DIR=/usr/share/openfoam
export FOAM_APPBIN=/usr/bin
export FOAM_LIBBIN=/usr/lib
export FOAM_ETC=/usr/share/openfoam/etc
export FOAM_TUTORIALS=/usr/share/openfoam/tutorials
export FOAM_SITE_APPBIN=/usr/local/bin
export FOAM_SITE_LIBBIN=/usr/local/lib
export FOAM_USER_APPBIN=/opt/phase11/user-bin
export FOAM_USER_LIBBIN=/opt/phase11/user-lib
export LD_LIBRARY_PATH="/usr/lib:/usr/lib/openmpi-system:${LD_LIBRARY_PATH:-}"
mkdir -p "$FOAM_USER_APPBIN" "$FOAM_USER_LIBBIN"
command -v gmshToFoam
command -v changeDictionary
command -v checkMesh
command -v rhoSimpleFoam
rhoSimpleFoam -help >/opt/phase11/rhoSimpleFoam-help.log 2>&1 || true
RUN_BUDGET="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["cloudBudget"]["runnerBudgetSeconds"])' \
  /opt/phase11/phase11/configs/phase11_iterative_optimization.json)"

python3 /opt/phase11/phase10/optimization/phase10_openfoam_worker.py \
  --case-root /opt/phase11/phase11/cases \
  --config /opt/phase11/phase11/configs/phase11_iterative_optimization.json \
  --output /opt/phase11/output \
  --instance-name "$INSTANCE_NAME" \
  --run-budget-seconds "$RUN_BUDGET"
RUNNER_RC=0
exit "$RUNNER_RC"
