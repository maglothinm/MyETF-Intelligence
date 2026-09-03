#!/usr/bin/env bash
set -euo pipefail

required=(
  PROJECT_ID PROJECT_NUMBER REGION STATE_BUCKET DEPLOYER_SERVICE_ACCOUNT
  ADMIN_JOB ADMIN_SERVICE_ACCOUNT WEB_SERVICE SQL_INSTANCE
  GITHUB_WORKSPACE GITHUB_SHA GITHUB_RUN_ID GITHUB_RUN_ATTEMPT RUNNER_TEMP
)
for name in "${required[@]}"; do
  [[ -n "${!name:-}" ]] || { echo "Missing ${name}." >&2; exit 1; }
done

root="${GITHUB_WORKSPACE}"
work="${RUNNER_TEMP}/phase3-closeout-gcs-v2-${GITHUB_RUN_ID}"
rm -rf "${work}"
mkdir -p "${work}"

deployer_member="serviceAccount:${DEPLOYER_SERVICE_ACCOUNT}"
admin_member="serviceAccount:${ADMIN_SERVICE_ACCOUNT}"
probe_object="phase3-acceptance/probes/${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}.json"
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

container_from_file() {
  jq -c 'first(.. | objects | select(has("containers")) | .containers[0])' "$1"
}

service_account_from_file() {
  jq -r 'first(.. | objects | select(((.serviceAccount? // .serviceAccountName? // "") | length) > 0) | (.serviceAccount // .serviceAccountName))' "$1"
}

assert_schedulers_paused() {
  local scheduler state
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
}

assert_private_sql() {
  gcloud sql instances describe "${SQL_INSTANCE}" \
    --project "${PROJECT_ID}" --format=json > "${work}/sql.json"
  jq -e '.settings.ipConfiguration.ipv4Enabled == false and any(.ipAddresses[]?; .type == "PRIVATE")' \
    "${work}/sql.json" >/dev/null || {
      echo "Cloud SQL is not private-only with a private address." >&2
      exit 1
    }
}

assert_nonpublic_web() {
  local policy
  policy="$(gcloud run services get-iam-policy "${WEB_SERVICE}" \
    --project "${PROJECT_ID}" --region "${REGION}" --format=json)"
  if jq -e '[.bindings[]?.members[]?] | any(. == "allUsers")' <<<"${policy}" >/dev/null; then
    echo "Runtime v2 web service has public allUsers access." >&2
    exit 1
  fi
}

assert_admin_baseline() {
  local path="$1" container service_account private_ip
  container="$(container_from_file "${path}")"
  [[ "$(jq -c '.command // []' <<<"${container}")" == '["python"]' ]] || {
    echo "Unexpected admin command baseline." >&2
    exit 1
  }
  [[ "$(jq -c '.args // []' <<<"${container}")" == '["-m","runtime_v2","init-db","--with-vault"]' ]] || {
    echo "Unexpected admin argument baseline." >&2
    exit 1
  }
  private_ip="$(jq -r '[.env[]? | select(.name == "PRIVATE_IP") | .value][0] // empty' <<<"${container}")"
  [[ "${private_ip,,}" == "true" ]] || {
    echo "Admin PRIVATE_IP is not true." >&2
    exit 1
  }
  service_account="$(service_account_from_file "${path}")"
  [[ "${service_account}" == "${ADMIN_SERVICE_ACCOUNT}" ]] || {
    echo "Unexpected admin service account ${service_account}." >&2
    exit 1
  }
}

verify_temporary_access_absent() {
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
    echo "Temporary probe object-creator authority remains." >&2
    exit 1
  fi
}

actual_number="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
[[ "${actual_number}" == "${PROJECT_NUMBER}" ]] || {
  echo "Immutable project boundary mismatch." >&2
  exit 1
}

existing_tag="$(git -C "${root}" ls-remote origin refs/tags/phase3-ready | awk '{print $1}')"
[[ -z "${existing_tag}" ]] || {
  echo "phase3-ready already exists at ${existing_tag}; refusing to move it." >&2
  exit 1
}

assert_schedulers_paused
assert_private_sql
assert_nonpublic_web

gcloud run jobs describe "${ADMIN_JOB}" \
  --project "${PROJECT_ID}" --region "${REGION}" \
  --format=json > "${work}/admin-before.json"
assert_admin_baseline "${work}/admin-before.json"
verify_temporary_access_absent

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
previous_execution="$(gcloud run jobs describe "${ADMIN_JOB}" \
  --project "${PROJECT_ID}" --region "${REGION}" \
  --format='value(status.latestCreatedExecution.name)')"

set +e
gcloud run jobs execute "${ADMIN_JOB}" \
  --project "${PROJECT_ID}" --region "${REGION}" \
  --args="-c,${bootstrap},${STATE_BUCKET},${probe_object},phase3" \
  --update-env-vars="PRIVATE_IP=true,SOURCE_REVISION=${GITHUB_SHA}" \
  --wait --format=json > "${work}/execute-result.json" 2> "${work}/execute-error.txt"
execute_rc=$?
set -e

status_execution=""
for attempt in $(seq 1 20); do
  status_execution="$(gcloud run jobs describe "${ADMIN_JOB}" \
    --project "${PROJECT_ID}" --region "${REGION}" \
    --format='value(status.latestCreatedExecution.name)')"
  if [[ -n "${status_execution}" && "${status_execution}" != "${previous_execution}" ]]; then
    break
  fi
  sleep 3
done
[[ -n "${status_execution}" && "${status_execution}" != "${previous_execution}" ]] || {
  cat "${work}/execute-error.txt" >&2 || true
  echo "A new private status execution was not created." >&2
  exit 1
}

gcloud run jobs executions describe "${status_execution}" \
  --project "${PROJECT_ID}" --region "${REGION}" \
  --format=json > "${work}/status-execution.json"

probe_found=false
for attempt in $(seq 1 36); do
  if gcloud storage cat "${probe_uri}" > "${work}/probe.json" 2>/dev/null; then
    probe_found=true
    break
  fi
  sleep 5
done
[[ "${probe_found}" == "true" ]] || {
  cat "${work}/execute-error.txt" >&2 || true
  echo "Private status probe produced no GCS receipt." >&2
  exit 1
}

cleanup
execution_access_added=false
object_access_added=false
verify_temporary_access_absent

if ! jq -e '.ok == true' "${work}/probe.json" >/dev/null; then
  jq '{ok,error_type,error_message,private_ip_env,database_private_ip_selected,database_module_sha256,cloud_sql_connector_version,connector_private_value,connector_public_value,traceback_tail}' \
    "${work}/probe.json" >&2
  [[ "${execute_rc}" -eq 0 ]] || cat "${work}/execute-error.txt" >&2 || true
  echo "Private Runtime v2 status probe failed." >&2
  exit 1
fi
[[ "${execute_rc}" -eq 0 ]] || {
  cat "${work}/execute-error.txt" >&2 || true
  echo "Status probe returned nonzero despite an ok receipt." >&2
  exit 1
}

jq -e '
  .phase == "phase3"
  and .private_ip_env == "true"
  and .database_private_ip_selected == true
  and .connector_private_value == "PRIVATE"
  and (.evidence_sha256 | test("^[0-9a-f]{64}$"))
' "${work}/probe.json" >/dev/null
jq '.status' "${work}/probe.json" > "${work}/status.json"

python "${root}/deploy/runtime-v2/validate_phase3_status.py" \
  --status "${work}/status.json" \
  --status-execution "${status_execution}" \
  --source-revision "${GITHUB_SHA}" \
  --output "${work}/phase3-acceptance-base.json"

STATUS_EXECUTION="${status_execution}" PROBE_OBJECT="${probe_object}" python - <<'PY'
import hashlib
import json
import os
from pathlib import Path

work = Path(os.environ["RUNNER_TEMP"]) / f"phase3-closeout-gcs-v2-{os.environ['GITHUB_RUN_ID']}"
base = json.loads((work / "phase3-acceptance-base.json").read_text(encoding="utf-8"))
probe = json.loads((work / "probe.json").read_text(encoding="utf-8"))
base.update(
    {
        "acceptance_channel": "private_gcs_probe",
        "status_execution": os.environ["STATUS_EXECUTION"],
        "probe_object": os.environ["PROBE_OBJECT"],
        "probe_evidence_sha256": probe["evidence_sha256"],
        "database_module_sha256": probe["database_module_sha256"],
        "cloud_sql_connector_version": probe["cloud_sql_connector_version"],
        "private_ip_env": probe["private_ip_env"],
        "database_private_ip_selected": probe["database_private_ip_selected"],
        "temporary_execution_authority_removed": True,
        "temporary_probe_storage_authority_removed": True,
        "schedulers_paused": True,
        "cloud_sql_private_only": True,
        "web_public_invoker_absent": True,
        "phase4_started": False,
        "production_authority_transferred": False,
    }
)
path = work / "phase3-acceptance.json"
path.write_text(json.dumps(base, indent=2, sort_keys=True) + "\n", encoding="utf-8")
digest = hashlib.sha256(path.read_bytes()).hexdigest()
(work / "phase3-acceptance.sha256").write_text(
    f"{digest}  phase3-acceptance.json\n", encoding="utf-8"
)
print(json.dumps(base, indent=2, sort_keys=True))
print(f"phase3_acceptance_sha256={digest}")
PY

assert_schedulers_paused
assert_private_sql
assert_nonpublic_web

gcloud run jobs describe "${ADMIN_JOB}" \
  --project "${PROJECT_ID}" --region "${REGION}" \
  --format=json > "${work}/admin-final.json"
assert_admin_baseline "${work}/admin-final.json"

final_uri="gs://${STATE_BUCKET}/phase3-acceptance/final/phase3-acceptance.json"
run_uri="gs://${STATE_BUCKET}/phase3-acceptance/runs/${GITHUB_RUN_ID}/phase3-acceptance.json"
gcloud storage cp "${work}/phase3-acceptance.json" "${run_uri}" >/dev/null
gcloud storage cp "${work}/phase3-acceptance.json" "${final_uri}" >/dev/null
local_digest="$(awk '{print $1}' "${work}/phase3-acceptance.sha256")"
remote_digest="$(gcloud storage cat "${final_uri}" | sha256sum | awk '{print $1}')"
[[ "${local_digest}" == "${remote_digest}" ]] || {
  echo "Private Phase 3 acceptance receipt failed its GCS round trip." >&2
  exit 1
}

mkdir -p "${root}/docs/runtime-v2/phase3"
cat > "${root}/docs/runtime-v2/phase3/PHASE4_READY.md" <<EOF
# Runtime v2 Phase 4 Readiness

Phase 3 was accepted at immutable tag \`phase3-ready\`, targeting commit \`${GITHUB_SHA}\`.

Acceptance evidence is retained privately at \`${final_uri}\` with SHA-256 \`${local_digest}\`.

The gate verified exact generation-1 Legislative, Executive, and AI migration provenance; the first private shadow dashboard snapshot; private-only Cloud SQL; private Runtime v2 routing; paused Cloud Scheduler jobs; a nonpublic Runtime v2 web service; the persistent admin baseline; and removal of temporary execution and probe-storage authority.

Phase 4 is ready but has not started. This marker does not authorize production mode, Scheduler activation, external notifications, callbacks, GitHub Pages publication, one-writer transfer, or Phase 5 promotion.
EOF

git -C "${root}" config user.name "github-actions[bot]"
git -C "${root}" config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git -C "${root}" add docs/runtime-v2/phase3/PHASE4_READY.md
git -C "${root}" commit -m "Record verified Phase 4 readiness"
git -C "${root}" pull --rebase origin main
git -C "${root}" tag phase3-ready "${GITHUB_SHA}"
git -C "${root}" push --atomic origin HEAD:main refs/tags/phase3-ready

remote_tag="$(git -C "${root}" ls-remote origin refs/tags/phase3-ready | awk '{print $1}')"
[[ "${remote_tag}" == "${GITHUB_SHA}" ]] || {
  echo "Remote phase3-ready tag does not target the accepted commit." >&2
  exit 1
}
