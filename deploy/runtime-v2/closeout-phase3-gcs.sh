#!/usr/bin/env bash
set -euo pipefail

required=(
  PROJECT_ID PROJECT_NUMBER REGION STATE_BUCKET DEPLOYER_SERVICE_ACCOUNT
  ADMIN_JOB ADMIN_SERVICE_ACCOUNT WEB_SERVICE SQL_INSTANCE
  GITHUB_SHA GITHUB_RUN_ID GITHUB_RUN_ATTEMPT GITHUB_WORKSPACE RUNNER_TEMP
)
for name in "${required[@]}"; do
  [[ -n "${!name:-}" ]] || { echo "Missing ${name}." >&2; exit 1; }
done

work="${RUNNER_TEMP}/phase3-closeout-gcs-${GITHUB_RUN_ID}"
rm -rf "${work}"
mkdir -p "${work}"
cd "${work}"

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
    --project "${PROJECT_ID}" --format=json > sql.json
  jq -e '
    .settings.ipConfiguration.ipv4Enabled == false
    and any(.ipAddresses[]?; .type == "PRIVATE")
  ' sql.json >/dev/null || {
    echo "Cloud SQL is not private-only with a private address." >&2
    exit 1
  }
}

assert_nonpublic_web() {
  local policy
  policy="$(gcloud run services get-iam-policy "${WEB_SERVICE}" \
    --project "${PROJECT_ID}" --region "${REGION}" --format=json)"
  if jq -e '[.bindings[]?.members[]?] | any(. == "allUsers")' \
    <<<"${policy}" >/dev/null; then
    echo "Runtime v2 web service has public allUsers access." >&2
    exit 1
  fi
}

assert_admin_baseline() {
  local container service_account private_ip
  container="$(container_from_file "$1")"
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
  service_account="$(jq -r 'first(.. | objects | .serviceAccountName? // empty)' "$1")"
  [[ "${service_account}" == "${ADMIN_SERVICE_ACCOUNT}" ]] || {
    echo "Unexpected admin service account ${service_account}." >&2
    exit 1
  }
}

verify_temporary_access_absent() {
  local job_policy bucket_policy project_policy
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

  project_policy="$(gcloud projects get-iam-policy "${PROJECT_ID}" --format=json)"
  if jq -e --arg member "${admin_member}" '
    [.bindings[]?
      | select(
          .role == "roles/storage.admin"
          or .role == "roles/storage.objectAdmin"
          or .role == "roles/storage.objectCreator"
        )
      | .members[]?]
    | any(. == $member)
  ' <<<"${project_policy}" >/dev/null; then
    echo "Admin service account has unexpected project-wide object-write authority." >&2
    exit 1
  fi
}

actual_number="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
[[ "${actual_number}" == "${PROJECT_NUMBER}" ]] || {
  echo "Immutable project boundary mismatch." >&2
  exit 1
}

existing_tag="$(git -C "${GITHUB_WORKSPACE}" ls-remote origin refs/tags/phase3-ready | awk '{print $1}')"
[[ -z "${existing_tag}" ]] || {
  echo "phase3-ready already exists at ${existing_tag}; refusing to move it." >&2
  exit 1
}

assert_schedulers_paused
assert_private_sql
assert_nonpublic_web

gcloud run jobs describe "${ADMIN_JOB}" \
  --project "${PROJECT_ID}" --region "${REGION}" \
  --format=json > admin-before.json
assert_admin_baseline admin-before.json
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

payload="$(
  base64 -w 0 "${GITHUB_WORKSPACE}/deploy/runtime-v2/gcs_status_probe.py"
)"
bootstrap="import base64;exec(base64.b64decode('${payload}'))"
previous_execution="$(gcloud run jobs describe "${ADMIN_JOB}" \
  --project "${PROJECT_ID}" --region "${REGION}" \
  --format='value(status.latestCreatedExecution.name)')"

set +e
gcloud run jobs execute "${ADMIN_JOB}" \
  --project "${PROJECT_ID}" --region "${REGION}" \
  --args="-c,${bootstrap},${STATE_BUCKET},${probe_object},phase3" \
  --wait --format=json > execute-result.json 2> execute-error.txt
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
  cat execute-error.txt >&2 || true
  echo "A new private status execution was not created." >&2
  exit 1
}

gcloud run jobs executions describe "${status_execution}" \
  --project "${PROJECT_ID}" --region "${REGION}" \
  --format=json > status-execution.json
status_container="$(container_from_file status-execution.json)"
[[ "$(jq -c '.command // []' <<<"${status_container}")" == '["python"]' ]] || {
  echo "Private status execution did not use python." >&2
  exit 1
}
[[ "$(jq -r '.args[0] // empty' <<<"${status_container}")" == "-c" ]] || {
  echo "Private status execution did not use the bounded injected probe." >&2
  exit 1
}
[[ "$(jq -r '.args[-3] // empty' <<<"${status_container}")" == "${STATE_BUCKET}" ]] || {
  echo "Private status execution targeted an unexpected bucket." >&2
  exit 1
}
[[ "$(jq -r '.args[-2] // empty' <<<"${status_container}")" == "${probe_object}" ]] || {
  echo "Private status execution targeted an unexpected object." >&2
  exit 1
}
[[ "$(jq -r '.args[-1] // empty' <<<"${status_container}")" == "phase3" ]] || {
  echo "Private status execution has an unexpected phase." >&2
  exit 1
}

probe_found=false
for attempt in $(seq 1 30); do
  if gcloud storage cat "${probe_uri}" > probe.json 2>/dev/null; then
    probe_found=true
    break
  fi
  sleep 5
done
[[ "${probe_found}" == "true" ]] || {
  cat execute-error.txt >&2 || true
  echo "Private status probe produced no GCS receipt." >&2
  exit 1
}

cleanup
execution_access_added=false
object_access_added=false
verify_temporary_access_absent

if ! jq -e '.ok == true' probe.json >/dev/null; then
  jq '{
    ok,
    error_type,
    error_message,
    private_ip_env,
    database_private_ip_selected,
    database_module_sha256,
    cloud_sql_connector_version,
    connector_private_value,
    connector_public_value,
    traceback_tail
  }' probe.json >&2
  [[ "${execute_rc}" -eq 0 ]] || cat execute-error.txt >&2 || true
  echo "Private Runtime v2 status probe failed." >&2
  exit 1
fi
[[ "${execute_rc}" -eq 0 ]] || {
  cat execute-error.txt >&2 || true
  echo "Status probe returned nonzero despite an ok receipt." >&2
  exit 1
}

jq -e '
  .phase == "phase3"
  and .private_ip_env == "true"
  and .database_private_ip_selected == true
  and .connector_private_value == "PRIVATE"
  and (.evidence_sha256 | test("^[0-9a-f]{64}$"))
' probe.json >/dev/null
jq '.status' probe.json > status.json

python "${GITHUB_WORKSPACE}/deploy/runtime-v2/validate_phase3_status.py" \
  --status status.json \
  --status-execution "${status_execution}" \
  --source-revision "${GITHUB_SHA}" \
  --output phase3-acceptance-base.json

export PROBE_OBJECT="${probe_object}"
export STATUS_EXECUTION="${status_execution}"
python - <<'PY'
import hashlib
import json
import os
from pathlib import Path

base = json.loads(Path("phase3-acceptance-base.json").read_text(encoding="utf-8"))
probe = json.loads(Path("probe.json").read_text(encoding="utf-8"))
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
path = Path("phase3-acceptance.json")
path.write_text(json.dumps(base, indent=2, sort_keys=True) + "\n", encoding="utf-8")
digest = hashlib.sha256(path.read_bytes()).hexdigest()
Path("phase3-acceptance.sha256").write_text(
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
  --format=json > admin-final.json
assert_admin_baseline admin-final.json
verify_temporary_access_absent

final_uri="gs://${STATE_BUCKET}/phase3-acceptance/final/phase3-acceptance.json"
run_uri="gs://${STATE_BUCKET}/phase3-acceptance/runs/${GITHUB_RUN_ID}/phase3-acceptance.json"
gcloud storage cp phase3-acceptance.json "${run_uri}" >/dev/null
gcloud storage cp phase3-acceptance.json "${final_uri}" >/dev/null
local_digest="$(awk '{print $1}' phase3-acceptance.sha256)"
remote_digest="$(gcloud storage cat "${final_uri}" | sha256sum | awk '{print $1}')"
[[ "${local_digest}" == "${remote_digest}" ]] || {
  echo "Private Phase 3 acceptance receipt failed its GCS round trip." >&2
  exit 1
}

cd "${GITHUB_WORKSPACE}"
git tag phase3-ready "${GITHUB_SHA}"

export READY_TARGET="${GITHUB_SHA}"
export ACCEPTANCE_URI="${final_uri}"
export ACCEPTANCE_SHA256="${local_digest}"
python - <<'PY'
import os
from pathlib import Path

path = Path("docs/runtime-v2/phase3/PHASE4_READY.md")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(
    f"""# Runtime v2 Phase 4 Readiness

Phase 3 was accepted at immutable tag `phase3-ready`, targeting commit `{os.environ["READY_TARGET"]}`.

Acceptance evidence is retained privately at `{os.environ["ACCEPTANCE_URI"]}` with SHA-256 `{os.environ["ACCEPTANCE_SHA256"]}`.

The gate verified exact generation-1 Legislative, Executive, and AI migration provenance; the first private shadow dashboard snapshot; private-only Cloud SQL; private Runtime v2 routing; paused Cloud Scheduler jobs; a nonpublic Runtime v2 web service; the persistent admin baseline; and removal of temporary execution and probe-storage authority.

Phase 4 is ready but has not started. This marker does not authorize production mode, Scheduler activation, external notifications, callbacks, GitHub Pages publication, one-writer transfer, or Phase 5 promotion.
""",
    encoding="utf-8",
)
PY

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add docs/runtime-v2/phase3/PHASE4_READY.md
git commit -m "Record verified Phase 4 readiness"
git pull --rebase origin main
git push --atomic origin HEAD:main refs/tags/phase3-ready

trap - EXIT
