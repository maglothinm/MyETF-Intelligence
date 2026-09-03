#!/usr/bin/env bash
set -euo pipefail

required=(
  PROJECT_ID PROJECT_NUMBER REGION STATE_BUCKET WIF_PROVIDER
  DEPLOYER_SERVICE_ACCOUNT ADMIN_JOB WEB_SERVICE SQL_INSTANCE
  LOG_BUCKET LOG_VIEW LOG_LOCATION GITHUB_SHA GITHUB_RUN_ID
)
for name in "${required[@]}"; do
  [[ -n "${!name:-}" ]] || { echo "Missing required environment variable ${name}." >&2; exit 1; }
done

workspace="${RUNNER_TEMP:-/tmp}/polititrack-phase3-converge-${GITHUB_RUN_ID}"
rm -rf "${workspace}"
mkdir -p "${workspace}"
cd "${workspace}"

member="serviceAccount:${DEPLOYER_SERVICE_ACCOUNT}"
acceptance_object="phase3-acceptance/final/phase3-acceptance.json"
acceptance_uri="gs://${STATE_BUCKET}/${acceptance_object}"
claim_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TEMPORARY_ACCESS_ACTIVE=false

cleanup_temporary_access() {
  set +e
  if [[ "${TEMPORARY_ACCESS_ACTIVE}" == "true" ]]; then
    gcloud logging views remove-iam-policy-binding "${LOG_VIEW}" \
      --bucket "${LOG_BUCKET}" \
      --location "${LOG_LOCATION}" \
      --project "${PROJECT_ID}" \
      --member "${member}" \
      --role roles/logging.viewAccessor \
      --quiet >/dev/null 2>&1
    gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
      --member "${member}" \
      --role roles/logging.admin \
      --condition=None \
      --quiet >/dev/null 2>&1
    gcloud run jobs remove-iam-policy-binding "${ADMIN_JOB}" \
      --project "${PROJECT_ID}" \
      --region "${REGION}" \
      --member "${member}" \
      --role roles/run.jobsExecutorWithOverrides \
      --quiet >/dev/null 2>&1
  fi
}
trap cleanup_temporary_access EXIT

container_from_file() {
  jq -c 'first(.. | objects | select(has("containers")) | .containers[0])' "$1"
}

private_ip_from_container() {
  jq -r '[.env[]? | select(.name == "PRIVATE_IP") | .value][0] // empty'
}

assert_schedulers_paused() {
  local scheduler state
  for scheduler in polititrack-legislative polititrack-executive polititrack-ai polititrack-dashboard polititrack-vault-lifecycle; do
    state="$(gcloud scheduler jobs describe "${scheduler}" \
      --project "${PROJECT_ID}" \
      --location "${REGION}" \
      --format='value(state)')"
    [[ "${state}" == "PAUSED" ]] || {
      echo "Scheduler ${scheduler} is not PAUSED." >&2
      exit 1
    }
  done
}

assert_private_sql() {
  gcloud sql instances describe "${SQL_INSTANCE}" \
    --project "${PROJECT_ID}" \
    --format=json > sql.json
  jq -e '.settings.ipConfiguration.ipv4Enabled == false and any(.ipAddresses[]?; .type == "PRIVATE")' sql.json >/dev/null || {
    echo "Cloud SQL is not private-only with a private address." >&2
    exit 1
  }
}

assert_nonpublic_web() {
  local policy
  policy="$(gcloud run services get-iam-policy "${WEB_SERVICE}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --format=json)"
  if jq -e '[.bindings[]?.members[]?] | any(. == "allUsers")' <<<"${policy}" >/dev/null; then
    echo "Runtime v2 web service has public allUsers access." >&2
    exit 1
  fi
}

assert_admin_baseline() {
  local file="$1" container
  container="$(container_from_file "${file}")"
  [[ "$(jq -c '.command // []' <<<"${container}")" == '["python"]' ]] || {
    echo "Unexpected admin command baseline." >&2
    exit 1
  }
  [[ "$(jq -c '.args // []' <<<"${container}")" == '["-m","runtime_v2","init-db","--with-vault"]' ]] || {
    echo "Unexpected admin argument baseline." >&2
    exit 1
  }
}

verify_temporary_access_removed() {
  local project_policy view_policy admin_policy
  project_policy="$(gcloud projects get-iam-policy "${PROJECT_ID}" --format=json)"
  if jq -e --arg member "${member}" '[.bindings[]? | select(.role == "roles/logging.admin") | .members[]?] | any(. == $member)' <<<"${project_policy}" >/dev/null; then
    echo "Temporary Logging Admin remains." >&2
    exit 1
  fi
  view_policy="$(gcloud logging views get-iam-policy "${LOG_VIEW}" \
    --bucket "${LOG_BUCKET}" \
    --location "${LOG_LOCATION}" \
    --project "${PROJECT_ID}" \
    --format=json)"
  if jq -e --arg member "${member}" '[.bindings[]? | select(.role == "roles/logging.viewAccessor") | .members[]?] | any(. == $member)' <<<"${view_policy}" >/dev/null; then
    echo "Temporary log-view accessor remains." >&2
    exit 1
  fi
  admin_policy="$(gcloud run jobs get-iam-policy "${ADMIN_JOB}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --format=json)"
  if jq -e --arg member "${member}" '[.bindings[]? | select(.role == "roles/run.jobsExecutorWithOverrides") | .members[]?] | any(. == $member)' <<<"${admin_policy}" >/dev/null; then
    echo "Temporary admin execution authority remains." >&2
    exit 1
  fi
}

actual_number="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
[[ "${actual_number}" == "${PROJECT_NUMBER}" ]] || {
  echo "Immutable project boundary mismatch." >&2
  exit 1
}

assert_schedulers_paused
assert_private_sql
assert_nonpublic_web

gcloud run jobs describe "${ADMIN_JOB}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --format=json > admin-before.json
assert_admin_baseline admin-before.json

# Terraform declares PRIVATE_IP=true. Correct only this observed deployment drift.
runtime_jobs=(polititrack-admin polititrack-legislative polititrack-executive polititrack-ai polititrack-dashboard)
: > private-ip-reconciliation.txt
for job in "${runtime_jobs[@]}"; do
  before="${job}-before.json"
  gcloud run jobs describe "${job}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --format=json > "${before}"
  container="$(container_from_file "${before}")"
  current="$(private_ip_from_container <<<"${container}")"
  if [[ "${current,,}" != "true" ]]; then
    gcloud run jobs update "${job}" \
      --project "${PROJECT_ID}" \
      --region "${REGION}" \
      --update-env-vars=PRIVATE_IP=true \
      --quiet >/dev/null
    printf '%s corrected from %q to true\n' "${job}" "${current}" >> private-ip-reconciliation.txt
  else
    printf '%s already true\n' "${job}" >> private-ip-reconciliation.txt
  fi
done

gcloud run services describe "${WEB_SERVICE}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --format=json > web-before.json
web_container="$(container_from_file web-before.json)"
web_private="$(private_ip_from_container <<<"${web_container}")"
if [[ "${web_private,,}" != "true" ]]; then
  gcloud run services update "${WEB_SERVICE}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --update-env-vars=PRIVATE_IP=true \
    --quiet >/dev/null
  printf '%s corrected from %q to true\n' "${WEB_SERVICE}" "${web_private}" >> private-ip-reconciliation.txt
else
  printf '%s already true\n' "${WEB_SERVICE}" >> private-ip-reconciliation.txt
fi

for job in "${runtime_jobs[@]}"; do
  after="${job}-after.json"
  gcloud run jobs describe "${job}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --format=json > "${after}"
  container="$(container_from_file "${after}")"
  [[ "$(private_ip_from_container <<<"${container}" | tr '[:upper:]' '[:lower:]')" == "true" ]] || {
    echo "${job} still lacks PRIVATE_IP=true after reconciliation." >&2
    exit 1
  }
done

gcloud run services describe "${WEB_SERVICE}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --format=json > web-after.json
web_after_container="$(container_from_file web-after.json)"
[[ "$(private_ip_from_container <<<"${web_after_container}" | tr '[:upper:]' '[:lower:]')" == "true" ]] || {
  echo "${WEB_SERVICE} still lacks PRIVATE_IP=true after reconciliation." >&2
  exit 1
}
assert_admin_baseline polititrack-admin-after.json
assert_schedulers_paused

# A valid private receipt can be reused, but only after current infrastructure is rechecked.
if gcloud storage cp "${acceptance_uri}" existing-acceptance.json >/dev/null 2>&1; then
  python - <<'PY'
import json
from pathlib import Path
receipt = json.loads(Path('existing-acceptance.json').read_text(encoding='utf-8'))
required = {
    'result': 'phase3_ready_for_phase4',
    'phase4_started': False,
    'production_authority_transferred': False,
    'schedulers_paused': True,
    'cloud_sql_private_only': True,
    'web_public_invoker_absent': True,
    'temporary_execution_authority_removed': True,
    'temporary_logging_authority_removed': True,
}
errors = [f'{key}={receipt.get(key)!r}' for key, value in required.items() if receipt.get(key) != value]
if errors:
    raise SystemExit('Existing Phase 3 acceptance receipt is invalid: ' + ', '.join(errors))
Path('phase3-acceptance.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print('Reused validated private Phase 3 acceptance receipt.')
PY
else
  cleanup_temporary_access
  TEMPORARY_ACCESS_ACTIVE=true
  gcloud run jobs add-iam-policy-binding "${ADMIN_JOB}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --member "${member}" \
    --role roles/run.jobsExecutorWithOverrides \
    --quiet >/dev/null
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member "${member}" \
    --role roles/logging.admin \
    --condition=None \
    --quiet >/dev/null
  gcloud logging views add-iam-policy-binding "${LOG_VIEW}" \
    --bucket "${LOG_BUCKET}" \
    --location "${LOG_LOCATION}" \
    --project "${PROJECT_ID}" \
    --member "${member}" \
    --role roles/logging.viewAccessor \
    --quiet >/dev/null

  logging_ready=false
  for attempt in $(seq 1 18); do
    if gcloud logging read 'resource.type="cloud_run_job"' \
      --project "${PROJECT_ID}" \
      --limit=1 \
      --format=json >/dev/null 2> logging-ready-error.txt; then
      logging_ready=true
      break
    fi
    echo "Log-view IAM not effective yet (attempt ${attempt}/18)."
    sleep 10
  done
  [[ "${logging_ready}" == "true" ]] || {
    cat logging-ready-error.txt >&2 || true
    echo "Cloud Logging access did not propagate." >&2
    exit 1
  }

  set +e
  gcloud run jobs execute "${ADMIN_JOB}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --args=-m,runtime_v2,status \
    --update-env-vars=PRIVATE_IP=true \
    --wait \
    --format=json > execute-result.json 2> execute-error.txt
  execute_rc=$?
  set -e

  status_execution="$(gcloud run jobs describe "${ADMIN_JOB}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --format='value(status.latestCreatedExecution.name)')"
  [[ -n "${status_execution}" ]] || {
    echo "Could not resolve the status execution name." >&2
    exit 1
  }
  gcloud run jobs executions describe "${status_execution}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --format=json > status-execution.json
  status_container="$(container_from_file status-execution.json)"
  [[ "$(jq -c '.command // []' <<<"${status_container}")" == '["python"]' ]] || {
    echo "Status execution did not use python." >&2
    exit 1
  }
  [[ "$(jq -c '.args // []' <<<"${status_container}")" == '["-m","runtime_v2","status"]' ]] || {
    echo "Latest execution is not the bounded status probe." >&2
    exit 1
  }
  [[ "$(private_ip_from_container <<<"${status_container}" | tr '[:upper:]' '[:lower:]')" == "true" ]] || {
    echo "Status execution did not receive PRIVATE_IP=true." >&2
    exit 1
  }
  start_time="$(jq -r '.status.startTime // empty' status-execution.json)"
  [[ -n "${start_time}" && "${start_time}" > "${claim_time}" ]] || {
    echo "Status execution predates this convergence run." >&2
    exit 1
  }

  status_found=false
  for attempt in $(seq 1 24); do
    gcloud logging read \
      "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"${ADMIN_JOB}\" AND resource.labels.location=\"${REGION}\" AND labels.\"run.googleapis.com/execution_name\"=\"${status_execution}\"" \
      --project "${PROJECT_ID}" \
      --order=asc \
      --limit=400 \
      --format=json > status-logs.json
    jq -c '[.[] | .textPayload? | select(type == "string") | fromjson? | select(type == "object" and has("heads") and has("latest_runs"))][0] // empty' status-logs.json > status.json
    if [[ -s status.json ]]; then
      status_found=true
      break
    fi
    sleep 5
  done
  if [[ "${execute_rc}" -ne 0 ]]; then
    cat execute-error.txt >&2 || true
    jq -r '.[] | .textPayload? // empty' status-logs.json >&2 || true
    echo "Current read-only status execution failed." >&2
    exit 1
  fi
  jq -e 'any(.status.conditions[]?; .type == "Completed" and .status == "True")' status-execution.json >/dev/null || {
    echo "Current status execution did not complete successfully." >&2
    exit 1
  }
  [[ "${status_found}" == "true" ]] || {
    echo "Current status execution produced no durable-state JSON." >&2
    exit 1
  }

  cleanup_temporary_access
  TEMPORARY_ACCESS_ACTIVE=false
  verify_temporary_access_removed
  assert_schedulers_paused
  assert_private_sql
  assert_nonpublic_web

  gcloud run jobs describe "${ADMIN_JOB}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --format=json > admin-final.json
  assert_admin_baseline admin-final.json
  admin_final_container="$(container_from_file admin-final.json)"
  [[ "$(private_ip_from_container <<<"${admin_final_container}" | tr '[:upper:]' '[:lower:]')" == "true" ]] || {
    echo "Admin private routing was not retained." >&2
    exit 1
  }

  python "${GITHUB_WORKSPACE}/deploy/runtime-v2/validate_phase3_status.py" \
    --status status.json \
    --status-execution "${status_execution}" \
    --source-revision "${GITHUB_SHA}" \
    --output phase3-acceptance.json

  python - <<'PY'
import json
from pathlib import Path
path = Path('phase3-acceptance.json')
receipt = json.loads(path.read_text(encoding='utf-8'))
receipt.update({
    'private_ip_environment_reconciled': True,
    'runtime_jobs_private_ip_verified': [
        'polititrack-admin',
        'polititrack-legislative',
        'polititrack-executive',
        'polititrack-ai',
        'polititrack-dashboard',
    ],
    'web_private_ip_verified': True,
})
path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print(json.dumps(receipt, indent=2, sort_keys=True))
PY
  gcloud storage cp phase3-acceptance.json "${acceptance_uri}" >/dev/null
fi

# Recheck all current boundaries even when reusing an existing receipt.
verify_temporary_access_removed
assert_schedulers_paused
assert_private_sql
assert_nonpublic_web
gcloud run jobs describe "${ADMIN_JOB}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --format=json > admin-current.json
assert_admin_baseline admin-current.json
admin_current_container="$(container_from_file admin-current.json)"
[[ "$(private_ip_from_container <<<"${admin_current_container}" | tr '[:upper:]' '[:lower:]')" == "true" ]] || {
  echo "Admin does not retain PRIVATE_IP=true." >&2
  exit 1
}

python - <<'PY'
import hashlib
import json
from pathlib import Path
path = Path('phase3-acceptance.json')
receipt = json.loads(path.read_text(encoding='utf-8'))
if receipt.get('result') != 'phase3_ready_for_phase4':
    raise SystemExit('Final receipt does not declare Phase 4 readiness.')
if receipt.get('phase4_started') is not False:
    raise SystemExit('Receipt indicates Phase 4 has already started.')
if receipt.get('production_authority_transferred') is not False:
    raise SystemExit('Receipt indicates production authority was transferred.')
digest = hashlib.sha256(path.read_bytes()).hexdigest()
Path('phase3-acceptance.sha256').write_text(digest + '  phase3-acceptance.json\n', encoding='utf-8')
print(f'phase3_acceptance_sha256={digest}')
PY
remote_digest="$(gcloud storage cat "${acceptance_uri}" | sha256sum | awk '{print $1}')"
local_digest="$(awk '{print $1}' phase3-acceptance.sha256)"
[[ "${remote_digest}" == "${local_digest}" ]] || {
  echo "Private acceptance receipt round-trip digest mismatch." >&2
  exit 1
}

printf 'result=phase3_ready_for_phase4\nsource_revision=%s\nworkflow_run=%s\nphase4_started=false\nproduction_authority_transferred=false\n' \
  "${GITHUB_SHA}" "${GITHUB_RUN_ID}" > phase4-ready.txt

trap - EXIT
