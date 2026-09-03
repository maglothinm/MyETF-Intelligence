#!/usr/bin/env bash
set -euo pipefail

required=(
  PROJECT_ID PROJECT_NUMBER REGION STATE_BUCKET DEPLOYER_SERVICE_ACCOUNT
  ADMIN_JOB ADMIN_SERVICE_ACCOUNT GITHUB_WORKSPACE GITHUB_SHA
  GITHUB_RUN_ID GITHUB_RUN_ATTEMPT RUNNER_TEMP
)
for name in "${required[@]}"; do
  [[ -n "${!name:-}" ]] || { echo "Missing ${name}." >&2; exit 1; }
done

work="${RUNNER_TEMP}/phase3-schema-converge-${GITHUB_RUN_ID}"
rm -rf "${work}"
mkdir -p "${work}"

deployer_member="serviceAccount:${DEPLOYER_SERVICE_ACCOUNT}"
admin_member="serviceAccount:${ADMIN_SERVICE_ACCOUNT}"
probe_object="phase3-acceptance/probes/schema-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}.json"
probe_uri="gs://${STATE_BUCKET}/${probe_object}"
execution_access_added=false
object_access_added=false

cleanup() {
  set +e
  if [[ "${execution_access_added}" == "true" ]]; then
    gcloud run jobs remove-iam-policy-binding "${ADMIN_JOB}" \
      --project "${PROJECT_ID}" --region "${REGION}" \
      --member "${deployer_member}" \
      --role roles/run.jobsExecutorWithOverrides \
      --quiet >/dev/null 2>&1
  fi
  if [[ "${object_access_added}" == "true" ]]; then
    gcloud storage buckets remove-iam-policy-binding "gs://${STATE_BUCKET}" \
      --member "${admin_member}" \
      --role roles/storage.objectCreator \
      --quiet >/dev/null 2>&1
  fi
}
trap cleanup EXIT

verify_absent() {
  local job_policy bucket_policy
  job_policy="$(gcloud run jobs get-iam-policy "${ADMIN_JOB}" \
    --project "${PROJECT_ID}" --region "${REGION}" --format=json)"
  if jq -e --arg member "${deployer_member}" \
    '[.bindings[]? | select(.role == "roles/run.jobsExecutorWithOverrides") | .members[]?] | any(. == $member)' \
    <<<"${job_policy}" >/dev/null; then
    echo "Temporary admin execution authority remains." >&2
    exit 1
  fi
  bucket_policy="$(gcloud storage buckets get-iam-policy "gs://${STATE_BUCKET}" --format=json)"
  if jq -e --arg member "${admin_member}" \
    '[.bindings[]? | select(.role == "roles/storage.objectCreator") | .members[]?] | any(. == $member)' \
    <<<"${bucket_policy}" >/dev/null; then
    echo "Temporary schema-probe object authority remains." >&2
    exit 1
  fi
}

actual_number="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
[[ "${actual_number}" == "${PROJECT_NUMBER}" ]] || {
  echo "Immutable project boundary mismatch." >&2
  exit 1
}

for scheduler in \
  polititrack-legislative \
  polititrack-executive \
  polititrack-ai \
  polititrack-dashboard \
  polititrack-vault-lifecycle; do
  state="$(gcloud scheduler jobs describe "${scheduler}" \
    --project "${PROJECT_ID}" --location "${REGION}" \
    --format='value(state)')"
  [[ "${state}" == "PAUSED" ]] || {
    echo "Scheduler ${scheduler} is not PAUSED." >&2
    exit 1
  }
done

verify_absent

gcloud storage buckets add-iam-policy-binding "gs://${STATE_BUCKET}" \
  --member "${admin_member}" \
  --role roles/storage.objectCreator \
  --quiet >/dev/null
object_access_added=true

gcloud run jobs add-iam-policy-binding "${ADMIN_JOB}" \
  --project "${PROJECT_ID}" --region "${REGION}" \
  --member "${deployer_member}" \
  --role roles/run.jobsExecutorWithOverrides \
  --quiet >/dev/null
execution_access_added=true

payload="$(python - <<'PY'
import base64
import os
from pathlib import Path

source = Path(os.environ["GITHUB_WORKSPACE"]) / "deploy/runtime-v2/gcs_status_probe.py"
print(base64.b64encode(source.read_bytes()).decode("ascii"))
PY
)"
bootstrap="import base64;exec(base64.b64decode('${payload}'))"

set +e
gcloud run jobs execute "${ADMIN_JOB}" \
  --project "${PROJECT_ID}" --region "${REGION}" \
  --args="-c,${bootstrap},${STATE_BUCKET},${probe_object},phase3,initialize-schema" \
  --update-env-vars="PRIVATE_IP=true,SOURCE_REVISION=${GITHUB_SHA}" \
  --wait --format=json > "${work}/execute-result.json" 2> "${work}/execute-error.txt"
execute_rc=$?
set -e

probe_found=false
for attempt in $(seq 1 36); do
  if gcloud storage cat "${probe_uri}" > "${work}/schema-probe.json" 2>/dev/null; then
    probe_found=true
    break
  fi
  sleep 5
done
[[ "${probe_found}" == "true" ]] || {
  cat "${work}/execute-error.txt" >&2 || true
  echo "Schema convergence produced no private receipt." >&2
  exit 1
}

cleanup
execution_access_added=false
object_access_added=false
verify_absent

if ! jq -e '
  .ok == true
  and .phase == "phase3"
  and .schema_initialize_requested == true
  and .schema_initialized == true
  and .protected_state_changed_by_schema_initialize == false
  and .private_ip_env == "true"
  and .database_private_ip_selected == true
  and (.status.heads | length >= 4)
' "${work}/schema-probe.json" >/dev/null; then
  jq '{ok,error_type,error_message,schema_initialize_requested,schema_initialized,protected_state_changed_by_schema_initialize,private_ip_env,database_private_ip_selected,traceback_tail}' \
    "${work}/schema-probe.json" >&2
  [[ "${execute_rc}" -eq 0 ]] || cat "${work}/execute-error.txt" >&2 || true
  echo "Runtime v2 additive schema convergence failed." >&2
  exit 1
fi
[[ "${execute_rc}" -eq 0 ]] || {
  cat "${work}/execute-error.txt" >&2 || true
  echo "Schema convergence returned nonzero despite a successful receipt." >&2
  exit 1
}

trap - EXIT
bash "${GITHUB_WORKSPACE}/deploy/runtime-v2/close-phase3-gcs-v2.sh"
