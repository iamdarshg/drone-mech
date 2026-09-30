#!/usr/bin/env bash
set -Eeuo pipefail

LOG=/var/log/phase13-openfoam-worker.log
ROOT=/opt/phase13
mkdir -p /var/log "$ROOT"
exec > >(tee -a "$LOG") 2>&1

MD='Metadata-Flavor: Google'
ATTR='http://metadata.google.internal/computeMetadata/v1/instance/attributes'
META='http://metadata.google.internal/computeMetadata/v1'
TOKEN_URL="$META/instance/service-accounts/default/token"
attr() { curl -fsS --max-time 4 -H "$MD" "$ATTR/$1"; }
urlencode() { python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1],safe=""))' "$1"; }
token() { curl -fsS --max-time 5 -H "$MD" "$TOKEN_URL" | python3 -c 'import json,sys;print(json.load(sys.stdin)["access_token"])'; }
gcs_get() {
  local obj tok
  obj="$(urlencode "$1")"
  tok="$(token)"
  curl -fsS --max-time 35 -H "Authorization: Bearer $tok" \
    "https://storage.googleapis.com/storage/v1/b/${BUCKET}/o/${obj}?alt=media" -o "$2"
}
gcs_put() {
  local file="$1" name="$2" obj tok
  [ -f "$file" ] || return 0
  obj="$(urlencode "$name")"
  tok="$(token)"
  curl -fsS --max-time 45 -X POST --data-binary "@$file" \
    -H "Authorization: Bearer $tok" -H 'Content-Type: application/octet-stream' \
    "https://storage.googleapis.com/upload/storage/v1/b/${BUCKET}/o?uploadType=media&name=${obj}" >/dev/null
}

BUCKET="$(attr BUCKET)"
BUNDLE_OBJECT="$(attr BUNDLE_OBJECT)"
RESULT_OBJECT="$(attr RESULT_OBJECT)"
FINISH_OBJECT="$(attr FINISH_OBJECT)"
MAX_ARTIFACT_BYTES="$(attr MAX_ARTIFACT_BYTES)"
INSTANCE_NAME="$(curl -fsS --max-time 4 -H "$MD" "$META/instance/name")"
# The metadata server does not expose a creation-timestamp leaf on every image.
# The controller records the authoritative Compute API timestamps separately.
CREATED_AT="$(curl -fsS --max-time 4 -H "$MD" "$META/instance/creation-timestamp" 2>/dev/null || true)"
[ -n "$CREATED_AT" ] || CREATED_AT="$(date -u +%FT%TZ)"
RUN_RC=1

finish() {
  local rc=$?
  local artifact_size=0
  set +e
  mkdir -p "$ROOT/output"
  cp "$LOG" "$ROOT/output/worker_startup.log" 2>/dev/null
  if [ -d "$ROOT/output" ]; then
    tar -czf "$ROOT/phase13-output.tar.gz" -C "$ROOT/output" .
    local size
    size="$(stat -c '%s' "$ROOT/phase13-output.tar.gz" 2>/dev/null || echo 999999999)"
    if [ "$size" -le "$MAX_ARTIFACT_BYTES" ]; then
      gcs_put "$ROOT/phase13-output.tar.gz" "$RESULT_OBJECT"
      artifact_size="$size"
    else
      echo "PHASE13_ARTIFACT_LIMIT_EXCEEDED bytes=$size cap=$MAX_ARTIFACT_BYTES"
      mkdir -p "$ROOT/compact-output/caseLogs"
      cp "$LOG" "$ROOT/compact-output/worker_startup.log" 2>/dev/null
      cp "$ROOT/output/phase13_solver_receipt.json" "$ROOT/compact-output/" 2>/dev/null
      cp -r "$ROOT/output/caseLogs/." "$ROOT/compact-output/caseLogs/" 2>/dev/null
      printf '{"cfdFields":null,"reason":"field archive exceeded the 15 MB ancillary transfer cap"}\n' \
        > "$ROOT/compact-output/cfd_fields_disposition.json"
      tar -czf "$ROOT/phase13-output-compact.tar.gz" -C "$ROOT/compact-output" .
      local compact_size
      compact_size="$(stat -c '%s' "$ROOT/phase13-output-compact.tar.gz" 2>/dev/null || echo 999999999)"
      if [ "$compact_size" -le "$MAX_ARTIFACT_BYTES" ]; then
        gcs_put "$ROOT/phase13-output-compact.tar.gz" "$RESULT_OBJECT"
        artifact_size="$compact_size"
      fi
    fi
  fi
  printf '{"instance":"%s","exitCode":%s,"createdAtUtc":"%s","finishedAtUtc":"%s","artifactBytes":%s}\n' \
    "$INSTANCE_NAME" "$rc" "$CREATED_AT" "$(date -u +%FT%TZ)" \
    "$artifact_size" > "$ROOT/finish.json"
  gcs_put "$ROOT/finish.json" "$FINISH_OBJECT"
  echo "PHASE13_WORKER_FINISH rc=$rc utc=$(date -u +%FT%TZ)"
  trap - EXIT
  exit "$rc"
}
trap finish EXIT

echo "PHASE13_WORKER_START instance=$INSTANCE_NAME created=$CREATED_AT utc=$(date -u +%FT%TZ)"
gcs_get "$BUNDLE_OBJECT" "$ROOT/input.tar.gz"
tar -xzf "$ROOT/input.tar.gz" -C "$ROOT"

export DEBIAN_FRONTEND=noninteractive
timeout -s TERM 75 apt-get update -qq
timeout -s TERM 180 apt-get install -y -qq openfoam

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
export FOAM_USER_APPBIN="$ROOT/user-bin"
export FOAM_USER_LIBBIN="$ROOT/user-lib"
export LD_LIBRARY_PATH="/usr/lib:/usr/lib/openmpi-system:${LD_LIBRARY_PATH:-}"
mkdir -p "$FOAM_USER_APPBIN" "$FOAM_USER_LIBBIN"
command -v gmshToFoam
command -v changeDictionary
command -v checkMesh
command -v rhoSimpleFoam

python3 "$ROOT/phase13/optimization/phase13_openfoam_worker.py" \
  --case-root "$ROOT/phase13/cases" \
  --config "$ROOT/phase13/configs/phase13_split_inlet_recovery.json" \
  --output "$ROOT/output" \
  --instance-name "$INSTANCE_NAME" \
  --vm-created-at "$CREATED_AT" \
  --runner-budget-seconds 300
RUN_RC=0
exit "$RUN_RC"
