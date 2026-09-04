#!/usr/bin/env bash
# Phase 4/5 overlays that preserve the exact observed legacy workflow state and
# permanently pin the immutable Runtime source revision on every producer job.

: "${LEGACY_STATE_FILE:=${EVIDENCE_DIR}/legacy-workflow-states.json}"

# Keep the reviewed v1 implementations available, then strengthen them without
# duplicating the rest of the controller. Execution receipts remain owned by
# runtime_promotion_control.sh so both Phase 4 and Phase 5 use one implementation.
eval "$(declare -f configure_runtime | sed '1s/configure_runtime/configure_runtime_v1/')"
eval "$(declare -f verify_runtime_configuration | sed '1s/verify_runtime_configuration/verify_runtime_configuration_v1/')"

# Cloud Logging emits structured Python log records as jsonPayload, while older
# Runtime images and local tests may expose the same JSON through textPayload.
# Accept either representation, preferring the last complete status record for
# the exact execution already bound by the shared receipt controller.
capture_status() {
  local output="$1"
  local stem="$2"
  local execute_result="${EVIDENCE_DIR}/${stem}-admin-execute.json"
  local execution logs payload
  gcloud run jobs execute "${ADMIN_JOB}" --project "${PROJECT_ID}" --region "${REGION}" \
    --args=-m,runtime_v2,status --wait --format=json > "${execute_result}"
  execution="$(latest_execution_name "${ADMIN_JOB}" "${execute_result}")"
  [[ -n "${execution}" ]] || { echo "Unable to resolve admin status execution." >&2; return 1; }
  printf '%s\n' "${execution}" > "${EVIDENCE_DIR}/${stem}-admin-execution.txt"
  logs="${EVIDENCE_DIR}/${stem}-admin-logs.json"
  payload=""
  for attempt in $(seq 1 24); do
    gcloud logging read \
      "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"${ADMIN_JOB}\" AND resource.labels.location=\"${REGION}\" AND labels.\"run.googleapis.com/execution_name\"=\"${execution}\"" \
      --project "${PROJECT_ID}" --freshness=2h --limit=1000 --order=asc --format=json > "${logs}"
    payload="$(jq -c '
      [
        .[]
        | (
            (.jsonPayload?
             | select(type == "object" and has("heads") and has("latest_runs"))),
            (.textPayload?
             | select(type == "string")
             | fromjson?
             | select(type == "object" and has("heads") and has("latest_runs")))
          )
      ][-1] // empty
    ' "${logs}")"
    [[ -n "${payload}" ]] && break
    sleep 5
  done
  [[ -n "${payload}" ]] || { echo "No Runtime v2 status payload was emitted by ${execution}." >&2; return 1; }
  printf '%s\n' "${payload}" | jq . > "${output}"
}

configure_runtime() {
  local mode="$1" job status=0
  configure_runtime_v1 "${mode}" || return 1
  if ! grant_service_account_user; then
    remove_service_account_user
    return 1
  fi
  for job in "${PRODUCER_JOBS[@]}"; do
    if ! gcloud run jobs update "${job}" --project "${PROJECT_ID}" --region "${REGION}" \
      --update-env-vars "SOURCE_REVISION=${RUNTIME_SOURCE_REVISION}" --quiet --format=none; then
      status=1
      break
    fi
  done
  remove_service_account_user
  (( status == 0 )) || return "${status}"
  verify_service_account_user_removed
}

verify_runtime_configuration() {
  local mode="$1" job
  verify_runtime_configuration_v1 "${mode}"
  for job in "${PRODUCER_JOBS[@]}"; do
    gcloud run jobs describe "${job}" --project "${PROJECT_ID}" --region "${REGION}" --format=json \
      > "${RESOURCE_DIR}/source-${job}.json"
    jq -e --arg source "${RUNTIME_SOURCE_REVISION}" \
      '[.. | objects | select(.name? == "SOURCE_REVISION") | .value?] | any(. == $source)' \
      "${RESOURCE_DIR}/source-${job}.json" >/dev/null || {
        echo "${job} does not persist the approved source revision." >&2
        return 1
      }
  done
}

capture_legacy_workflow_states() {
  local workflow state ndjson="${EVIDENCE_DIR}/legacy-workflow-states.ndjson"
  : > "${ndjson}"
  for workflow in "${LEGACY_WORKFLOWS[@]}"; do
    state="$(legacy_workflow_state "${workflow}")"
    [[ "${state}" == "active" || "${state}" == "disabled_manually" ]] || {
      echo "Unsupported legacy workflow state ${workflow}=${state}." >&2
      return 1
    }
    jq -cn --arg workflow "${workflow}" --arg state "${state}" '{key:$workflow,value:$state}' >> "${ndjson}"
  done
  jq -s 'from_entries' "${ndjson}" > "${LEGACY_STATE_FILE}"
  jq -e \
    '.["legislative_trade_tracker_v2.yml"] == "active" and
     .["executive_trade_tracker.yml"] == "active" and
     (keys | sort) == (["legislative_trade_tracker_v2.yml","executive_trade_tracker.yml","ai_filing_analyst.yml","publish_trade_dashboard.yml"] | sort)' \
    "${LEGACY_STATE_FILE}" >/dev/null || {
      echo "The two legacy collector workflows are not available as the rollback route." >&2
      return 1
    }
}

verify_legacy_workflows_match_observed() {
  [[ -f "${LEGACY_STATE_FILE}" ]] || { echo "Observed legacy workflow state is missing." >&2; return 1; }
  local workflow expected actual
  for workflow in "${LEGACY_WORKFLOWS[@]}"; do
    expected="$(jq -r --arg workflow "${workflow}" '.[$workflow] // empty' "${LEGACY_STATE_FILE}")"
    actual="$(legacy_workflow_state "${workflow}")"
    [[ -n "${expected}" && "${actual}" == "${expected}" ]] || {
      echo "Legacy workflow ${workflow} is ${actual}, expected observed state ${expected}." >&2
      return 1
    }
  done
}

restore_legacy_workflows_observed() {
  [[ -f "${LEGACY_STATE_FILE}" ]] || { echo "Observed legacy workflow state is missing." >&2; return 1; }
  local workflow expected
  for workflow in "${LEGACY_WORKFLOWS[@]}"; do
    expected="$(jq -r --arg workflow "${workflow}" '.[$workflow] // empty' "${LEGACY_STATE_FILE}")"
    case "${expected}" in
      active)
        gh api --method PUT "repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow}/enable" >/dev/null
        ;;
      disabled_manually)
        gh api --method PUT "repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow}/disable" >/dev/null
        ;;
      *)
        echo "Cannot restore unsupported legacy workflow state ${workflow}=${expected}." >&2
        return 1
        ;;
    esac
  done
  verify_legacy_workflows_match_observed
}
