#!/usr/bin/env bash
# Bounded one-VM Phase-4 runner. Starts no sidecar/second VM and auto-terminates
# through the GCE max-run-duration set by the operator.
set -Eeuo pipefail
LOG=/var/log/phase4-ross.log
mkdir -p /var/log
exec > >(tee -a "$LOG") 2>&1
MD='Metadata-Flavor: Google'
ATTR='http://metadata.google.internal/computeMetadata/v1/instance/attributes'
TOKEN_URL='http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token'

attr() { curl -fsS -H "$MD" "$ATTR/$1"; }
urlencode() { python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1],safe=""))' "$1"; }
BUCKET="$(attr BUCKET)"
PLAN_OBJECT="$(attr PLAN_OBJECT)"
RUNNER_OBJECT="$(attr RUNNER_OBJECT)"
RESULT_OBJECT="$(attr RESULT_OBJECT)"
ARCHIVE_OBJECT="$(attr ARCHIVE_OBJECT)"
FAILURE_OBJECT="$(attr FAILURE_OBJECT)"
REPO_COMMIT="$(attr REPO_COMMIT)"

token() {
  curl -fsS -H "$MD" "$TOKEN_URL" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
}
gcs_get() {
  local object token_value
  object="$(urlencode "$1")"
  token_value="$(token)"
  curl -fsS -H "Authorization: Bearer $token_value" \
    "https://storage.googleapis.com/storage/v1/b/${BUCKET}/o/${object}?alt=media" -o "$2"
}
gcs_put() {
  local file="$1" name="$2" object token_value
  object="$(urlencode "$name")"
  token_value="$(token)"
  curl -fsS -X POST --data-binary "@$file" \
    -H "Authorization: Bearer $token_value" \
    -H "Content-Type: application/octet-stream" \
    "https://storage.googleapis.com/upload/storage/v1/b/${BUCKET}/o?uploadType=media&name=${object}" >/dev/null
}
failed() {
  local rc=$?
  echo "PHASE4_WORKER_FAILED rc=$rc at=$(date -u +%FT%TZ)"
  if [ -n "${FAILURE_OBJECT:-}" ] && [ -f "$LOG" ]; then
    gcs_put "$LOG" "$FAILURE_OBJECT" || true
  fi
  exit "$rc"
}
trap failed ERR

echo "PHASE4_WORKER_START utc=$(date -u +%FT%TZ) commit=$REPO_COMMIT"
mkdir -p /opt/phase4 /opt/repo
gcs_get "$PLAN_OBJECT" /opt/phase4/phase4_ross_job_plan.json
gcs_get "$RUNNER_OBJECT" /opt/phase4/phase4_gcp_ross_runner.py

export DEBIAN_FRONTEND=noninteractive
timeout 240 apt-get update -qq
timeout 240 apt-get install -y -qq git curl ca-certificates software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
timeout 240 apt-get update -qq
timeout 240 apt-get install -y -qq python3.12 python3.12-venv
curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

git clone --filter=blob:none --no-checkout \
  https://github.com/iamdarshg/aero-multiphysics-workbench.git /opt/repo
git -C /opt/repo fetch --depth 1 origin "$REPO_COMMIT"
git -C /opt/repo checkout --detach FETCH_HEAD
test "$(git -C /opt/repo rev-parse HEAD)" = "$REPO_COMMIT"

export UV_PROJECT_ENVIRONMENT=/opt/phase4-venv
timeout 600 uv sync --frozen --directory /opt/repo/services/api
/opt/phase4-venv/bin/python - <<'PY'
import importlib.metadata as md
import ross
assert hasattr(ross, "Material"), f"wrong ROSS module loaded: {ross.__file__}"
print("ROSS_READY", md.version("ross-rotordynamics"), ross.__file__)
PY

export NUMBA_DISABLE_JIT=1
/opt/phase4-venv/bin/python /opt/phase4/phase4_gcp_ross_runner.py \
  --workbench /opt/repo \
  --plan /opt/phase4/phase4_ross_job_plan.json \
  --job-root /opt/phase4/jobs \
  --output /opt/phase4/output

gcs_put /opt/phase4/output/phase4_ross_evidence.json "$RESULT_OBJECT"
gcs_put /opt/phase4/output/phase4_ross_cases.tar.gz "$ARCHIVE_OBJECT"
printf 'PHASE4_DONE %s\n' "$(date -u +%FT%TZ)" > /opt/phase4/DONE
gcs_put /opt/phase4/DONE "${RESULT_OBJECT%.json}-DONE.txt"
echo "PHASE4_WORKER_COMPLETE utc=$(date -u +%FT%TZ)"
trap - ERR
