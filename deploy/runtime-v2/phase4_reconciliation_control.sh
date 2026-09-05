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
