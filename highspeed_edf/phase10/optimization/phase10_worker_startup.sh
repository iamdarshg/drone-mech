#!/usr/bin/env bash
set -Ee -o pipefail

LOG=/var/log/phase10-openfoam-worker.log
mkdir -p /var/log /opt/phase10
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
  curl -fsS -H "Authorization: Bearer $tok" "https://storage.googleapis.com/storage/v1/b/${BUCKET}/o/${obj}?alt=media" -o "$2"
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
RUN_RC=1

finish() {
  local rc=$?
  set +e
  if [ -d /opt/phase10/output ]; then
    tar -czf /opt/phase10/phase10-output.tar.gz -C /opt/phase10/output .
    gcs_put /opt/phase10/phase10-output.tar.gz "$RESULT_OBJECT"
  fi
  gcs_put "$LOG" "$LOG_OBJECT"
  printf '{"instance":"%s","exitCode":%s,"finishedAtUtc":"%s"}\n' "$INSTANCE_NAME" "$rc" "$(date -u +%FT%TZ)" >/opt/phase10/finish.json
  gcs_put /opt/phase10/finish.json "$FINISH_OBJECT"
  if [ "$rc" -ne 0 ]; then gcs_put "$LOG" "$FAILURE_OBJECT"; fi
  echo "PHASE10_WORKER_FINISH rc=$rc utc=$(date -u +%FT%TZ)"
  shutdown -h now || true
}
trap finish EXIT

echo "PHASE10_WORKER_START instance=$INSTANCE_NAME utc=$(date -u +%FT%TZ)"
gcs_get "$BUNDLE_OBJECT" /opt/phase10/input.tar.gz
tar -xzf /opt/phase10/input.tar.gz -C /opt/phase10
export DEBIAN_FRONTEND=noninteractive
timeout 240 apt-get update -qq
timeout 480 apt-get install -y -qq openfoam
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
export FOAM_USER_APPBIN=/opt/phase10/user-bin
export FOAM_USER_LIBBIN=/opt/phase10/user-lib
export LD_LIBRARY_PATH="/usr/lib:/usr/lib/openmpi-system:${LD_LIBRARY_PATH:-}"
mkdir -p "$FOAM_USER_APPBIN" "$FOAM_USER_LIBBIN"
command -v gmshToFoam
command -v rhoSimpleFoam
rhoSimpleFoam -help >/opt/phase10/rhoSimpleFoam-help.log 2>&1 || true
python3 /opt/phase10/phase10/optimization/phase10_openfoam_worker.py \
  --case-root /opt/phase10/phase10/cases \
  --config /opt/phase10/phase10/configs/phase10_openfoam_study.json \
  --output /opt/phase10/output \
  --instance-name "$INSTANCE_NAME" \
  --run-budget-seconds 1320
RUN_RC=0
exit "$RUN_RC"
