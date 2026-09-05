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
  if ! gcloud run jobs execute "${ADMIN_JOB}" --project "${PROJECT_ID}" --region "${REGION}" \
    --args=-m,runtime_v2,status --wait --format=json > "${execute_result}"; then
    echo "Runtime v2 status execution failed." >&2
    return 1
  fi
  if ! execution="$(latest_execution_name "${ADMIN_JOB}" "${execute_result}")"; then
    return 1
  fi
  [[ -n "${execution}" ]] || { echo "Unable to resolve admin status execution." >&2; return 1; }
  printf '%s\n' "${execution}" > "${EVIDENCE_DIR}/${stem}-admin-execution.txt"
  logs="${EVIDENCE_DIR}/${stem}-admin-logs.json"
  payload=""
  for attempt in $(seq 1 24); do
    if ! gcloud logging read \
      "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"${ADMIN_JOB}\" AND resource.labels.location=\"${REGION}\" AND labels.\"run.googleapis.com/execution_name\"=\"${execution}\"" \
      --project "${PROJECT_ID}" --freshness=2h --limit=1000 --order=asc --format=json > "${logs}"; then
      sleep 5
      continue
    fi
    if ! payload="$(jq -c '
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
    ' "${logs}")"; then
      payload=""
    fi
    [[ -n "${payload}" ]] && break
    sleep 5
  done
  [[ -n "${payload}" ]] || { echo "No Runtime v2 status payload was emitted by ${execution}." >&2; return 1; }
  printf '%s\n' "${payload}" | jq . > "${output}"
}

configure_runtime() {
  local mode="$1" job status=0 cleanup_status=0
  configure_runtime_v1 "${mode}" || return 1
  if ! grant_service_account_user; then
    remove_service_account_user
    verify_service_account_user_removed || cleanup_status=1
    (( cleanup_status == 0 )) || echo "Temporary actAs cleanup could not be verified after source-pin grant failure." >&2
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
  verify_service_account_user_removed || cleanup_status=1
  (( status == 0 )) || return "${status}"
  if (( cleanup_status != 0 )); then
    echo "Runtime source pinning completed but temporary actAs cleanup is unverified." >&2
    return 1
  fi
}

verify_runtime_configuration() {
  local mode="$1" job
  verify_runtime_configuration_v1 "${mode}" || return 1
  for job in "${PRODUCER_JOBS[@]}"; do
    if ! gcloud run jobs describe "${job}" --project "${PROJECT_ID}" --region "${REGION}" --format=json \
      > "${RESOURCE_DIR}/source-${job}.json"; then
      echo "Unable to verify approved source revision on ${job}." >&2
      return 1
    fi
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
  : > "${ndjson}" || return 1
  for workflow in "${LEGACY_WORKFLOWS[@]}"; do
    if ! state="$(legacy_workflow_state "${workflow}")"; then
      echo "Unable to capture legacy workflow ${workflow}." >&2
      return 1
    fi
    [[ "${state}" == "active" || "${state}" == "disabled_manually" ]] || {
      echo "Unsupported legacy workflow state ${workflow}=${state}." >&2
      return 1
    }
    jq -cn --arg workflow "${workflow}" --arg state "${state}" \
      '{key:$workflow,value:$state}' >> "${ndjson}" || return 1
  done
  jq -s 'from_entries' "${ndjson}" > "${LEGACY_STATE_FILE}" || return 1
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
    if ! expected="$(jq -r --arg workflow "${workflow}" '.[$workflow] // empty' "${LEGACY_STATE_FILE}")"; then
      echo "Unable to read observed state for ${workflow}." >&2
      return 1
    fi
    if ! actual="$(legacy_workflow_state "${workflow}")"; then
      echo "Unable to verify current state for ${workflow}." >&2
      return 1
    fi
    [[ -n "${expected}" && "${actual}" == "${expected}" ]] || {
      echo "Legacy workflow ${workflow} is ${actual}, expected observed state ${expected}." >&2
      return 1
    }
  done
}

restore_legacy_workflows_observed() {
  [[ -f "${LEGACY_STATE_FILE}" ]] || { echo "Observed legacy workflow state is missing." >&2; return 1; }
  local workflow expected
  if ! jq -e \
    '(keys | sort) ==
       (["legislative_trade_tracker_v2.yml", "executive_trade_tracker.yml",
         "ai_filing_analyst.yml", "publish_trade_dashboard.yml"] | sort) and
     all(.[]; . == "active" or . == "disabled_manually")' \
    "${LEGACY_STATE_FILE}" >/dev/null; then
    echo "Observed legacy workflow inventory is not exact." >&2
    return 1
  fi
  for workflow in "${LEGACY_WORKFLOWS[@]}"; do
    if ! expected="$(jq -r --arg workflow "${workflow}" '.[$workflow] // empty' "${LEGACY_STATE_FILE}")"; then
      echo "Unable to read observed state for ${workflow}." >&2
      return 1
    fi
    case "${expected}" in
      active|disabled_manually) ;;
      *)
        echo "Cannot restore unsupported legacy workflow state ${workflow}=${expected}." >&2
        return 1
        ;;
    esac
  done
  for workflow in "${LEGACY_WORKFLOWS[@]}"; do
    expected="$(jq -r --arg workflow "${workflow}" '.[$workflow]' "${LEGACY_STATE_FILE}")" || return 1
    ensure_legacy_workflow_state "${workflow}" "${expected}" || return 1
  done
  verify_legacy_workflows_match_observed
}
