#!/usr/bin/env bash
# Narrow, sourceable authority helpers for the read-only Phase 4 status capture.

grant_phase4_status_authority() {
  gcloud run jobs add-iam-policy-binding "${ADMIN_JOB}" --project "${PROJECT_ID}" --region "${REGION}" \
    --member "${DEPLOYER_MEMBER}" --role roles/run.jobsExecutorWithOverrides --quiet --format=none
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member "${DEPLOYER_MEMBER}" \
    --role roles/logging.admin --condition=None --quiet --format=none
  gcloud logging views add-iam-policy-binding _Default --bucket _Default --location global \
    --project "${PROJECT_ID}" --member "${DEPLOYER_MEMBER}" --role roles/logging.viewAccessor \
    --quiet --format=none
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
  gcloud run jobs remove-iam-policy-binding "${ADMIN_JOB}" --project "${PROJECT_ID}" --region "${REGION}" \
    --member "${DEPLOYER_MEMBER}" --role roles/run.jobsExecutorWithOverrides --quiet >/dev/null 2>&1 || true
  gcloud logging views remove-iam-policy-binding _Default --bucket _Default --location global \
    --project "${PROJECT_ID}" --member "${DEPLOYER_MEMBER}" --role roles/logging.viewAccessor \
    --quiet >/dev/null 2>&1 || true
  gcloud projects remove-iam-policy-binding "${PROJECT_ID}" --member "${DEPLOYER_MEMBER}" \
    --role roles/logging.admin --condition=None --quiet >/dev/null 2>&1 || true
}

verify_phase4_status_authority_removed() {
  local policy
  policy="$(gcloud run jobs get-iam-policy "${ADMIN_JOB}" --project "${PROJECT_ID}" --region "${REGION}" --format=json)"
  if jq -e --arg member "${DEPLOYER_MEMBER}" \
    '[.bindings[]? | select(.role == "roles/run.jobsExecutorWithOverrides") | .members[]?] | any(. == $member)' \
    <<<"${policy}" >/dev/null; then
    echo "Temporary Phase 4 admin execution authority remains." >&2
    return 1
  fi
  policy="$(gcloud projects get-iam-policy "${PROJECT_ID}" --format=json)"
  if jq -e --arg member "${DEPLOYER_MEMBER}" \
    '[.bindings[]? | select(.role == "roles/logging.admin") | .members[]?] | any(. == $member)' \
    <<<"${policy}" >/dev/null; then
    echo "Temporary Phase 4 logging.admin authority remains." >&2
    return 1
  fi
  policy="$(gcloud logging views get-iam-policy _Default --bucket _Default --location global --project "${PROJECT_ID}" --format=json)"
  if jq -e --arg member "${DEPLOYER_MEMBER}" \
    '[.bindings[]? | select(.role == "roles/logging.viewAccessor") | .members[]?] | any(. == $member)' \
    <<<"${policy}" >/dev/null; then
    echo "Temporary Phase 4 logging-view authority remains." >&2
    return 1
  fi
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

# Rollback is not complete unless both retained collector workflows accepted
# their recovery dispatches. Keep the reviewed workflow targets but remove the
# v1 helper's best-effort error swallowing.
dispatch_legacy_recovery() {
  local status=0
  gh workflow run legislative_trade_tracker_v2.yml \
    --repo "${GITHUB_REPOSITORY}" --ref main || status=$?
  gh workflow run executive_trade_tracker.yml \
    --repo "${GITHUB_REPOSITORY}" --ref main || status=$?
  if (( status != 0 )); then
    echo "One or more legacy recovery dispatches failed." >&2
    return "${status}"
  fi
  printf '%s\n' '{"result":"legacy_recovery_dispatches_accepted","workflows":["legislative_trade_tracker_v2.yml","executive_trade_tracker.yml"]}' \
    > "${EVIDENCE_DIR}/legacy-recovery-dispatch.json"
}
