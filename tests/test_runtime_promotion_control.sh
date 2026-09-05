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
export GITHUB_REPOSITORY="test-owner/test-repository"
export CONTROL_REVISION="cccccccccccccccccccccccccccccccccccccccc"

# shellcheck source=../deploy/runtime-v2/runtime_promotion_control.sh
source "${ROOT}/deploy/runtime-v2/runtime_promotion_control.sh"
# shellcheck source=../deploy/runtime-v2/runtime_promotion_observed_state.sh
source "${ROOT}/deploy/runtime-v2/runtime_promotion_observed_state.sh"
# shellcheck source=../deploy/runtime-v2/phase4_reconciliation_control.sh
source "${ROOT}/deploy/runtime-v2/phase4_reconciliation_control.sh"

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
PRODUCER_EXECUTION_STATUS=0

# Stub only the Cloud SDK surfaces exercised by the receipt and status helpers.
gcloud() {
  if [[ "${1:-}" == "run" && "${2:-}" == "jobs" && "${3:-}" == "describe" ]]; then
    printf '%s-fallback123\n' "${4:?job name is required}"
    return 0
  fi
  if [[ "${1:-}" == "run" && "${2:-}" == "jobs" && "${3:-}" == "execute" ]]; then
    printf '{"metadata":{"name":"%s-test123"}}\n' "${4:?job name is required}"
    if [[ "${4}" != "polititrack-admin" && "${PRODUCER_EXECUTION_STATUS}" != "0" ]]; then
      return "${PRODUCER_EXECUTION_STATUS}"
    fi
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

PRODUCER_EXECUTION_STATUS=42
if execute_producer executive phase5_smoke smoke-failure >/dev/null 2>&1; then
  fail "failed producer command was accepted"
fi
[[ ! -e "${EVIDENCE_DIR}/smoke-failure-executive-execution.txt" ]] \
  || fail "failed producer command emitted an accepted execution receipt"

if grep -Fq 'gcloud run jobs executions describe-latest' \
  "${ROOT}/deploy/runtime-v2/runtime_promotion_control.sh"; then
  fail "obsolete Cloud SDK execution lookup remains"
fi

# GitHub rejects enable/disable calls for a workflow already in the requested
# state. Mixed observed states must therefore converge without issuing the
# invalid request that stopped the first Phase 5 promotion attempt.
declare -A WORKFLOW_STATES=(
  [legislative_trade_tracker_v2.yml]=active
  [executive_trade_tracker.yml]=active
  [ai_filing_analyst.yml]=disabled_manually
  [publish_trade_dashboard.yml]=active
)
GH_MUTATIONS=""
GH_RACE_DISABLE_WORKFLOW=""
GH_MUTATION_FAILURE_WORKFLOW=""
GH_MUTATION_FAILURE_WITH_TARGET_OUTPUT_WORKFLOW=""
GH_READ_FAILURE_WORKFLOW=""
GH_READ_FAILURE_OUTPUT=""

gh() {
  [[ "${1:-}" == "api" ]] || { echo "unexpected gh invocation: $*" >&2; return 64; }
  local endpoint="" arg workflow action=""
  for arg in "$@"; do
    case "${arg}" in
      repos/*/actions/workflows/*) endpoint="${arg}" ;;
    esac
  done
  [[ -n "${endpoint}" ]] || { echo "missing workflow endpoint: $*" >&2; return 64; }
  case "${endpoint}" in
    */enable) action="enable"; endpoint="${endpoint%/enable}" ;;
    */disable) action="disable"; endpoint="${endpoint%/disable}" ;;
  esac
  workflow="${endpoint##*/}"
  [[ -n "${WORKFLOW_STATES[${workflow}]+present}" ]] || {
    echo "unknown workflow: ${workflow}" >&2
    return 64
  }
  if [[ -z "${action}" ]]; then
    if [[ "${workflow}" == "${GH_READ_FAILURE_WORKFLOW}" ]]; then
      [[ -z "${GH_READ_FAILURE_OUTPUT}" ]] || printf '%s\n' "${GH_READ_FAILURE_OUTPUT}"
      return 22
    fi
    printf '%s\n' "${WORKFLOW_STATES[${workflow}]}"
    return 0
  fi
  if [[ "${workflow}" == "${GH_MUTATION_FAILURE_WITH_TARGET_OUTPUT_WORKFLOW}" ]]; then
    GH_READ_FAILURE_WORKFLOW="${workflow}"
    if [[ "${action}" == "disable" ]]; then
      GH_READ_FAILURE_OUTPUT="disabled_manually"
    else
      GH_READ_FAILURE_OUTPUT="active"
    fi
    return 22
  fi
  [[ "${workflow}" != "${GH_MUTATION_FAILURE_WORKFLOW}" ]] || return 22
  if [[ "${action}" == "disable" && "${workflow}" == "${GH_RACE_DISABLE_WORKFLOW}" ]]; then
    WORKFLOW_STATES[${workflow}]=disabled_manually
    GH_RACE_DISABLE_WORKFLOW=""
    return 22
  fi
  case "${action}:${WORKFLOW_STATES[${workflow}]}" in
    disable:active) WORKFLOW_STATES[${workflow}]=disabled_manually ;;
    enable:disabled_manually) WORKFLOW_STATES[${workflow}]=active ;;
    *) return 22 ;;
  esac
  GH_MUTATIONS+=" ${workflow}:${action}"
}

disable_legacy_workflows
for workflow in "${LEGACY_WORKFLOWS[@]}"; do
  [[ "${WORKFLOW_STATES[${workflow}]}" == "disabled_manually" ]] \
    || fail "${workflow} was not disabled"
done
[[ "${GH_MUTATIONS}" != *"ai_filing_analyst.yml:disable"* ]] \
  || fail "already-disabled workflow received an invalid disable request"

GH_MUTATIONS=""
disable_legacy_workflows
[[ -z "${GH_MUTATIONS}" ]] || fail "repeated disable issued a mutation"

# If another actor reaches the desired state between our read and write, the
# failed write is accepted only after the follow-up state read proves success.
WORKFLOW_STATES[legislative_trade_tracker_v2.yml]=active
GH_RACE_DISABLE_WORKFLOW=legislative_trade_tracker_v2.yml
ensure_legacy_workflow_state legislative_trade_tracker_v2.yml disabled_manually \
  || fail "concurrent disable did not converge"

jq -n '{
  "legislative_trade_tracker_v2.yml":"active",
  "executive_trade_tracker.yml":"active",
  "ai_filing_analyst.yml":"disabled_manually",
  "publish_trade_dashboard.yml":"active"
}' > "${LEGACY_STATE_FILE}"
restore_legacy_workflows_observed
[[ "${WORKFLOW_STATES[legislative_trade_tracker_v2.yml]}" == "active" ]] \
  || fail "Legislative observed state was not restored"
[[ "${WORKFLOW_STATES[executive_trade_tracker.yml]}" == "active" ]] \
  || fail "Executive observed state was not restored"
[[ "${WORKFLOW_STATES[ai_filing_analyst.yml]}" == "disabled_manually" ]] \
  || fail "AI observed disabled state was not preserved"
[[ "${WORKFLOW_STATES[publish_trade_dashboard.yml]}" == "active" ]] \
  || fail "dashboard observed state was not restored"

GH_MUTATIONS=""
restore_legacy_workflows_observed
[[ -z "${GH_MUTATIONS}" ]] || fail "repeated observed-state restore issued a mutation"

GH_MUTATIONS=""
enable_legacy_workflows
for workflow in "${LEGACY_WORKFLOWS[@]}"; do
  [[ "${WORKFLOW_STATES[${workflow}]}" == "active" ]] \
    || fail "${workflow} was not enabled"
done
[[ "${GH_MUTATIONS}" == " ai_filing_analyst.yml:enable" ]] \
  || fail "enable did not limit mutation to the disabled workflow"

GH_MUTATIONS=""
enable_legacy_workflows
[[ -z "${GH_MUTATIONS}" ]] || fail "repeated enable issued a mutation"

WORKFLOW_STATES[legislative_trade_tracker_v2.yml]=active
GH_MUTATION_FAILURE_WORKFLOW=legislative_trade_tracker_v2.yml
if ensure_legacy_workflow_state legislative_trade_tracker_v2.yml disabled_manually >/dev/null 2>&1; then
  fail "failed workflow mutation was accepted without target state"
fi
GH_MUTATION_FAILURE_WORKFLOW=""
[[ "${WORKFLOW_STATES[legislative_trade_tracker_v2.yml]}" == "active" ]] \
  || fail "failed workflow mutation changed state"

GH_MUTATION_FAILURE_WITH_TARGET_OUTPUT_WORKFLOW=legislative_trade_tracker_v2.yml
if ensure_legacy_workflow_state legislative_trade_tracker_v2.yml disabled_manually >/dev/null 2>&1; then
  fail "failed follow-up read output was accepted as workflow state"
fi
GH_MUTATION_FAILURE_WITH_TARGET_OUTPUT_WORKFLOW=""
GH_READ_FAILURE_WORKFLOW=""
GH_READ_FAILURE_OUTPUT=""

GH_READ_FAILURE_WORKFLOW=legislative_trade_tracker_v2.yml
if ensure_legacy_workflow_state legislative_trade_tracker_v2.yml disabled_manually >/dev/null 2>&1; then
  fail "unreadable workflow state was accepted"
fi
GH_READ_FAILURE_WORKFLOW=""

WORKFLOW_STATES[executive_trade_tracker.yml]=disabled_inactivity
if ensure_legacy_workflow_state executive_trade_tracker.yml active >/dev/null 2>&1; then
  fail "unsupported workflow state was accepted"
fi

WORKFLOW_STATES[executive_trade_tracker.yml]=disabled_manually
GH_MUTATIONS=""
jq -n '{
  "legislative_trade_tracker_v2.yml":"disabled_manually",
  "executive_trade_tracker.yml":"invalid",
  "ai_filing_analyst.yml":"disabled_manually",
  "publish_trade_dashboard.yml":"active"
}' > "${LEGACY_STATE_FILE}"
if restore_legacy_workflows_observed >/dev/null 2>&1; then
  fail "invalid observed-state descriptor was accepted"
fi
[[ -z "${GH_MUTATIONS}" ]] || fail "invalid observed state mutated a workflow"

# Exercise cleanup verifiers as conditionals, where Bash suppresses implicit
# errexit inside called functions. Every read must therefore be guarded by the
# controller itself rather than inferred from a later command's status.
IAM_JOB_POLICY_MODE=absent
IAM_PROJECT_POLICY_MODE=absent
IAM_VIEW_POLICY_MODE=absent
IAM_SERVICE_ACCOUNT_POLICY_MODE=absent
IAM_VIEW_READ_ALLOWED=true
IAM_VIEW_REMOVE_FAILURE=false
IAM_PROJECT_REMOVE_FAILURE=false
WEB_POLICY_MODE=absent
DESCRIBE_FAILURE_RESOURCE=""
SERVICE_ACCOUNT_GRANT_FAILURE=""
SCHEDULER_READ_FAILURE=""
SCHEDULER_MUTATION_FAILURE=""
IAM_CALLS=""
WEB_DIGEST="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
declare -A SCHEDULER_STATES=(
  [polititrack-legislative]=PAUSED
  [polititrack-executive]=PAUSED
  [polititrack-ai]=PAUSED
  [polititrack-dashboard]=PAUSED
  [polititrack-vault-lifecycle]=PAUSED
)

emit_policy() {
  local mode="$1" role="$2" member="$3"
  case "${mode}" in
    absent) printf '%s\n' '{"bindings":[]}' ;;
    present)
      jq -cn --arg role "${role}" --arg member "${member}" \
        '{bindings:[{role:$role,members:[$member]}]}'
      ;;
    malformed) printf '%s\n' '{' ;;
    read_failure) return 42 ;;
    read_failure_valid)
      printf '%s\n' '{"bindings":[]}'
      return 42
      ;;
    *) echo "unknown policy mode: ${mode}" >&2; return 64 ;;
  esac
}

gcloud() {
  local joined="$*" resource="${4:-}"
  if [[ "${1:-}" == "run" && "${2:-}" == "jobs" && "${3:-}" == "get-iam-policy" ]]; then
    emit_policy "${IAM_JOB_POLICY_MODE}" roles/run.jobsExecutorWithOverrides "${DEPLOYER_MEMBER}"
    return $?
  fi
  if [[ "${1:-}" == "projects" && "${2:-}" == "get-iam-policy" ]]; then
    emit_policy "${IAM_PROJECT_POLICY_MODE}" roles/logging.admin "${DEPLOYER_MEMBER}"
    return $?
  fi
  if [[ "${1:-}" == "logging" && "${2:-}" == "views" && "${3:-}" == "get-iam-policy" ]]; then
    IAM_CALLS+=" view-get"
    [[ "${IAM_VIEW_READ_ALLOWED}" == "true" ]] || return 42
    emit_policy "${IAM_VIEW_POLICY_MODE}" roles/logging.viewAccessor "${DEPLOYER_MEMBER}"
    return $?
  fi
  if [[ "${1:-}" == "iam" && "${2:-}" == "service-accounts" && "${3:-}" == "get-iam-policy" ]]; then
    emit_policy "${IAM_SERVICE_ACCOUNT_POLICY_MODE}" roles/iam.serviceAccountUser "${DEPLOYER_MEMBER}"
    return $?
  fi
  if [[ "${1:-}" == "run" && "${2:-}" == "services" && "${3:-}" == "get-iam-policy" ]]; then
    emit_policy "${WEB_POLICY_MODE}" roles/run.invoker allUsers
    return $?
  fi
  if [[ "${1:-}" == "run" && "${2:-}" == "jobs" && "${3:-}" == "describe" ]]; then
    printf '{"template":{"serviceAccount":"%s@test-project.iam.gserviceaccount.com"}}\n' "${resource}"
    [[ "${resource}" != "${DESCRIBE_FAILURE_RESOURCE}" ]] || return 42
    return 0
  fi
  if [[ "${1:-}" == "run" && "${2:-}" == "services" && "${3:-}" == "describe" ]]; then
    if [[ "${joined}" == *"value(status.url)"* ]]; then
      printf '%s\n' 'https://runtime.example.test'
    else
      printf '{"template":{"serviceAccount":"%s@test-project.iam.gserviceaccount.com"}}\n' "${resource}"
    fi
    [[ "${resource}" != "${DESCRIBE_FAILURE_RESOURCE}" ]] || return 42
    return 0
  fi
  if [[ "${1:-}" == "scheduler" && "${2:-}" == "jobs" && "${3:-}" == "describe" ]]; then
    printf '%s\n' "${SCHEDULER_STATES[${resource}]}"
    [[ "${resource}" != "${SCHEDULER_READ_FAILURE}" ]] || return 42
    return 0
  fi
  if [[ "${1:-}" == "scheduler" && "${2:-}" == "jobs" && ( "${3:-}" == "pause" || "${3:-}" == "resume" ) ]]; then
    [[ "${resource}" != "${SCHEDULER_MUTATION_FAILURE}" ]] || return 42
    if [[ "${3}" == "pause" ]]; then SCHEDULER_STATES[${resource}]=PAUSED; else SCHEDULER_STATES[${resource}]=ENABLED; fi
    return 0
  fi
  if [[ "${1:-}" == "logging" && "${2:-}" == "views" && "${3:-}" == "remove-iam-policy-binding" ]]; then
    IAM_CALLS+=" view-remove"
    [[ "${IAM_VIEW_REMOVE_FAILURE}" != "true" ]] || return 42
    case "${IAM_VIEW_POLICY_MODE}" in
      read_failure|read_failure_valid) ;;
      *) IAM_VIEW_POLICY_MODE=absent ;;
    esac
    return 0
  fi
  if [[ "${1:-}" == "projects" && "${2:-}" == "remove-iam-policy-binding" ]]; then
    IAM_CALLS+=" project-remove"
    [[ "${IAM_PROJECT_REMOVE_FAILURE}" != "true" ]] || return 42
    IAM_PROJECT_POLICY_MODE=absent
    IAM_VIEW_READ_ALLOWED=false
    return 0
  fi
  if [[ "${1:-}" == "run" && "${2:-}" == "jobs" && "${3:-}" == "remove-iam-policy-binding" ]]; then
    IAM_JOB_POLICY_MODE=absent
    return 0
  fi
  if [[ "${1:-}" == "iam" && "${2:-}" == "service-accounts" && "${3:-}" == "remove-iam-policy-binding" ]]; then
    return 0
  fi
  if [[ "${1:-}" == "iam" && "${2:-}" == "service-accounts" && "${3:-}" == "add-iam-policy-binding" ]]; then
    [[ "${resource}" != "${SERVICE_ACCOUNT_GRANT_FAILURE}" ]] || return 42
    return 0
  fi
  if [[ "${1:-}" == "run" && "${2:-}" == "jobs" && "${3:-}" == "add-iam-policy-binding" ]]; then
    IAM_JOB_POLICY_MODE=present
    return 0
  fi
  if [[ "${1:-}" == "projects" && "${2:-}" == "add-iam-policy-binding" ]]; then
    IAM_PROJECT_POLICY_MODE=present
    IAM_VIEW_READ_ALLOWED=true
    return 0
  fi
  if [[ "${1:-}" == "logging" && "${2:-}" == "views" && "${3:-}" == "add-iam-policy-binding" ]]; then
    IAM_VIEW_POLICY_MODE=present
    return 0
  fi
  if [[ "${1:-}" == "logging" && "${2:-}" == "read" ]]; then
    printf '%s\n' '[]'
    return 0
  fi
  echo "unexpected fail-closed gcloud invocation: $*" >&2
  return 64
}

verify_producer_scheduler_state PAUSED || fail "paused scheduler inventory was rejected"
SCHEDULER_READ_FAILURE=polititrack-executive
if verify_producer_scheduler_state PAUSED >/dev/null 2>&1; then
  fail "failed scheduler read with expected output was accepted"
fi
SCHEDULER_READ_FAILURE=""
SCHEDULER_STATES[polititrack-executive]=ENABLED
SCHEDULER_MUTATION_FAILURE=polititrack-executive
if pause_producer_schedulers >/dev/null 2>&1; then
  fail "failed scheduler pause was masked by later schedulers"
fi
SCHEDULER_MUTATION_FAILURE=""
SCHEDULER_STATES[polititrack-executive]=PAUSED

collect_service_accounts || fail "service-account inventory capture failed"
verify_service_account_inventory || fail "service-account inventory receipt was rejected"
inventory_sha="$(sha256sum "${SERVICE_ACCOUNTS_FILE}" | awk '{print $1}')"
DESCRIBE_FAILURE_RESOURCE=polititrack-executive
if collect_service_accounts >/dev/null 2>&1; then
  fail "failed service-account resource read was accepted"
fi
[[ "$(sha256sum "${SERVICE_ACCOUNTS_FILE}" | awk '{print $1}')" == "${inventory_sha}" ]] \
  || fail "failed service-account recollection replaced the valid inventory"
DESCRIBE_FAILURE_RESOURCE=""

IAM_SERVICE_ACCOUNT_POLICY_MODE=absent
verify_service_account_user_removed || fail "absent Service Account User bindings were rejected"
IAM_SERVICE_ACCOUNT_POLICY_MODE=read_failure_valid
if verify_service_account_user_removed >/dev/null 2>&1; then
  fail "failed Service Account User policy read was accepted"
fi
IAM_SERVICE_ACCOUNT_POLICY_MODE=present
if verify_service_account_user_removed >/dev/null 2>&1; then
  fail "present Service Account User binding was accepted"
fi
IAM_SERVICE_ACCOUNT_POLICY_MODE=absent

SERVICE_ACCOUNT_GRANT_FAILURE=polititrack-executive@test-project.iam.gserviceaccount.com
if grant_service_account_user >/dev/null 2>&1; then
  fail "partial Service Account User grant was accepted"
fi
SERVICE_ACCOUNT_GRANT_FAILURE=""

: > "${SERVICE_ACCOUNTS_FILE}"
if verify_service_account_user_removed >/dev/null 2>&1; then
  fail "empty service-account inventory was accepted"
fi
collect_service_accounts || fail "service-account inventory could not be restored"

rm -f "${LOGGING_VIEW_POLICY_RECEIPT}"
if verify_execution_authority_removed >/dev/null 2>&1; then
  fail "missing logging-view cleanup receipt was accepted"
fi
IAM_CALLS=""
IAM_VIEW_READ_ALLOWED=true
remove_logging_authority || fail "logging authority cleanup with readable policy failed"
verify_logging_view_removal_receipt || fail "logging-view cleanup receipt was rejected"
[[ "${IAM_CALLS}" == " view-remove view-get project-remove" ]] \
  || fail "logging authority was not verified before logging.admin removal"

cp "${LOGGING_VIEW_POLICY_RECEIPT}" "${WORK}/valid-logging-view-receipt.json"
jq '.project_id = "wrong-project"' "${LOGGING_VIEW_POLICY_RECEIPT}" \
  > "${LOGGING_VIEW_POLICY_RECEIPT}.tmp"
mv "${LOGGING_VIEW_POLICY_RECEIPT}.tmp" "${LOGGING_VIEW_POLICY_RECEIPT}"
IAM_VIEW_POLICY_MODE=read_failure_valid
IAM_VIEW_READ_ALLOWED=true
IAM_CALLS=""
if remove_logging_authority >/dev/null 2>&1; then
  fail "failed live view read with stale receipt was accepted"
fi
[[ "${IAM_CALLS}" == *" project-remove"* ]] \
  || fail "failed live view verification did not minimize logging.admin authority"
IAM_VIEW_POLICY_MODE=absent
IAM_VIEW_READ_ALLOWED=true
cp "${WORK}/valid-logging-view-receipt.json" "${LOGGING_VIEW_POLICY_RECEIPT}"

rm -f "${LOGGING_VIEW_POLICY_RECEIPT}"
IAM_VIEW_POLICY_MODE=present
IAM_PROJECT_POLICY_MODE=present
IAM_VIEW_READ_ALLOWED=true
IAM_VIEW_REMOVE_FAILURE=true
IAM_CALLS=""
if remove_logging_authority >/dev/null 2>&1; then
  fail "failed logging-view removal was accepted"
fi
[[ ! -e "${LOGGING_VIEW_POLICY_RECEIPT}" && "${IAM_CALLS}" == *" project-remove"* ]] \
  || fail "failed logging-view removal did not fail closed while minimizing project authority"
IAM_VIEW_REMOVE_FAILURE=false

IAM_VIEW_POLICY_MODE=present
IAM_PROJECT_POLICY_MODE=present
IAM_VIEW_READ_ALLOWED=true
IAM_PROJECT_REMOVE_FAILURE=true
IAM_CALLS=""
if remove_logging_authority >/dev/null 2>&1; then
  fail "failed logging.admin removal was accepted"
fi
verify_logging_view_removal_receipt \
  || fail "logging-view receipt was not retained across project-role removal failure"
[[ "${IAM_PROJECT_POLICY_MODE}" == "present" ]] \
  || fail "mock logging.admin binding unexpectedly disappeared after failed removal"
IAM_PROJECT_REMOVE_FAILURE=false
remove_logging_authority || fail "logging.admin cleanup retry did not reuse the valid receipt"

IAM_JOB_POLICY_MODE=read_failure_valid
if verify_execution_authority_removed >/dev/null 2>&1; then
  fail "failed execution-policy read with valid output was accepted"
fi
IAM_JOB_POLICY_MODE=present
if verify_execution_authority_removed >/dev/null 2>&1; then
  fail "present execution binding was accepted"
fi
IAM_JOB_POLICY_MODE=absent
IAM_PROJECT_POLICY_MODE=read_failure_valid
if verify_execution_authority_removed >/dev/null 2>&1; then
  fail "failed project-policy read with valid output was accepted"
fi
IAM_PROJECT_POLICY_MODE=absent
verify_execution_authority_removed || fail "verified temporary-authority absence was rejected"

grant_execution_authority || fail "mock execution-authority grant failed"
[[ ! -e "${LOGGING_VIEW_POLICY_RECEIPT}" ]] \
  || fail "authority grant did not invalidate the old cleanup receipt"
remove_logging_authority || fail "post-grant logging cleanup receipt was not recreated"

# Phase 4 uses the same receipt across the live step and its later terminal
# cleanup step, after logging.admin removal makes the view policy unreadable.
grant_phase4_status_authority || fail "mock Phase 4 status-authority grant failed"
[[ ! -e "${LOGGING_VIEW_POLICY_RECEIPT}" ]] \
  || fail "Phase 4 authority grant did not invalidate the old cleanup receipt"
[[ "${IAM_JOB_POLICY_MODE}:${IAM_PROJECT_POLICY_MODE}:${IAM_VIEW_POLICY_MODE}" == "present:present:present" ]] \
  || fail "Phase 4 authority grant did not establish the mocked bindings"
remove_phase4_status_authority || fail "Phase 4 authority cleanup failed"
[[ "${IAM_JOB_POLICY_MODE}:${IAM_PROJECT_POLICY_MODE}:${IAM_VIEW_POLICY_MODE}" == "absent:absent:absent" ]] \
  || fail "Phase 4 authority cleanup did not remove the mocked bindings"
[[ "${IAM_VIEW_READ_ALLOWED}" == "false" ]] \
  || fail "mock logging.admin removal did not revoke view-policy reads"
# Model the separate terminal step: functions are re-sourced while the receipt
# and cloud state persist in the job workspace.
source "${ROOT}/deploy/runtime-v2/runtime_promotion_control.sh"
source "${ROOT}/deploy/runtime-v2/phase4_reconciliation_control.sh"
remove_phase4_status_authority || fail "Phase 4 terminal cleanup could not reuse its receipt"
verify_phase4_status_authority_removed || fail "Phase 4 terminal cleanup receipt was rejected"

WEB_POLICY_MODE=absent
verify_web_private || fail "private web policy was rejected"
WEB_POLICY_MODE=read_failure_valid
if verify_web_private >/dev/null 2>&1; then
  fail "failed web-policy read with private-looking output was accepted"
fi
WEB_POLICY_MODE=malformed
if verify_web_private >/dev/null 2>&1; then
  fail "malformed web policy was accepted"
fi
WEB_POLICY_MODE=present
if verify_web_private >/dev/null 2>&1; then
  fail "public web policy was accepted as private"
fi
WEB_POLICY_MODE=absent

curl() {
  local url="${!#}" header_file="" index next
  for ((index=1; index <= $#; index++)); do
    if [[ "${!index}" == "--dump-header" ]]; then
      next=$((index + 1))
      header_file="${!next}"
    fi
  done
  case "${url}" in
    */healthz) printf '%s\n' '{"status":"bad","service":"polititrack-runtime-v2"}' ;;
    */readyz) printf '{"status":"ready","dashboard":true,"snapshot_sha256":"%s"}\n' "${WEB_DIGEST}" ;;
    */)
      printf 'X-PolitiTrack-Snapshot: %s\r\n' "${WEB_DIGEST}" > "${header_file}"
      printf '%s\n' '<html>ok</html>'
      ;;
    *) return 64 ;;
  esac
}
if verify_public_web "${WEB_DIGEST}" >/dev/null 2>&1; then
  fail "invalid health response was masked by later public-web checks"
fi

# Recovery dispatches are live producers. Persist exact acceptance before
# waiting, reuse it across cleanup calls, and never redispatch an ambiguous or
# partially accepted pair.
declare -A RECOVERY_RUN_IDS=(
  [legislative_trade_tracker_v2.yml]=101
  [executive_trade_tracker.yml]=201
)
declare -A RECOVERY_WORKFLOW_IDS=(
  [legislative_trade_tracker_v2.yml]=345003824
  [executive_trade_tracker.yml]=344663671
)
RECOVERY_RUN_READS_DIR="${WORK}/recovery-run-reads"
mkdir -p "${RECOVERY_RUN_READS_DIR}"
RECOVERY_DISPATCH_FAILURE=""
RECOVERY_RUN_ATTEMPT=1
RECOVERY_HEAD_SHA="${CONTROL_REVISION}"
RECOVERY_DISPATCH_LOG_FILE="${WORK}/recovery-dispatch.log"
: > "${RECOVERY_DISPATCH_LOG_FILE}"

emit_recovery_run() {
  local workflow="$1" status="$2" conclusion="${3:-}"
  local conclusion_json=null
  [[ -z "${conclusion}" ]] || conclusion_json="\"${conclusion}\""
  jq -cn \
    --argjson id "${RECOVERY_RUN_IDS[${workflow}]}" \
    --argjson workflow_id "${RECOVERY_WORKFLOW_IDS[${workflow}]}" \
    --argjson run_attempt "${RECOVERY_RUN_ATTEMPT}" \
    --arg workflow "${workflow}" \
    --arg status "${status}" \
    --argjson conclusion "${conclusion_json}" \
    --arg repository "${GITHUB_REPOSITORY}" \
    --arg control_revision "${RECOVERY_HEAD_SHA}" \
    '{id:$id, event:"workflow_dispatch", head_branch:"main",
      head_repository:{id:1349678672, full_name:$repository}, status:$status,
      workflow_id:$workflow_id, head_sha:$control_revision, run_attempt:$run_attempt,
      conclusion:$conclusion, html_url:("https://example.test/actions/runs/" + ($id|tostring)),
      path:(".github/workflows/" + $workflow)}'
}

gh() {
  [[ "${1:-}" == "api" ]] || { echo "unexpected recovery gh invocation: $*" >&2; return 64; }
  local endpoint="${2:-}" workflow run_id candidate count_file count joined="$*"
  if [[ "${endpoint}" == repos/*/actions/workflows/*/dispatches ]]; then
    [[ "${joined}" == *"--method POST"* &&
       "${joined}" == *"X-GitHub-Api-Version: 2026-03-10"* &&
       "${joined}" == *"-f ref=main"* ]] || {
      echo "exact-ID dispatch API contract is incomplete: ${joined}" >&2
      return 64
    }
    candidate="${endpoint#*/actions/workflows/}"
    workflow="${candidate%/dispatches}"
    printf ' %s' "${workflow}" >> "${RECOVERY_DISPATCH_LOG_FILE}"
    jq -cn \
      --argjson id "${RECOVERY_RUN_IDS[${workflow}]}" \
      --arg repository "${GITHUB_REPOSITORY}" \
      '{workflow_run_id:$id,
        run_url:("https://api.github.com/repos/" + $repository + "/actions/runs/" + ($id|tostring)),
        html_url:("https://github.com/" + $repository + "/actions/runs/" + ($id|tostring))}'
    [[ "${workflow}" != "${RECOVERY_DISPATCH_FAILURE}" ]] || return 22
    return 0
  fi
  if [[ "${endpoint}" == repos/*/actions/runs/* ]]; then
    run_id="${endpoint##*/}"
    workflow=""
    for candidate in "${!RECOVERY_RUN_IDS[@]}"; do
      if [[ "${RECOVERY_RUN_IDS[${candidate}]}" == "${run_id}" ]]; then
        workflow="${candidate}"
        break
      fi
    done
    [[ -n "${workflow}" ]] || return 64
    count_file="${RECOVERY_RUN_READS_DIR}/${run_id}"
    count=0
    [[ ! -f "${count_file}" ]] || count="$(<"${count_file}")"
    count=$((count + 1))
    printf '%s\n' "${count}" > "${count_file}"
    if (( count == 1 )); then
      emit_recovery_run "${workflow}" in_progress
    else
      emit_recovery_run "${workflow}" completed success
    fi
    return 0
  fi
  echo "unexpected recovery gh endpoint: ${endpoint}" >&2
  return 64
}

EVIDENCE_DIR="${WORK}/recovery-success"
mkdir -p "${EVIDENCE_DIR}"
dispatch_legacy_recovery || fail "tracked recovery dispatch did not complete"
[[ "$(<"${RECOVERY_DISPATCH_LOG_FILE}")" == " legislative_trade_tracker_v2.yml executive_trade_tracker.yml" ]] \
  || fail "tracked recovery did not issue exactly one dispatch per workflow"
jq -e \
  '.result == "legacy_recovery_runs_succeeded" and
   (.workflows | length) == 2 and
   all(.workflows[]; .result == "legacy_recovery_run_succeeded" and
       .run_attempt == 1 and .status == "completed" and .conclusion == "success")' \
  "${EVIDENCE_DIR}/legacy-recovery-dispatch.json" >/dev/null \
  || fail "tracked recovery completion receipt is invalid"
(( $(<"${RECOVERY_RUN_READS_DIR}/101") >= 2 )) \
  || fail "Legislative recovery completion was not awaited"
(( $(<"${RECOVERY_RUN_READS_DIR}/201") >= 2 )) \
  || fail "Executive recovery completion was not awaited"

dispatch_legacy_recovery || fail "completed recovery receipt was not reusable"
[[ "$(<"${RECOVERY_DISPATCH_LOG_FILE}")" == " legislative_trade_tracker_v2.yml executive_trade_tracker.yml" ]] \
  || fail "completed recovery cleanup redispatched a producer"

EVIDENCE_DIR="${WORK}/recovery-partial"
mkdir -p "${EVIDENCE_DIR}"
rm -f "${RECOVERY_RUN_READS_DIR}/101" "${RECOVERY_RUN_READS_DIR}/201"
RECOVERY_DISPATCH_FAILURE=executive_trade_tracker.yml
: > "${RECOVERY_DISPATCH_LOG_FILE}"
if dispatch_legacy_recovery >/dev/null 2>&1; then
  fail "partial recovery dispatch was accepted"
fi
if dispatch_legacy_recovery >/dev/null 2>&1; then
  fail "ambiguous recovery dispatch was retried and accepted"
fi
[[ "$(<"${RECOVERY_DISPATCH_LOG_FILE}")" == " legislative_trade_tracker_v2.yml executive_trade_tracker.yml" ]] \
  || fail "partial recovery cleanup duplicated a live producer dispatch"
jq -e '.result == "legacy_recovery_dispatch_accepted" and .run_id == 101' \
  "${EVIDENCE_DIR}/legacy-recovery-legislative.json" >/dev/null \
  || fail "accepted partial recovery run was not retained"
jq -e '.result == "legacy_recovery_dispatch_pending" and .run_id == null' \
  "${EVIDENCE_DIR}/legacy-recovery-executive.json" >/dev/null \
  || fail "ambiguous partial recovery dispatch was not retained fail-closed"

EVIDENCE_DIR="${WORK}/recovery-rerun-attempt"
mkdir -p "${EVIDENCE_DIR}"
RECOVERY_DISPATCH_FAILURE=""
RECOVERY_RUN_ATTEMPT=2
RECOVERY_HEAD_SHA="${CONTROL_REVISION}"
rm -f "${RECOVERY_RUN_READS_DIR}/101"
rerun_id="$(ensure_legacy_recovery_dispatch legislative_trade_tracker_v2.yml)" \
  || fail "exact recovery dispatch was not accepted for rerun-attempt test"
if wait_legacy_recovery_success legislative_trade_tracker_v2.yml "${rerun_id}" >/dev/null 2>&1; then
  fail "a later rerun attempt was accepted as the exact dispatched recovery attempt"
fi
jq -e '.result == "legacy_recovery_dispatch_accepted" and .run_id == 101' \
  "${EVIDENCE_DIR}/legacy-recovery-legislative.json" >/dev/null \
  || fail "rejected rerun attempt overwrote the exact dispatch receipt"

EVIDENCE_DIR="${WORK}/recovery-head-drift"
mkdir -p "${EVIDENCE_DIR}"
RECOVERY_RUN_ATTEMPT=1
RECOVERY_HEAD_SHA="dddddddddddddddddddddddddddddddddddddddd"
rm -f "${RECOVERY_RUN_READS_DIR}/101"
drift_id="$(ensure_legacy_recovery_dispatch legislative_trade_tracker_v2.yml)" \
  || fail "exact recovery dispatch was not accepted for head-drift test"
if wait_legacy_recovery_success legislative_trade_tracker_v2.yml "${drift_id}" >/dev/null 2>&1; then
  fail "recovery from a revision other than the certified control revision was accepted"
fi
jq -e '.result == "legacy_recovery_dispatch_accepted" and .run_id == 101' \
  "${EVIDENCE_DIR}/legacy-recovery-legislative.json" >/dev/null \
  || fail "rejected head-drift run overwrote the exact dispatch receipt"

printf '%s\n' "runtime promotion controller receipt and status regression passed"
