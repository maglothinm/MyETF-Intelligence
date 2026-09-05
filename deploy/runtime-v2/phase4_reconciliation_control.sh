#!/usr/bin/env bash
# Narrow, sourceable authority helpers for the read-only Phase 4 status capture.

grant_phase4_status_authority() {
  rm -f "${LOGGING_VIEW_POLICY_RECEIPT}" || return 1
  gcloud run jobs add-iam-policy-binding "${ADMIN_JOB}" --project "${PROJECT_ID}" --region "${REGION}" \
    --member "${DEPLOYER_MEMBER}" --role roles/run.jobsExecutorWithOverrides --quiet --format=none || return 1
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member "${DEPLOYER_MEMBER}" \
    --role roles/logging.admin --condition=None --quiet --format=none || return 1
  gcloud logging views add-iam-policy-binding _Default --bucket _Default --location global \
    --project "${PROJECT_ID}" --member "${DEPLOYER_MEMBER}" --role roles/logging.viewAccessor \
    --quiet --format=none || return 1
  for attempt in $(seq 1 18); do
    if gcloud logging read 'resource.type="cloud_run_job"' --project "${PROJECT_ID}" --limit=1 --format=json >/dev/null 2>&1; then
      return 0
    fi
    sleep 10
  done
  echo "Temporary Phase 4 status authority did not become effective." >&2
  return 1
}

remove_phase4_status_authority() {
  local status=0
  gcloud run jobs remove-iam-policy-binding "${ADMIN_JOB}" --project "${PROJECT_ID}" --region "${REGION}" \
    --member "${DEPLOYER_MEMBER}" --role roles/run.jobsExecutorWithOverrides --quiet >/dev/null 2>&1 || true
  remove_logging_authority || status=1
  verify_phase4_status_authority_removed || status=1
  return "${status}"
}

verify_phase4_status_authority_removed() {
  local policy
  if ! policy="$(gcloud run jobs get-iam-policy "${ADMIN_JOB}" --project "${PROJECT_ID}" --region "${REGION}" --format=json)"; then
    echo "Unable to verify Phase 4 admin execution-authority cleanup." >&2
    return 1
  fi
  if ! jq -e --arg member "${DEPLOYER_MEMBER}" \
    'type == "object" and
     ([.bindings[]? | select(.role == "roles/run.jobsExecutorWithOverrides") | .members[]?] | any(. == $member) | not)' \
    <<<"${policy}" >/dev/null; then
    echo "Temporary Phase 4 admin execution-authority cleanup is unverified." >&2
    return 1
  fi
  verify_logging_authority_removed
}

# Preserve the shared receipt lookup while making the Phase 5 smoke execution
# fail closed. A failed `gcloud run jobs execute --wait` may still write a JSON
# response; it must never be mistaken for a successful producer receipt.
execute_producer() {
  local logical_name="$1"
  local trigger="$2"
  local stem="$3"
  local job="polititrack-${logical_name}"
  local execute_result="${EVIDENCE_DIR}/${stem}-${logical_name}-execute.json"
  local execute_status=0

  gcloud run jobs execute "${job}" --project "${PROJECT_ID}" --region "${REGION}" \
    --update-env-vars "POLITITRACK_TRIGGER_SOURCE=${trigger},SOURCE_REVISION=${RUNTIME_SOURCE_REVISION}" \
    --wait --format=json > "${execute_result}" || execute_status=$?
  if (( execute_status != 0 )); then
    echo "Producer execution ${job} failed; refusing to resolve or accept a receipt." >&2
    return "${execute_status}"
  fi

  latest_execution_name "${job}" "${execute_result}" \
    | tee "${EVIDENCE_DIR}/${stem}-${logical_name}-execution.txt"
}

# Rollback is not complete until both exact recovery runs succeed. The shared
# helper persists per-workflow acceptance before waiting, so a later cleanup step
# resumes the same runs instead of dispatching either live producer again.
dispatch_legacy_recovery() {
  dispatch_legacy_recovery_tracked
}
