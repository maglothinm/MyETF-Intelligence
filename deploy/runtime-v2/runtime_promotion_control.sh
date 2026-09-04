#!/usr/bin/env bash
# Sourceable control-plane helpers for the serialized Phase 4/5 Runtime v2 gate.

: "${PROJECT_ID:?PROJECT_ID is required}"
: "${PROJECT_NUMBER:?PROJECT_NUMBER is required}"
: "${REGION:?REGION is required}"
: "${DEPLOYER_SERVICE_ACCOUNT:?DEPLOYER_SERVICE_ACCOUNT is required}"
: "${APPROVED_IMAGE:?APPROVED_IMAGE is required}"
: "${RUNTIME_SOURCE_REVISION:?RUNTIME_SOURCE_REVISION is required}"
: "${EVIDENCE_DIR:?EVIDENCE_DIR is required}"

ADMIN_JOB="polititrack-admin"
WEB_SERVICE="polititrack-web"
SQL_INSTANCE="polititrack-runtime-v2"
VAULT_SCHEDULER="polititrack-vault-lifecycle"
PRODUCER_JOBS=(polititrack-legislative polititrack-executive polititrack-ai polititrack-dashboard)
PRODUCER_NAMES=(legislative executive ai dashboard)
PRODUCER_SCHEDULERS=(polititrack-legislative polititrack-executive polititrack-ai polititrack-dashboard)
LEGACY_WORKFLOWS=(
  legislative_trade_tracker_v2.yml
  executive_trade_tracker.yml
  ai_filing_analyst.yml
  publish_trade_dashboard.yml
)
DEPLOYER_MEMBER="serviceAccount:${DEPLOYER_SERVICE_ACCOUNT}"
RESOURCE_DIR="${EVIDENCE_DIR}/resources"
SERVICE_ACCOUNTS_FILE="${EVIDENCE_DIR}/service-accounts.txt"
mkdir -p "${RESOURCE_DIR}"

verify_canonical_context() {
  [[ "${GITHUB_REPOSITORY_ID:-}" == "1349678672" ]] || { echo "Repository ID mismatch." >&2; return 1; }
  [[ "${GITHUB_REPOSITORY:-}" == "maglothinm/MyETF-Intelligence" ]] || { echo "Repository name mismatch." >&2; return 1; }
  [[ "${GITHUB_REF:-}" == "refs/heads/main" || "${GITHUB_EVENT_NAME:-}" == "workflow_run" ]] || {
    echo "Live control is restricted to canonical main." >&2; return 1;
  }
}

verify_project_boundary() {
  local actual
  actual="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
  [[ "${actual}" == "${PROJECT_NUMBER}" ]] || { echo "Immutable project boundary mismatch." >&2; return 1; }
  gcloud artifacts docker images describe "${APPROVED_IMAGE}" \
    --project "${PROJECT_ID}" --format=none
}

pause_producer_schedulers() {
  local scheduler state
  for scheduler in "${PRODUCER_SCHEDULERS[@]}"; do
    state="$(gcloud scheduler jobs describe "${scheduler}" --project "${PROJECT_ID}" --location "${REGION}" --format='value(state)')"
    if [[ "${state}" != "PAUSED" ]]; then
      gcloud scheduler jobs pause "${scheduler}" --project "${PROJECT_ID}" --location "${REGION}" --quiet
    fi
  done
}

resume_producer_schedulers() {
  local scheduler state
  for scheduler in "${PRODUCER_SCHEDULERS[@]}"; do
    state="$(gcloud scheduler jobs describe "${scheduler}" --project "${PROJECT_ID}" --location "${REGION}" --format='value(state)')"
    if [[ "${state}" != "ENABLED" ]]; then
      gcloud scheduler jobs resume "${scheduler}" --project "${PROJECT_ID}" --location "${REGION}" --quiet
    fi
  done
}

verify_producer_scheduler_state() {
  local expected="$1" scheduler state
  for scheduler in "${PRODUCER_SCHEDULERS[@]}"; do
    state="$(gcloud scheduler jobs describe "${scheduler}" --project "${PROJECT_ID}" --location "${REGION}" --format='value(state)')"
    [[ "${state}" == "${expected}" ]] || { echo "${scheduler} is ${state}, expected ${expected}." >&2; return 1; }
  done
}

verify_vault_scheduler_paused() {
  [[ "$(gcloud scheduler jobs describe "${VAULT_SCHEDULER}" --project "${PROJECT_ID}" --location "${REGION}" --format='value(state)')" == "PAUSED" ]] || {
    echo "Filing Vault scheduler is not PAUSED; Phase 5 will not alter unrelated lifecycle scheduling." >&2; return 1;
  }
}

verify_cloud_sql_private() {
  gcloud sql instances describe "${SQL_INSTANCE}" --project "${PROJECT_ID}" --format=json > "${RESOURCE_DIR}/cloud-sql.json"
  jq -e '(.settings.ipConfiguration.ipv4Enabled // false) == false and ((.settings.ipConfiguration.privateNetwork // "") | length > 0)' \
    "${RESOURCE_DIR}/cloud-sql.json" >/dev/null || { echo "Cloud SQL is not private-only." >&2; return 1; }
}

collect_service_accounts() {
  local job
  for job in "${ADMIN_JOB}" "${PRODUCER_JOBS[@]}"; do
    gcloud run jobs describe "${job}" --project "${PROJECT_ID}" --region "${REGION}" --format=json \
      > "${RESOURCE_DIR}/${job}.json"
  done
  gcloud run services describe "${WEB_SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --format=json \
    > "${RESOURCE_DIR}/${WEB_SERVICE}.json"
  python - "${RESOURCE_DIR}" "${SERVICE_ACCOUNTS_FILE}" <<'PY'
import json
import sys
from pathlib import Path

def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)

accounts = set()
for path in Path(sys.argv[1]).glob("polititrack-*.json"):
    data = json.loads(path.read_text(encoding="utf-8"))
    account = ""
    for item in walk(data):
        value = item.get("serviceAccount") or item.get("serviceAccountName")
        if isinstance(value, str) and value.endswith(".gserviceaccount.com"):
            account = value
            break
    if not account:
        raise SystemExit(f"Unable to resolve service account from {path}")
    accounts.add(account)
Path(sys.argv[2]).write_text("\n".join(sorted(accounts)) + "\n", encoding="utf-8")
PY
}

grant_service_account_user() {
  collect_service_accounts
  local account
  while IFS= read -r account; do
    [[ -n "${account}" ]] || continue
    gcloud iam service-accounts add-iam-policy-binding "${account}" --project "${PROJECT_ID}" \
      --member "${DEPLOYER_MEMBER}" --role roles/iam.serviceAccountUser --condition=None --quiet --format=none
  done < "${SERVICE_ACCOUNTS_FILE}"
}

remove_service_account_user() {
  [[ -f "${SERVICE_ACCOUNTS_FILE}" ]] || return 0
  local account
  while IFS= read -r account; do
    [[ -n "${account}" ]] || continue
    gcloud iam service-accounts remove-iam-policy-binding "${account}" --project "${PROJECT_ID}" \
      --member "${DEPLOYER_MEMBER}" --role roles/iam.serviceAccountUser --condition=None --quiet >/dev/null 2>&1 || true
  done < "${SERVICE_ACCOUNTS_FILE}"
}

verify_service_account_user_removed() {
  [[ -f "${SERVICE_ACCOUNTS_FILE}" ]] || { echo "Service-account inventory is missing." >&2; return 1; }
  local account
  while IFS= read -r account; do
    [[ -n "${account}" ]] || continue
    gcloud iam service-accounts get-iam-policy "${account}" --project "${PROJECT_ID}" --format=json \
      > "${RESOURCE_DIR}/sa-policy-$(echo "${account}" | tr '@.' '__').json"
    if jq -e --arg member "${DEPLOYER_MEMBER}" \
      '[.bindings[]? | select(.role == "roles/iam.serviceAccountUser") | .members[]?] | any(. == $member)' \
      "${RESOURCE_DIR}/sa-policy-$(echo "${account}" | tr '@.' '__').json" >/dev/null; then
      echo "Temporary Service Account User binding remains on ${account}." >&2
      return 1
    fi
  done < "${SERVICE_ACCOUNTS_FILE}"
}

configure_runtime() {
  local mode="$1" job status=0
  if [[ "${mode}" != "shadow" && "${mode}" != "production" ]]; then
    echo "Invalid Runtime v2 mode: ${mode}." >&2
    return 1
  fi
  if ! grant_service_account_user; then
    remove_service_account_user
    return 1
  fi
  if ! gcloud run jobs update "${ADMIN_JOB}" --project "${PROJECT_ID}" --region "${REGION}" \
    --image "${APPROVED_IMAGE}" --update-env-vars PRIVATE_IP=true --quiet --format=none; then
    status=1
  fi
  if (( status == 0 )); then
    for job in "${PRODUCER_JOBS[@]}"; do
      if ! gcloud run jobs update "${job}" --project "${PROJECT_ID}" --region "${REGION}" \
        --image "${APPROVED_IMAGE}" --update-env-vars "PRIVATE_IP=true,POLITITRACK_MODE=${mode}" \
        --quiet --format=none; then
        status=1
        break
      fi
    done
  fi
  if (( status == 0 )) && ! gcloud run services update "${WEB_SERVICE}" \
    --project "${PROJECT_ID}" --region "${REGION}" --image "${APPROVED_IMAGE}" \
    --update-env-vars PRIVATE_IP=true --quiet --format=none; then
    status=1
  fi
  remove_service_account_user
  if (( status != 0 )); then
    echo "Runtime v2 configuration update failed; temporary actAs authority was removed." >&2
    return "${status}"
  fi
  verify_service_account_user_removed
}

configure_runtime_best_effort() {
  configure_runtime "$1"
}

verify_runtime_configuration() {
  local mode="$1" job
  for job in "${ADMIN_JOB}" "${PRODUCER_JOBS[@]}"; do
    gcloud run jobs describe "${job}" --project "${PROJECT_ID}" --region "${REGION}" --format=json \
      > "${RESOURCE_DIR}/verify-${job}.json"
  done
  gcloud run services describe "${WEB_SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --format=json \
    > "${RESOURCE_DIR}/verify-${WEB_SERVICE}.json"
  python - "${RESOURCE_DIR}" "${APPROVED_IMAGE}" "${mode}" <<'PY'
import json
import sys
from pathlib import Path

root, image, mode = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
resources = ["polititrack-admin", "polititrack-legislative", "polititrack-executive", "polititrack-ai", "polititrack-dashboard", "polititrack-web"]
producers = set(resources[1:5])

def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)

for name in resources:
    data = json.loads((root / f"verify-{name}.json").read_text(encoding="utf-8"))
    images = []
    env = {}
    for item in walk(data):
        candidate = item.get("image")
        if isinstance(candidate, str) and "docker.pkg.dev" in candidate:
            images.append(candidate)
        if isinstance(item.get("name"), str) and ("value" in item):
            value = item.get("value")
            if isinstance(value, str):
                env[item["name"]] = value
    if image not in images:
        raise SystemExit(f"{name} is not pinned to the approved immutable image")
    if env.get("PRIVATE_IP", "").lower() != "true":
        raise SystemExit(f"{name} does not require private Cloud SQL routing")
    if name in producers and env.get("POLITITRACK_MODE") != mode:
        raise SystemExit(f"{name} mode is not {mode}")
PY
}

grant_execution_authority() {
  local job
  for job in "${ADMIN_JOB}" "${PRODUCER_JOBS[@]}"; do
    gcloud run jobs add-iam-policy-binding "${job}" --project "${PROJECT_ID}" --region "${REGION}" \
      --member "${DEPLOYER_MEMBER}" --role roles/run.jobsExecutorWithOverrides --quiet --format=none
  done
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
  echo "Temporary execution/logging authority did not become effective." >&2
  return 1
}

remove_execution_authority() {
  local job
  for job in "${ADMIN_JOB}" "${PRODUCER_JOBS[@]}"; do
    gcloud run jobs remove-iam-policy-binding "${job}" --project "${PROJECT_ID}" --region "${REGION}" \
      --member "${DEPLOYER_MEMBER}" --role roles/run.jobsExecutorWithOverrides --quiet >/dev/null 2>&1 || true
  done
  gcloud logging views remove-iam-policy-binding _Default --bucket _Default --location global \
    --project "${PROJECT_ID}" --member "${DEPLOYER_MEMBER}" --role roles/logging.viewAccessor \
    --quiet >/dev/null 2>&1 || true
  gcloud projects remove-iam-policy-binding "${PROJECT_ID}" --member "${DEPLOYER_MEMBER}" \
    --role roles/logging.admin --condition=None --quiet >/dev/null 2>&1 || true
}

verify_execution_authority_removed() {
  local job policy
  for job in "${ADMIN_JOB}" "${PRODUCER_JOBS[@]}"; do
    policy="$(gcloud run jobs get-iam-policy "${job}" --project "${PROJECT_ID}" --region "${REGION}" --format=json)"
    if jq -e --arg member "${DEPLOYER_MEMBER}" \
      '[.bindings[]? | select(.role == "roles/run.jobsExecutorWithOverrides") | .members[]?] | any(. == $member)' \
      <<<"${policy}" >/dev/null; then
      echo "Temporary execution authority remains on ${job}." >&2
      return 1
    fi
  done
  policy="$(gcloud projects get-iam-policy "${PROJECT_ID}" --format=json)"
  if jq -e --arg member "${DEPLOYER_MEMBER}" \
    '[.bindings[]? | select(.role == "roles/logging.admin") | .members[]?] | any(. == $member)' \
    <<<"${policy}" >/dev/null; then
    echo "Temporary logging.admin authority remains." >&2
    return 1
  fi
  policy="$(gcloud logging views get-iam-policy _Default --bucket _Default --location global --project "${PROJECT_ID}" --format=json)"
  if jq -e --arg member "${DEPLOYER_MEMBER}" \
    '[.bindings[]? | select(.role == "roles/logging.viewAccessor") | .members[]?] | any(. == $member)' \
    <<<"${policy}" >/dev/null; then
    echo "Temporary logging view authority remains." >&2
    return 1
  fi
}

latest_execution_name() {
  local job="$1"
  gcloud run jobs executions describe-latest --job "${job}" --project "${PROJECT_ID}" --region "${REGION}" \
    --format='value(metadata.name)'
}

execute_admin_init() {
  local result="${EVIDENCE_DIR}/admin-init-execute.json"
  gcloud run jobs execute "${ADMIN_JOB}" --project "${PROJECT_ID}" --region "${REGION}" \
    --wait --format=json > "${result}"
  latest_execution_name "${ADMIN_JOB}" > "${EVIDENCE_DIR}/admin-init-execution.txt"
}

capture_status() {
  local output="$1" stem="$2" execute_result="${EVIDENCE_DIR}/${stem}-admin-execute.json"
  local execution logs payload
  gcloud run jobs execute "${ADMIN_JOB}" --project "${PROJECT_ID}" --region "${REGION}" \
    --args=-m,runtime_v2,status --wait --format=json > "${execute_result}"
  execution="$(latest_execution_name "${ADMIN_JOB}")"
  [[ -n "${execution}" ]] || { echo "Unable to resolve admin status execution." >&2; return 1; }
  printf '%s\n' "${execution}" > "${EVIDENCE_DIR}/${stem}-admin-execution.txt"
  logs="${EVIDENCE_DIR}/${stem}-admin-logs.json"
  payload=""
  for attempt in $(seq 1 24); do
    gcloud logging read \
      "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"${ADMIN_JOB}\" AND resource.labels.location=\"${REGION}\" AND labels.\"run.googleapis.com/execution_name\"=\"${execution}\"" \
      --project "${PROJECT_ID}" --freshness=2h --limit=1000 --order=asc --format=json > "${logs}"
    payload="$(jq -c '[.[] | .textPayload? | select(type == "string") | fromjson? | select(type == "object" and has("heads") and has("latest_runs"))][-1] // empty' "${logs}")"
    [[ -n "${payload}" ]] && break
    sleep 5
  done
  [[ -n "${payload}" ]] || { echo "No Runtime v2 status payload was emitted by ${execution}." >&2; return 1; }
  printf '%s\n' "${payload}" | jq . > "${output}"
}

execute_producer() {
  local logical_name="$1" trigger="$2" stem="$3" job="polititrack-${logical_name}"
  gcloud run jobs execute "${job}" --project "${PROJECT_ID}" --region "${REGION}" \
    --update-env-vars "POLITITRACK_TRIGGER_SOURCE=${trigger},SOURCE_REVISION=${RUNTIME_SOURCE_REVISION}" \
    --wait --format=json > "${EVIDENCE_DIR}/${stem}-${logical_name}-execute.json"
  latest_execution_name "${job}" | tee "${EVIDENCE_DIR}/${stem}-${logical_name}-execution.txt"
}

web_policy_has_public_invoker() {
  gcloud run services get-iam-policy "${WEB_SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --format=json \
    | jq -e '[.bindings[]? | select(.role == "roles/run.invoker") | .members[]?] | any(. == "allUsers")' >/dev/null
}

verify_web_private() {
  if web_policy_has_public_invoker; then
    echo "Runtime v2 web service unexpectedly has a public invoker." >&2
    return 1
  fi
}

make_web_public() {
  gcloud run services add-iam-policy-binding "${WEB_SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" \
    --member allUsers --role roles/run.invoker --quiet --format=none
  web_policy_has_public_invoker
}

make_web_private() {
  gcloud run services remove-iam-policy-binding "${WEB_SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" \
    --member allUsers --role roles/run.invoker --quiet >/dev/null 2>&1 || true
}

legacy_workflow_state() {
  local workflow="$1"
  gh api "repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow}" --jq '.state'
}

verify_legacy_workflows_state() {
  local expected="$1" workflow state
  for workflow in "${LEGACY_WORKFLOWS[@]}"; do
    state="$(legacy_workflow_state "${workflow}")"
    [[ "${state}" == "${expected}" ]] || { echo "Legacy workflow ${workflow} is ${state}, expected ${expected}." >&2; return 1; }
  done
}

disable_legacy_workflows() {
  local workflow
  for workflow in "${LEGACY_WORKFLOWS[@]}"; do
    gh api --method PUT "repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow}/disable" >/dev/null
  done
  verify_legacy_workflows_state disabled_manually
}

enable_legacy_workflows() {
  local workflow
  for workflow in "${LEGACY_WORKFLOWS[@]}"; do
    gh api --method PUT "repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow}/enable" >/dev/null 2>&1 || true
  done
}

drain_legacy_workflows() {
  local workflow active_file="${EVIDENCE_DIR}/legacy-active-run-ids.txt"
  : > "${active_file}"
  for workflow in "${LEGACY_WORKFLOWS[@]}"; do
    gh api --paginate "repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow}/runs?per_page=100" \
      --jq '.workflow_runs[] | select(.status != "completed") | .id' >> "${active_file}"
  done
  sort -u -o "${active_file}" "${active_file}"
  local run_id status
  while IFS= read -r run_id; do
    [[ -n "${run_id}" ]] || continue
    for attempt in $(seq 1 180); do
      status="$(gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${run_id}" --jq '.status')"
      [[ "${status}" == "completed" ]] && break
      sleep 10
    done
    [[ "${status}" == "completed" ]] || { echo "Legacy run ${run_id} did not drain." >&2; return 1; }
  done < "${active_file}"
  for workflow in "${LEGACY_WORKFLOWS[@]}"; do
    [[ "$(gh api "repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow}/runs?per_page=100" --jq '[.workflow_runs[] | select(.status != "completed")] | length')" == "0" ]] || {
      echo "Legacy workflow ${workflow} still has active runs." >&2; return 1;
    }
  done
}

dispatch_legacy_recovery() {
  gh workflow run legislative_trade_tracker_v2.yml --repo "${GITHUB_REPOSITORY}" --ref main >/dev/null 2>&1 || true
  gh workflow run executive_trade_tracker.yml --repo "${GITHUB_REPOSITORY}" --ref main >/dev/null 2>&1 || true
}

verify_public_web() {
  local expected_digest="$1" url
  url="$(gcloud run services describe "${WEB_SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --format='value(status.url)')"
  [[ "${url}" == https://* ]] || { echo "Runtime v2 web URL is invalid." >&2; return 1; }
  printf '%s\n' "${url}" > "${EVIDENCE_DIR}/web-url.txt"
  local ready=false
  for attempt in $(seq 1 30); do
    if curl --fail --silent --show-error "${url}/healthz" > "${EVIDENCE_DIR}/healthz.json" \
      && curl --fail --silent --show-error "${url}/readyz" > "${EVIDENCE_DIR}/readyz.json" \
      && curl --fail --silent --show-error --dump-header "${EVIDENCE_DIR}/dashboard.headers" "${url}/" \
        > "${EVIDENCE_DIR}/dashboard.html"; then
      ready=true
      break
    fi
    sleep 5
  done
  [[ "${ready}" == "true" ]] || { echo "Runtime v2 web service did not become ready." >&2; return 1; }
  jq -e '.status == "ok" and .service == "polititrack-runtime-v2"' "${EVIDENCE_DIR}/healthz.json" >/dev/null
  jq -e --arg digest "${expected_digest}" '.status == "ready" and .dashboard == true and .snapshot_sha256 == $digest' \
    "${EVIDENCE_DIR}/readyz.json" >/dev/null
  local served
  served="$(awk 'BEGIN{IGNORECASE=1} /^X-PolitiTrack-Snapshot:/ {gsub("\r", "", $2); print $2}' "${EVIDENCE_DIR}/dashboard.headers" | tail -1)"
  [[ "${served}" == "${expected_digest}" ]] || { echo "Served dashboard digest mismatch." >&2; return 1; }
  printf '%s\n' "${served}" > "${EVIDENCE_DIR}/served-dashboard-sha256.txt"
}
