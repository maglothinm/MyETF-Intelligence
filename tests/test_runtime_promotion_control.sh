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
# shellcheck source=../deploy/runtime-v2/runtime_promotion_observed_state.sh
source "${ROOT}/deploy/runtime-v2/runtime_promotion_observed_state.sh"

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

STATUS_LOG_FORMAT=structured

# Stub only the Cloud SDK surfaces exercised by the receipt and status helpers.
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
    case "${STATUS_LOG_FORMAT}" in
      structured)
        printf '%s\n' '[{"jsonPayload":{"heads":[],"latest_runs":[]}}]'
        ;;
      text)
        printf '%s\n' '[{"textPayload":"{\"heads\":[],\"latest_runs\":[]}"}]'
        ;;
      *)
        echo "unexpected STATUS_LOG_FORMAT=${STATUS_LOG_FORMAT}" >&2
        return 65
        ;;
    esac
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

capture_status "${WORK}/structured-status.json" structured
jq -e '.heads == [] and .latest_runs == []' "${WORK}/structured-status.json" >/dev/null \
  || fail "structured jsonPayload status was not captured"
[[ "$(<"${EVIDENCE_DIR}/structured-admin-execution.txt")" == "polititrack-admin-test123" ]] \
  || fail "structured status execution receipt was not persisted"

STATUS_LOG_FORMAT=text
capture_status "${WORK}/text-status.json" text-fallback
jq -e '.heads == [] and .latest_runs == []' "${WORK}/text-status.json" >/dev/null \
  || fail "legacy textPayload status was not captured"
[[ "$(<"${EVIDENCE_DIR}/text-fallback-admin-execution.txt")" == "polititrack-admin-test123" ]] \
  || fail "text status execution receipt was not persisted"

producer_execution="$(execute_producer legislative shadow cycle-1-sequence-1)"
[[ "${producer_execution}" == "polititrack-legislative-test123" ]] \
  || fail "producer execution receipt was not returned"
[[ -s "${EVIDENCE_DIR}/cycle-1-sequence-1-legislative-execute.json" ]] \
  || fail "producer command response was not retained"

if grep -Fq 'gcloud run jobs executions describe-latest' \
  "${ROOT}/deploy/runtime-v2/runtime_promotion_control.sh"; then
  fail "obsolete Cloud SDK execution lookup remains"
fi

printf '%s\n' "runtime promotion controller receipt and status regression passed"
