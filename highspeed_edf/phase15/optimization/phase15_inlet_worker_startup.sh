#!/usr/bin/env bash
set -Ee -o pipefail
LOG=/var/log/phase15-inlet-worker.log
mkdir -p /var/log /opt/phase15
exec > >(tee -a "$LOG") 2>&1
MD='Metadata-Flavor: Google'
ATTR='http://metadata.google.internal/computeMetadata/v1/instance/attributes'
TOKEN_URL='http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token'
attr() { curl -fsS -H "$MD" "$ATTR/$1"; }
urlencode() { python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1],safe=""))' "$1"; }
token() { curl -fsS -H "$MD" "$TOKEN_URL" | python3 -c 'import json,sys;print(json.load(sys.stdin)["access_token"])'; }
gcs_get() { local obj tok; obj="$(urlencode "$1")"; tok="$(token)"; curl -fsS -H "Authorization: Bearer $tok" "https://storage.googleapis.com/storage/v1/b/${BUCKET}/o/${obj}?alt=media" -o "$2"; }
gcs_put() { local f="$1" n="$2" obj tok; [ -f "$f" ] || return 0; obj="$(urlencode "$n")"; tok="$(token)"; curl -fsS -X POST --data-binary "@$f" -H "Authorization: Bearer $tok" -H 'Content-Type: application/octet-stream' "https://storage.googleapis.com/upload/storage/v1/b/${BUCKET}/o?uploadType=media&name=${obj}" >/dev/null; }
BUCKET="$(attr BUCKET)"; BUNDLE_OBJECT="$(attr BUNDLE_OBJECT)"; RESULT_OBJECT="$(attr RESULT_OBJECT)"; LOG_OBJECT="$(attr LOG_OBJECT)"; FAILURE_OBJECT="$(attr FAILURE_OBJECT)"; INSTANCE_NAME="$(attr INSTANCE_NAME)"
FINISH_OBJECT="${RESULT_OBJECT%.tar.gz}-finish.json"
RUN_RC=1
finish() {
  local rc=$?
  set +e
  if [ -d /opt/phase15/output ]; then tar -czf /opt/phase15/phase15-output.tar.gz -C /opt/phase15/output .; gcs_put /opt/phase15/phase15-output.tar.gz "$RESULT_OBJECT"; fi
  gcs_put "$LOG" "$LOG_OBJECT"
  printf '{"instance":"%s","exitCode":%s,"finishedAtUtc":"%s"}\n' "$INSTANCE_NAME" "$rc" "$(date -u +%FT%TZ)" >/opt/phase15/finish.json
  gcs_put /opt/phase15/finish.json "$FINISH_OBJECT"
  [ "$rc" -ne 0 ] && gcs_put "$LOG" "$FAILURE_OBJECT"
  echo "PHASE15_WORKER_FINISH rc=$rc utc=$(date -u +%FT%TZ)"
  shutdown -h now || true
}
trap finish EXIT
echo "PHASE15_WORKER_START instance=$INSTANCE_NAME utc=$(date -u +%FT%TZ) bucket=$BUCKET bundle=$BUNDLE_OBJECT"
echo "STEP fetch-bundle"
gcs_get "$BUNDLE_OBJECT" /opt/phase15/input.tar.gz
echo "STEP extract-bundle"
tar -xzf /opt/phase15/input.tar.gz -C /opt/phase15
echo "STEP apt-update"
export DEBIAN_FRONTEND=noninteractive
timeout 300 apt-get update -qq
echo "STEP apt-install"
timeout 900 apt-get install -y -qq openfoam gmsh
echo "STEP installed"
export WM_PROJECT=OpenFOAM WM_PROJECT_VERSION=1912 WM_PROJECT_DIR=/usr/share/openfoam
export FOAM_APPBIN=/usr/bin FOAM_LIBBIN=/usr/lib FOAM_ETC=/usr/share/openfoam/etc
export FOAM_USER_APPBIN=/opt/phase15/user-bin FOAM_USER_LIBBIN=/opt/phase15/user-lib
export LD_LIBRARY_PATH="/usr/lib:/usr/lib/openmpi-system:${LD_LIBRARY_PATH:-}"
echo "FOAM_VERSION=${WM_PROJECT_VERSION} DIR=$WM_PROJECT_DIR"
mkdir -p "$FOAM_USER_APPBIN" "$FOAM_USER_LIBBIN"
command -v gmshToFoam; command -v rhoSimpleFoam; command -v gmsh
python3 /opt/phase15/phase15/optimization/phase15_inlet_worker.py \
  --output /opt/phase15/output \
  --work /opt/phase15/work \
  --run-budget-seconds 360
RUN_RC=0
exit "$RUN_RC"

