#!/usr/bin/env bash
set -euo pipefail

required=(
  PROJECT_ID PROJECT_NUMBER REGION STATE_BUCKET DEPLOYER_SERVICE_ACCOUNT
  ADMIN_JOB WEB_SERVICE SQL_INSTANCE LOG_BUCKET LOG_VIEW LOG_LOCATION
  RUNTIME_IMAGE GITHUB_SHA GITHUB_RUN_ID GITHUB_WORKSPACE
)
for name in "${required[@]}"; do
  [[ -n "${!name:-}" ]] || { echo "Missing ${name}." >&2; exit 1; }
done

work="${RUNNER_TEMP:-/tmp}/phase3-force-converge-${GITHUB_RUN_ID}"
rm -rf "${work}"
mkdir -p "${work}"
cd "${work}"
member="serviceAccount:${DEPLOYER_SERVICE_ACCOUNT}"
receipt_uri="gs://${STATE_BUCKET}/phase3-acceptance/final/phase3-acceptance.json"
claim_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
access_active=false

cleanup() {
  set +e
  if [[ "${access_active}" == "true" ]]; then
    gcloud logging views remove-iam-policy-binding "${LOG_VIEW}" --bucket "${LOG_BUCKET}" --location "${LOG_LOCATION}" --project "${PROJECT_ID}" --member "${member}" --role roles/logging.viewAccessor --quiet >/dev/null 2>&1
    gcloud projects remove-iam-policy-binding "${PROJECT_ID}" --member "${member}" --role roles/logging.admin --condition=None --quiet >/dev/null 2>&1
    gcloud run jobs remove-iam-policy-binding "${ADMIN_JOB}" --project "${PROJECT_ID}" --region "${REGION}" --member "${member}" --role roles/run.jobsExecutorWithOverrides --quiet >/dev/null 2>&1
  fi
}
trap cleanup EXIT

container() { jq -c 'first(.. | objects | select(has("containers")) | .containers[0])' "$1"; }
private_ip() { jq -r '[.env[]? | select(.name == "PRIVATE_IP") | .value][0] // empty'; }
image_ref() { jq -r '.image // empty'; }

paused() {
  local name state
  for name in polititrack-legislative polititrack-executive polititrack-ai polititrack-dashboard polititrack-vault-lifecycle; do
    state="$(gcloud scheduler jobs describe "${name}" --project "${PROJECT_ID}" --location "${REGION}" --format='value(state)')"
    [[ "${state}" == "PAUSED" ]] || { echo "${name} is not PAUSED." >&2; exit 1; }
  done
}

private_sql() {
  gcloud sql instances describe "${SQL_INSTANCE}" --project "${PROJECT_ID}" --format=json > sql.json
  jq -e '.settings.ipConfiguration.ipv4Enabled == false and any(.ipAddresses[]?; .type == "PRIVATE")' sql.json >/dev/null || { echo "Cloud SQL is not private-only." >&2; exit 1; }
}

nonpublic_web() {
  policy="$(gcloud run services get-iam-policy "${WEB_SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --format=json)"
  ! jq -e '[.bindings[]?.members[]?] | any(. == "allUsers")' <<<"${policy}" >/dev/null || { echo "Web service is public." >&2; exit 1; }
}

admin_baseline() {
  c="$(container "$1")"
  [[ "$(jq -c '.command // []' <<<"${c}")" == '["python"]' ]] || { echo "Admin command baseline changed." >&2; exit 1; }
  [[ "$(jq -c '.args // []' <<<"${c}")" == '["-m","runtime_v2","init-db","--with-vault"]' ]] || { echo "Admin args baseline changed." >&2; exit 1; }
}

verify_access_removed() {
  project_policy="$(gcloud projects get-iam-policy "${PROJECT_ID}" --format=json)"
  ! jq -e --arg m "${member}" '[.bindings[]? | select(.role == "roles/logging.admin") | .members[]?] | any(. == $m)' <<<"${project_policy}" >/dev/null || { echo "Logging Admin remains." >&2; exit 1; }
  view_policy="$(gcloud logging views get-iam-policy "${LOG_VIEW}" --bucket "${LOG_BUCKET}" --location "${LOG_LOCATION}" --project "${PROJECT_ID}" --format=json)"
  ! jq -e --arg m "${member}" '[.bindings[]? | select(.role == "roles/logging.viewAccessor") | .members[]?] | any(. == $m)' <<<"${view_policy}" >/dev/null || { echo "Log-view access remains." >&2; exit 1; }
  admin_policy="$(gcloud run jobs get-iam-policy "${ADMIN_JOB}" --project "${PROJECT_ID}" --region "${REGION}" --format=json)"
  ! jq -e --arg m "${member}" '[.bindings[]? | select(.role == "roles/run.jobsExecutorWithOverrides") | .members[]?] | any(. == $m)' <<<"${admin_policy}" >/dev/null || { echo "Admin execution access remains." >&2; exit 1; }
}

actual="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
[[ "${actual}" == "${PROJECT_NUMBER}" ]] || { echo "Project boundary mismatch." >&2; exit 1; }
paused
private_sql
nonpublic_web

gcloud run jobs describe "${ADMIN_JOB}" --project "${PROJECT_ID}" --region "${REGION}" --format=json > admin-before.json
admin_baseline admin-before.json

jobs=(polititrack-admin polititrack-legislative polititrack-executive polititrack-ai polititrack-dashboard)
: > deployment-reconciliation.txt
for job in "${jobs[@]}"; do
  gcloud run jobs update "${job}" --project "${PROJECT_ID}" --region "${REGION}" --image "${RUNTIME_IMAGE}" --update-env-vars=PRIVATE_IP=true --quiet >/dev/null
  gcloud run jobs describe "${job}" --project "${PROJECT_ID}" --region "${REGION}" --format=json > "${job}.json"
  c="$(container "${job}.json")"
  [[ "$(private_ip <<<"${c}" | tr '[:upper:]' '[:lower:]')" == "true" ]] || { echo "${job} lacks PRIVATE_IP=true." >&2; exit 1; }
  [[ "$(image_ref <<<"${c}")" == "${RUNTIME_IMAGE}" ]] || { echo "${job} is not pinned to the built digest." >&2; exit 1; }
  printf '%s=%s\n' "${job}" "${RUNTIME_IMAGE}" >> deployment-reconciliation.txt
done

gcloud run services update "${WEB_SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --image "${RUNTIME_IMAGE}" --update-env-vars=PRIVATE_IP=true --quiet >/dev/null
gcloud run services describe "${WEB_SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --format=json > web.json
wc="$(container web.json)"
[[ "$(private_ip <<<"${wc}" | tr '[:upper:]' '[:lower:]')" == "true" ]] || { echo "Web lacks PRIVATE_IP=true." >&2; exit 1; }
[[ "$(image_ref <<<"${wc}")" == "${RUNTIME_IMAGE}" ]] || { echo "Web is not pinned to the built digest." >&2; exit 1; }
printf '%s=%s\n' "${WEB_SERVICE}" "${RUNTIME_IMAGE}" >> deployment-reconciliation.txt

admin_baseline polititrack-admin.json
paused

cleanup
access_active=true
gcloud run jobs add-iam-policy-binding "${ADMIN_JOB}" --project "${PROJECT_ID}" --region "${REGION}" --member "${member}" --role roles/run.jobsExecutorWithOverrides --quiet >/dev/null
gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member "${member}" --role roles/logging.admin --condition=None --quiet >/dev/null
gcloud logging views add-iam-policy-binding "${LOG_VIEW}" --bucket "${LOG_BUCKET}" --location "${LOG_LOCATION}" --project "${PROJECT_ID}" --member "${member}" --role roles/logging.viewAccessor --quiet >/dev/null

ready=false
for attempt in $(seq 1 18); do
  if gcloud logging read 'resource.type="cloud_run_job"' --project "${PROJECT_ID}" --limit=1 --format=json >/dev/null 2> logging-error.txt; then ready=true; break; fi
  echo "Waiting for log-view IAM (${attempt}/18)."
  sleep 10
done
[[ "${ready}" == "true" ]] || { cat logging-error.txt >&2 || true; exit 1; }

set +e
gcloud run jobs execute "${ADMIN_JOB}" --project "${PROJECT_ID}" --region "${REGION}" --args=-m,runtime_v2,status --update-env-vars=PRIVATE_IP=true --wait --format=json > execute.json 2> execute-error.txt
execute_rc=$?
set -e
execution="$(gcloud run jobs describe "${ADMIN_JOB}" --project "${PROJECT_ID}" --region "${REGION}" --format='value(status.latestCreatedExecution.name)')"
[[ -n "${execution}" ]] || { echo "No status execution name." >&2; exit 1; }
gcloud run jobs executions describe "${execution}" --project "${PROJECT_ID}" --region "${REGION}" --format=json > execution.json
ec="$(container execution.json)"
[[ "$(jq -c '.args // []' <<<"${ec}")" == '["-m","runtime_v2","status"]' ]] || { echo "Latest execution is not status." >&2; exit 1; }
[[ "$(private_ip <<<"${ec}" | tr '[:upper:]' '[:lower:]')" == "true" ]] || { echo "Status execution lacks PRIVATE_IP=true." >&2; exit 1; }
start="$(jq -r '.status.startTime // empty' execution.json)"
[[ -n "${start}" && "${start}" > "${claim_time}" ]] || { echo "Status execution predates this run." >&2; exit 1; }

found=false
for attempt in $(seq 1 30); do
  gcloud logging read "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"${ADMIN_JOB}\" AND resource.labels.location=\"${REGION}\" AND labels.\"run.googleapis.com/execution_name\"=\"${execution}\"" --project "${PROJECT_ID}" --order=asc --limit=500 --format=json > logs.json
  jq -c '[.[] | .textPayload? | select(type == "string") | fromjson? | select(type == "object" and has("heads") and has("latest_runs"))][0] // empty' logs.json > status.json
  if [[ -s status.json ]]; then found=true; break; fi
  sleep 5
done
if [[ "${execute_rc}" -ne 0 ]]; then
  cat execute-error.txt >&2 || true
  jq -r '.[] | .textPayload? // empty' logs.json >&2 || true
  exit 1
fi
jq -e 'any(.status.conditions[]?; .type == "Completed" and .status == "True")' execution.json >/dev/null || { echo "Status execution failed." >&2; exit 1; }
[[ "${found}" == "true" ]] || { echo "No durable status JSON." >&2; exit 1; }

cleanup
access_active=false
verify_access_removed
paused
private_sql
nonpublic_web
gcloud run jobs describe "${ADMIN_JOB}" --project "${PROJECT_ID}" --region "${REGION}" --format=json > admin-final.json
admin_baseline admin-final.json

python "${GITHUB_WORKSPACE}/deploy/runtime-v2/validate_phase3_status.py" --status status.json --status-execution "${execution}" --source-revision "${GITHUB_SHA}" --output phase3-acceptance.json
python - <<'PY'
import hashlib, json, os
from pathlib import Path
p=Path('phase3-acceptance.json')
r=json.loads(p.read_text())
r.update({
  'runtime_image': os.environ['RUNTIME_IMAGE'],
  'current_main_image_deployed': True,
  'private_ip_environment_reconciled': True,
  'phase4_started': False,
  'production_authority_transferred': False,
})
p.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
d=hashlib.sha256(p.read_bytes()).hexdigest()
Path('phase3-acceptance.sha256').write_text(d+'  phase3-acceptance.json\n')
print(json.dumps(r,indent=2,sort_keys=True))
print('phase3_acceptance_sha256='+d)
PY
gcloud storage cp phase3-acceptance.json "${receipt_uri}" >/dev/null
remote="$(gcloud storage cat "${receipt_uri}" | sha256sum | awk '{print $1}')"
local="$(awk '{print $1}' phase3-acceptance.sha256)"
[[ "${remote}" == "${local}" ]] || { echo "Receipt digest mismatch." >&2; exit 1; }
printf 'result=phase3_ready_for_phase4\nsource_revision=%s\nworkflow_run=%s\nruntime_image=%s\nphase4_started=false\nproduction_authority_transferred=false\n' "${GITHUB_SHA}" "${GITHUB_RUN_ID}" "${RUNTIME_IMAGE}" > phase4-ready.txt
trap - EXIT
