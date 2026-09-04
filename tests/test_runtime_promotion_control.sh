#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

export PROJECT_ID="test-project"
export PROJECT_NUMBER="123456789012"
export REGION="us-central1"
export DEPLOYER_SERVICE_ACCOUNT="test-deployer@test-project.iam.gserviceaccount.com"
export APPROVED_IMAGE="us-central1-docker.pkg.dev/test-project/polititrack/runtime-v2@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
export RUNTIME_SOURCE_REVISION="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
export EVIDENCE_DIR="${WORK}/evidence"

# shellcheck source=../deploy/runtime-v2/runtime_promotion_control.sh
source "${ROOT}/deploy/runtime-v2/runtime_promotion_control.sh"

fail() {
  echo "runtime promotion controller regression: $*" >&2
  exit 1
}

# The completed gcloud command response is the authoritative execution receipt.
cat > "${WORK}/admin-execute.json" <<'JSON'
{"metadata":{"name":"polititrack-admin-json123"}}
JSON
[[ "$(latest_execution_name polititrack-admin "${WORK}/admin-execute.json")" == "polititrack-admin-json123" ]] \
  || fail "command response execution receipt was not accepted"

# A receipt for another job must fail closed rather than being misattributed.
cat > "${WORK}/wrong-job.json" <<'JSON'
{"metadata":{"name":"polititrack-executive-json123"}}
JSON
if latest_execution_name polititrack-admin "${WORK}/wrong-job.json" >/dev/null 2>&1; then
  fail "cross-job execution receipt was accepted"
fi

# Stub only the Cloud SDK surfaces exercised by the receipt helpers.
gcloud() {
  if [[ "${1:-}" == "run" && "${2:-}" == "jobs" && "${3:-}" == "describe" ]]; then
    printf '%s-fallback123\n' "${4:?job name is required}"
    return 0
  fi
  if [[ "${1:-}" == "run" && "${2:-}" == "jobs" && "${3:-}" == "execute" ]]; then
    printf '{"metadata":{"name":"%s-test123"}}\n' "${4:?job name is required}"
    return 0
  fi
  if [[ "${1:-}" == "logging" && "${2:-}" == "read" ]]; then
    printf '%s\n' '[{"textPayload":"{\"heads\":{},\"latest_runs\":{}}"}]'
    return 0
  fi
  echo "unexpected gcloud invocation: $*" >&2
  return 64
}

sleep() {
  :
}

# The supported Cloud Run Job status field is a bounded fallback when a caller
# has no command-response file.
[[ "$(latest_execution_name polititrack-admin)" == "polititrack-admin-fallback123" ]] \
  || fail "supported Job status fallback did not resolve"

# These calls execute with nounset enabled. They exercise the previously unsafe
# dependent local declarations as well as command-response receipt propagation.
execute_admin_init
[[ "$(<"${EVIDENCE_DIR}/admin-init-execution.txt")" == "polititrack-admin-test123" ]] \
  || fail "admin initialization receipt was not persisted"

capture_status "${WORK}/status.json" baseline
jq -e '.heads == {} and .latest_runs == {}' "${WORK}/status.json" >/dev/null \
  || fail "status payload was not captured"
[[ "$(<"${EVIDENCE_DIR}/baseline-admin-execution.txt")" == "polititrack-admin-test123" ]] \
  || fail "status execution receipt was not persisted"

producer_execution="$(execute_producer legislative shadow cycle-1-sequence-1)"
[[ "${producer_execution}" == "polititrack-legislative-test123" ]] \
  || fail "producer execution receipt was not returned"
[[ -s "${EVIDENCE_DIR}/cycle-1-sequence-1-legislative-execute.json" ]] \
  || fail "producer command response was not retained"

if grep -Fq 'gcloud run jobs executions describe-latest' \
  "${ROOT}/deploy/runtime-v2/runtime_promotion_control.sh"; then
  fail "obsolete Cloud SDK execution lookup remains"
fi

printf '%s\n' "runtime promotion controller receipt regression passed"
