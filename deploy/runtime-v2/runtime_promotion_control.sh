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
SERVICE_ACCOUNT_INVENTORY_RECEIPT="${RESOURCE_DIR}/service-account-inventory.json"
LOGGING_VIEW_POLICY_RECEIPT="${RESOURCE_DIR}/logging-view-policy-after-removal.json"
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
  if ! actual="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"; then
    echo "Unable to verify the immutable project boundary." >&2
    return 1
  fi
  [[ "${actual}" == "${PROJECT_NUMBER}" ]] || { echo "Immutable project boundary mismatch." >&2; return 1; }
  gcloud artifacts docker images describe "${APPROVED_IMAGE}" \
    --project "${PROJECT_ID}" --format=none || {
      echo "Unable to verify the approved immutable image." >&2
      return 1
    }
}

pause_producer_schedulers() {
  local scheduler state
  for scheduler in "${PRODUCER_SCHEDULERS[@]}"; do
    if ! state="$(gcloud scheduler jobs describe "${scheduler}" --project "${PROJECT_ID}" --location "${REGION}" --format='value(state)')"; then
      echo "Unable to read scheduler ${scheduler}." >&2
      return 1
    fi
    if [[ "${state}" != "PAUSED" ]]; then
      gcloud scheduler jobs pause "${scheduler}" --project "${PROJECT_ID}" --location "${REGION}" --quiet || return 1
    fi
  done
}

resume_producer_schedulers() {
  local scheduler state
  for scheduler in "${PRODUCER_SCHEDULERS[@]}"; do
    if ! state="$(gcloud scheduler jobs describe "${scheduler}" --project "${PROJECT_ID}" --location "${REGION}" --format='value(state)')"; then
      echo "Unable to read scheduler ${scheduler}." >&2
      return 1
    fi
    if [[ "${state}" != "ENABLED" ]]; then
      gcloud scheduler jobs resume "${scheduler}" --project "${PROJECT_ID}" --location "${REGION}" --quiet || return 1
    fi
  done
}

verify_producer_scheduler_state() {
  local expected="$1" scheduler state
  for scheduler in "${PRODUCER_SCHEDULERS[@]}"; do
    if ! state="$(gcloud scheduler jobs describe "${scheduler}" --project "${PROJECT_ID}" --location "${REGION}" --format='value(state)')"; then
      echo "Unable to verify scheduler ${scheduler}." >&2
      return 1
    fi
    [[ "${state}" == "${expected}" ]] || { echo "${scheduler} is ${state}, expected ${expected}." >&2; return 1; }
  done
}

verify_vault_scheduler_paused() {
  local state
  if ! state="$(gcloud scheduler jobs describe "${VAULT_SCHEDULER}" --project "${PROJECT_ID}" --location "${REGION}" --format='value(state)')"; then
    echo "Unable to verify the Filing Vault scheduler." >&2
    return 1
  fi
  [[ "${state}" == "PAUSED" ]] || {
    echo "Filing Vault scheduler is not PAUSED; Phase 5 will not alter unrelated lifecycle scheduling." >&2; return 1;
  }
}

verify_cloud_sql_private() {
  if ! gcloud sql instances describe "${SQL_INSTANCE}" --project "${PROJECT_ID}" --format=json \
    > "${RESOURCE_DIR}/cloud-sql.json"; then
    echo "Unable to verify Cloud SQL network state." >&2
    return 1
  fi
  jq -e '(.settings.ipConfiguration.ipv4Enabled // false) == false and ((.settings.ipConfiguration.privateNetwork // "") | length > 0)' \
    "${RESOURCE_DIR}/cloud-sql.json" >/dev/null || { echo "Cloud SQL is not private-only." >&2; return 1; }
}

collect_service_accounts() {
  local job output temporary_accounts="${SERVICE_ACCOUNTS_FILE}.tmp"
  local temporary_receipt="${SERVICE_ACCOUNT_INVENTORY_RECEIPT}.tmp"
  rm -f "${temporary_accounts}" "${temporary_receipt}" || return 1
  for job in "${ADMIN_JOB}" "${PRODUCER_JOBS[@]}"; do
    output="${RESOURCE_DIR}/${job}.json.tmp"
    if ! gcloud run jobs describe "${job}" --project "${PROJECT_ID}" --region "${REGION}" --format=json \
      > "${output}"; then
      rm -f "${output}" "${temporary_accounts}" "${temporary_receipt}"
      echo "Unable to resolve service account for ${job}." >&2
      return 1
    fi
    mv "${output}" "${RESOURCE_DIR}/${job}.json" || return 1
  done
  output="${RESOURCE_DIR}/${WEB_SERVICE}.json.tmp"
  if ! gcloud run services describe "${WEB_SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --format=json \
    > "${output}"; then
    rm -f "${output}" "${temporary_accounts}" "${temporary_receipt}"
    echo "Unable to resolve service account for ${WEB_SERVICE}." >&2
    return 1
  fi
  mv "${output}" "${RESOURCE_DIR}/${WEB_SERVICE}.json" || return 1
  if ! python - "${RESOURCE_DIR}" "${temporary_accounts}" "${temporary_receipt}" "${PROJECT_ID}" <<'PY'
import hashlib
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

root = Path(sys.argv[1])
resource_names = [
    "polititrack-admin", "polititrack-legislative", "polititrack-executive",
    "polititrack-ai", "polititrack-dashboard", "polititrack-web",
]
accounts = set()
for name in resource_names:
    path = root / f"{name}.json"
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
if not accounts:
    raise SystemExit("Service-account inventory is empty")
content = ("\n".join(sorted(accounts)) + "\n").encode("utf-8")
Path(sys.argv[2]).write_bytes(content)
receipt = {
    "schema_version": 1,
    "result": "runtime_service_account_inventory",
    "project_id": sys.argv[4],
    "resources": resource_names,
    "accounts": sorted(accounts),
    "accounts_sha256": hashlib.sha256(content).hexdigest(),
}
Path(sys.argv[3]).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  then
    rm -f "${temporary_accounts}" "${temporary_receipt}"
    return 1
  fi
  mv "${temporary_receipt}" "${SERVICE_ACCOUNT_INVENTORY_RECEIPT}" || return 1
  mv "${temporary_accounts}" "${SERVICE_ACCOUNTS_FILE}" || return 1
  verify_service_account_inventory
}

verify_service_account_inventory() {
  [[ -s "${SERVICE_ACCOUNTS_FILE}" && -s "${SERVICE_ACCOUNT_INVENTORY_RECEIPT}" ]] || {
    echo "Service-account inventory or its receipt is missing." >&2
    return 1
  }
  local digest
  if ! digest="$(sha256sum "${SERVICE_ACCOUNTS_FILE}" | awk '{print $1}')"; then
    echo "Unable to hash the service-account inventory." >&2
    return 1
  fi
  jq -e \
    --arg project "${PROJECT_ID}" \
    --arg digest "${digest}" \
    --rawfile accounts_file "${SERVICE_ACCOUNTS_FILE}" \
    'type == "object" and
     .schema_version == 1 and
     .result == "runtime_service_account_inventory" and
     .project_id == $project and
     .resources == ["polititrack-admin", "polititrack-legislative", "polititrack-executive",
                    "polititrack-ai", "polititrack-dashboard", "polititrack-web"] and
     (.accounts | type == "array" and length > 0 and all(.[]; type == "string" and endswith(".gserviceaccount.com"))) and
     .accounts == ($accounts_file | split("\n") | map(select(length > 0))) and
     .accounts_sha256 == $digest' \
    "${SERVICE_ACCOUNT_INVENTORY_RECEIPT}" >/dev/null || {
      echo "Service-account inventory receipt is invalid." >&2
      return 1
    }
}

grant_service_account_user() {
  collect_service_accounts || return 1
  verify_service_account_inventory || return 1
  local account
  while IFS= read -r account; do
    [[ -n "${account}" ]] || continue
    gcloud iam service-accounts add-iam-policy-binding "${account}" --project "${PROJECT_ID}" \
      --member "${DEPLOYER_MEMBER}" --role roles/iam.serviceAccountUser --condition=None --quiet --format=none || return 1
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
  verify_service_account_inventory || return 1
  local account policy_file
  while IFS= read -r account; do
    [[ -n "${account}" ]] || continue
    policy_file="${RESOURCE_DIR}/sa-policy-$(echo "${account}" | tr '@.' '__').json"
    if ! gcloud iam service-accounts get-iam-policy "${account}" --project "${PROJECT_ID}" --format=json \
      > "${policy_file}"; then
      echo "Unable to verify Service Account User cleanup on ${account}." >&2
      return 1
    fi
    if ! jq -e --arg member "${DEPLOYER_MEMBER}" \
      'type == "object" and
       ([.bindings[]? | select(.role == "roles/iam.serviceAccountUser") | .members[]?] | any(. == $member) | not)' \
      "${policy_file}" >/dev/null; then
      echo "Temporary Service Account User cleanup is unverified on ${account}." >&2
      return 1
    fi
  done < "${SERVICE_ACCOUNTS_FILE}"
}

configure_runtime() {
  local mode="$1" job status=0 cleanup_status=0
  if [[ "${mode}" != "shadow" && "${mode}" != "production" ]]; then
    echo "Invalid Runtime v2 mode: ${mode}." >&2
    return 1
  fi
  if ! grant_service_account_user; then
    remove_service_account_user
    verify_service_account_user_removed || cleanup_status=1
    (( cleanup_status == 0 )) || echo "Temporary actAs cleanup could not be verified after grant failure." >&2
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
  verify_service_account_user_removed || cleanup_status=1
  if (( status != 0 )); then
    echo "Runtime v2 configuration update failed; temporary actAs cleanup was attempted." >&2
    return "${status}"
  fi
  if (( cleanup_status != 0 )); then
    echo "Runtime v2 configuration completed but temporary actAs cleanup is unverified." >&2
    return 1
  fi
}

configure_runtime_best_effort() {
  configure_runtime "$1"
}

verify_runtime_configuration() {
  local mode="$1" job
  for job in "${ADMIN_JOB}" "${PRODUCER_JOBS[@]}"; do
    if ! gcloud run jobs describe "${job}" --project "${PROJECT_ID}" --region "${REGION}" --format=json \
      > "${RESOURCE_DIR}/verify-${job}.json"; then
      echo "Unable to verify Runtime v2 job ${job}." >&2
      return 1
    fi
  done
  if ! gcloud run services describe "${WEB_SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --format=json \
    > "${RESOURCE_DIR}/verify-${WEB_SERVICE}.json"; then
    echo "Unable to verify Runtime v2 service ${WEB_SERVICE}." >&2
    return 1
  fi
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
  rm -f "${LOGGING_VIEW_POLICY_RECEIPT}" || return 1
  for job in "${ADMIN_JOB}" "${PRODUCER_JOBS[@]}"; do
    gcloud run jobs add-iam-policy-binding "${job}" --project "${PROJECT_ID}" --region "${REGION}" \
      --member "${DEPLOYER_MEMBER}" --role roles/run.jobsExecutorWithOverrides --quiet --format=none || return 1
  done
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
  echo "Temporary execution/logging authority did not become effective." >&2
  return 1
}

verify_logging_view_removal_receipt() {
  [[ -s "${LOGGING_VIEW_POLICY_RECEIPT}" ]] || {
    echo "Logging-view cleanup receipt is missing." >&2
    return 1
  }
  jq -e \
    --arg project "${PROJECT_ID}" \
    --arg member "${DEPLOYER_MEMBER}" \
    'type == "object" and
     .schema_version == 1 and
     .result == "logging_view_accessor_removed" and
     .project_id == $project and
     .location == "global" and
     .bucket == "_Default" and
     .view == "_Default" and
     .member == $member and
     .role == "roles/logging.viewAccessor" and
     .verified_absent == true and
     (.policy | type == "object") and
     ([.policy.bindings[]? | select(.role == "roles/logging.viewAccessor") | .members[]?] |
      any(. == $member) | not)' \
    "${LOGGING_VIEW_POLICY_RECEIPT}" >/dev/null || {
      echo "Logging-view cleanup receipt is invalid or still contains temporary authority." >&2
      return 1
    }
}

capture_logging_view_removal_receipt() {
  local policy_file="${LOGGING_VIEW_POLICY_RECEIPT}.policy.tmp"
  local receipt_file="${LOGGING_VIEW_POLICY_RECEIPT}.tmp"
  rm -f "${policy_file}" "${receipt_file}"
  if ! gcloud logging views get-iam-policy _Default --bucket _Default --location global \
    --project "${PROJECT_ID}" --format=json > "${policy_file}"; then
    rm -f "${policy_file}" "${receipt_file}"
    return 1
  fi
  if ! jq -e --arg member "${DEPLOYER_MEMBER}" \
    'type == "object" and
     ([.bindings[]? | select(.role == "roles/logging.viewAccessor") | .members[]?] | any(. == $member) | not)' \
    "${policy_file}" >/dev/null; then
    rm -f "${policy_file}" "${receipt_file}"
    return 1
  fi
  jq -n \
    --arg project "${PROJECT_ID}" \
    --arg member "${DEPLOYER_MEMBER}" \
    --slurpfile policy "${policy_file}" \
    '{schema_version:1, result:"logging_view_accessor_removed",
      project_id:$project, location:"global", bucket:"_Default", view:"_Default",
      member:$member, role:"roles/logging.viewAccessor", verified_absent:true,
      policy:$policy[0]}' > "${receipt_file}" || {
        rm -f "${policy_file}" "${receipt_file}"
        return 1
      }
  rm -f "${policy_file}"
  mv "${receipt_file}" "${LOGGING_VIEW_POLICY_RECEIPT}" || return 1
  verify_logging_view_removal_receipt
}

verify_logging_authority_removed() {
  local policy
  if ! policy="$(gcloud projects get-iam-policy "${PROJECT_ID}" --format=json)"; then
    echo "Unable to verify logging.admin cleanup." >&2
    return 1
  fi
  if ! jq -e --arg member "${DEPLOYER_MEMBER}" \
    'type == "object" and
     ([.bindings[]? | select(.role == "roles/logging.admin") | .members[]?] | any(. == $member) | not)' \
    <<<"${policy}" >/dev/null; then
    echo "Temporary logging.admin cleanup is unverified." >&2
    return 1
  fi
  verify_logging_view_removal_receipt
}

remove_logging_authority() {
  local attempt view_verified=false status=0

  # logging.views.getIamPolicy is provided by the temporary logging.admin
  # grant. Prove view-accessor removal before dropping that grant, then retain
  # the exact policy as the terminal cleanup receipt. Repeated cleanup calls may
  # reuse the receipt because each authority grant invalidates it first.
  if verify_logging_view_removal_receipt >/dev/null 2>&1; then
    view_verified=true
  fi
  if [[ "${view_verified}" != "true" ]]; then
    for attempt in $(seq 1 3); do
      gcloud logging views remove-iam-policy-binding _Default --bucket _Default --location global \
        --project "${PROJECT_ID}" --member "${DEPLOYER_MEMBER}" --role roles/logging.viewAccessor \
        --quiet >/dev/null 2>&1 || true
      if capture_logging_view_removal_receipt; then
        view_verified=true
        break
      fi
      sleep 2
    done
  fi
  [[ "${view_verified}" == "true" ]] || status=1

  # Even if view verification is unavailable, minimize residual authority by
  # removing logging.admin. The missing receipt keeps the workflow failed closed
  # and requires an independently authorized cleanup audit before any retry.
  gcloud projects remove-iam-policy-binding "${PROJECT_ID}" --member "${DEPLOYER_MEMBER}" \
    --role roles/logging.admin --condition=None --quiet >/dev/null 2>&1 || true
  verify_logging_authority_removed || status=1
  return "${status}"
}

remove_execution_authority() {
  local job status=0
  for job in "${ADMIN_JOB}" "${PRODUCER_JOBS[@]}"; do
    gcloud run jobs remove-iam-policy-binding "${job}" --project "${PROJECT_ID}" --region "${REGION}" \
      --member "${DEPLOYER_MEMBER}" --role roles/run.jobsExecutorWithOverrides --quiet >/dev/null 2>&1 || true
  done
  remove_logging_authority || status=1
  verify_execution_authority_removed || status=1
  return "${status}"
}

verify_execution_authority_removed() {
  local job policy
  for job in "${ADMIN_JOB}" "${PRODUCER_JOBS[@]}"; do
    if ! policy="$(gcloud run jobs get-iam-policy "${job}" --project "${PROJECT_ID}" --region "${REGION}" --format=json)"; then
      echo "Unable to verify execution-authority cleanup on ${job}." >&2
      return 1
    fi
    if ! jq -e --arg member "${DEPLOYER_MEMBER}" \
      'type == "object" and
       ([.bindings[]? | select(.role == "roles/run.jobsExecutorWithOverrides") | .members[]?] | any(. == $member) | not)' \
      <<<"${policy}" >/dev/null; then
      echo "Temporary execution-authority cleanup is unverified on ${job}." >&2
      return 1
    fi
  done
  verify_logging_authority_removed
}

latest_execution_name() {
  local job="$1"
  local execute_result="${2:-}"
  local execution=""

  if [[ -n "${execute_result}" && -s "${execute_result}" ]]; then
    if ! execution="$(jq -r '.metadata.name // .name // empty' "${execute_result}")"; then
      echo "Unable to parse the execution command response for ${job}." >&2
      return 1
    fi
  fi

  if [[ -z "${execution}" ]]; then
    for attempt in $(seq 1 12); do
      if ! execution="$(gcloud run jobs describe "${job}" \
        --project "${PROJECT_ID}" \
        --region "${REGION}" \
        --format='value(status.latestCreatedExecution.name)')"; then
        execution=""
      fi
      [[ -n "${execution}" ]] && break
      sleep 5
    done
  fi

  [[ -n "${execution}" ]] || {
    echo "Unable to resolve the latest execution for ${job}." >&2
    return 1
  }
  case "${execution}" in
    "${job}-"*) ;;
    *)
      echo "Execution receipt ${execution} does not belong to ${job}." >&2
      return 1
      ;;
  esac
  printf '%s\n' "${execution}"
}

execute_admin_init() {
  local result="${EVIDENCE_DIR}/admin-init-execute.json"
  if ! gcloud run jobs execute "${ADMIN_JOB}" --project "${PROJECT_ID}" --region "${REGION}" \
    --wait --format=json > "${result}"; then
    echo "Runtime v2 admin initialization failed." >&2
    return 1
  fi
  latest_execution_name "${ADMIN_JOB}" "${result}" > "${EVIDENCE_DIR}/admin-init-execution.txt"
}

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
    if ! payload="$(jq -c '[.[] | .textPayload? | select(type == "string") | fromjson? | select(type == "object" and has("heads") and has("latest_runs"))][-1] // empty' "${logs}")"; then
      payload=""
    fi
    [[ -n "${payload}" ]] && break
    sleep 5
  done
  [[ -n "${payload}" ]] || { echo "No Runtime v2 status payload was emitted by ${execution}." >&2; return 1; }
  printf '%s\n' "${payload}" | jq . > "${output}"
}

execute_producer() {
  local logical_name="$1"
  local trigger="$2"
  local stem="$3"
  local job="polititrack-${logical_name}"
  local execute_result="${EVIDENCE_DIR}/${stem}-${logical_name}-execute.json"
  if ! gcloud run jobs execute "${job}" --project "${PROJECT_ID}" --region "${REGION}" \
    --update-env-vars "POLITITRACK_TRIGGER_SOURCE=${trigger},SOURCE_REVISION=${RUNTIME_SOURCE_REVISION}" \
    --wait --format=json > "${execute_result}"; then
    echo "Runtime v2 producer execution ${job} failed." >&2
    return 1
  fi
  latest_execution_name "${job}" "${execute_result}" | tee "${EVIDENCE_DIR}/${stem}-${logical_name}-execution.txt"
}

web_policy_has_public_invoker() {
  local policy status
  if ! policy="$(gcloud run services get-iam-policy "${WEB_SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --format=json)"; then
    echo "Unable to read the Runtime v2 web IAM policy." >&2
    return 2
  fi
  if ! jq -e 'type == "object"' <<<"${policy}" >/dev/null; then
    echo "Runtime v2 web IAM policy is malformed." >&2
    return 2
  fi
  if jq -e '[.bindings[]? | select(.role == "roles/run.invoker") | .members[]?] | any(. == "allUsers")' \
    <<<"${policy}" >/dev/null; then
    return 0
  else
    status=$?
    [[ "${status}" == "1" ]] && return 1
    echo "Unable to evaluate the Runtime v2 web IAM policy." >&2
    return 2
  fi
}

verify_web_private() {
  local status
  if web_policy_has_public_invoker; then
    echo "Runtime v2 web service unexpectedly has a public invoker." >&2
    return 1
  else
    status=$?
  fi
  [[ "${status}" == "1" ]] || {
    echo "Runtime v2 web privacy could not be verified." >&2
    return 1
  }
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

ensure_legacy_workflow_state() {
  local workflow="$1"
  local expected="$2"
  local action state attempt

  case "${expected}" in
    active) action="enable" ;;
    disabled_manually) action="disable" ;;
    *)
      echo "Unsupported target state for legacy workflow ${workflow}: ${expected}." >&2
      return 1
      ;;
  esac

  if ! state="$(legacy_workflow_state "${workflow}")"; then
    echo "Unable to read legacy workflow ${workflow}." >&2
    return 1
  fi
  [[ "${state}" == "${expected}" ]] && return 0
  if [[ "${state}" != "active" && "${state}" != "disabled_manually" ]]; then
    echo "Legacy workflow ${workflow} is in unsupported state ${state}." >&2
    return 1
  fi

  # GitHub returns HTTP 403 when enable/disable is requested for a workflow
  # that is already in the requested state. Read before writing, and if the
  # mutation loses a race, accept it only after the target state is proven.
  if ! gh api --method PUT \
    "repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow}/${action}" \
    >/dev/null; then
    if state="$(legacy_workflow_state "${workflow}" 2>/dev/null)" && [[ "${state}" == "${expected}" ]]; then
      return 0
    fi
    echo "Legacy workflow ${workflow} transition to ${expected} failed; current state is ${state:-unreadable}." >&2
    return 1
  fi

  for attempt in $(seq 1 12); do
    if state="$(legacy_workflow_state "${workflow}" 2>/dev/null)"; then
      [[ "${state}" == "${expected}" ]] && return 0
      if [[ "${state}" != "active" && "${state}" != "disabled_manually" ]]; then
        echo "Legacy workflow ${workflow} entered unsupported state ${state}." >&2
        return 1
      fi
    else
      state=""
    fi
    sleep 2
  done

  echo "Legacy workflow ${workflow} is ${state:-unreadable}, expected ${expected}." >&2
  return 1
}

verify_legacy_workflows_state() {
  local expected="$1" workflow state
  for workflow in "${LEGACY_WORKFLOWS[@]}"; do
    if ! state="$(legacy_workflow_state "${workflow}")"; then
      echo "Unable to verify legacy workflow ${workflow}." >&2
      return 1
    fi
    [[ "${state}" == "${expected}" ]] || { echo "Legacy workflow ${workflow} is ${state}, expected ${expected}." >&2; return 1; }
  done
}

disable_legacy_workflows() {
  local workflow
  for workflow in "${LEGACY_WORKFLOWS[@]}"; do
    ensure_legacy_workflow_state "${workflow}" disabled_manually || return 1
  done
  verify_legacy_workflows_state disabled_manually
}

enable_legacy_workflows() {
  local workflow
  for workflow in "${LEGACY_WORKFLOWS[@]}"; do
    ensure_legacy_workflow_state "${workflow}" active || return 1
  done
  verify_legacy_workflows_state active
}

drain_legacy_workflows() {
  local workflow active_file="${EVIDENCE_DIR}/legacy-active-run-ids.txt"
  : > "${active_file}" || return 1
  for workflow in "${LEGACY_WORKFLOWS[@]}"; do
    if ! gh api --paginate "repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow}/runs?per_page=100" \
      --jq '.workflow_runs[] | select(.status != "completed") | .id' >> "${active_file}"; then
      echo "Unable to inventory active runs for ${workflow}." >&2
      return 1
    fi
  done
  sort -u -o "${active_file}" "${active_file}" || return 1
  local run_id status count
  while IFS= read -r run_id; do
    [[ -n "${run_id}" ]] || continue
    for attempt in $(seq 1 180); do
      if status="$(gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${run_id}" --jq '.status')"; then
        [[ "${status}" == "completed" ]] && break
      else
        status="unreadable"
      fi
      sleep 10
    done
    [[ "${status}" == "completed" ]] || { echo "Legacy run ${run_id} did not drain." >&2; return 1; }
  done < "${active_file}"
  for workflow in "${LEGACY_WORKFLOWS[@]}"; do
    if ! count="$(gh api "repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow}/runs?per_page=100" \
      --jq '[.workflow_runs[] | select(.status != "completed")] | length')"; then
      echo "Unable to verify drained runs for ${workflow}." >&2
      return 1
    fi
    [[ "${count}" == "0" ]] || {
      echo "Legacy workflow ${workflow} still has active runs." >&2; return 1;
    }
  done
}

legacy_recovery_state_file() {
  local workflow="$1"
  case "${workflow}" in
    legislative_trade_tracker_v2.yml) printf '%s\n' "${EVIDENCE_DIR}/legacy-recovery-legislative.json" ;;
    executive_trade_tracker.yml) printf '%s\n' "${EVIDENCE_DIR}/legacy-recovery-executive.json" ;;
    *) echo "Unsupported legacy recovery workflow ${workflow}." >&2; return 1 ;;
  esac
}

legacy_recovery_workflow_id() {
  local workflow="$1"
  case "${workflow}" in
    legislative_trade_tracker_v2.yml) printf '%s\n' '345003824' ;;
    executive_trade_tracker.yml) printf '%s\n' '344663671' ;;
    *) echo "Unsupported legacy recovery workflow ${workflow}." >&2; return 1 ;;
  esac
}

write_legacy_recovery_pending() {
  local workflow="$1" workflow_id="$2" output="$3"
  local temporary="${output}.tmp"
  if ! jq -n \
    --arg workflow "${workflow}" \
    --argjson workflow_id "${workflow_id}" \
    --arg control_revision "${CONTROL_REVISION}" \
    '{schema_version:1, result:"legacy_recovery_dispatch_pending",
      workflow:$workflow, workflow_id:$workflow_id,
      control_revision:$control_revision,
      dispatch_attempted:true, run_id:null, run_url:null,
      status:"pending", conclusion:null}' > "${temporary}"; then
    rm -f "${temporary}"
    return 1
  fi
  mv "${temporary}" "${output}"
}

write_legacy_recovery_acceptance() {
  local state_file="$1" dispatch_json="$2"
  local temporary="${state_file}.tmp"
  if ! jq -n \
    --slurpfile state "${state_file}" \
    --argjson dispatch "${dispatch_json}" \
    '$state[0] + {result:"legacy_recovery_dispatch_accepted",
                  run_id:$dispatch.workflow_run_id,
                  run_url:$dispatch.html_url,
                  api_run_url:$dispatch.run_url,
                  status:"requested", conclusion:null}' > "${temporary}"; then
    rm -f "${temporary}"
    return 1
  fi
  mv "${temporary}" "${state_file}"
}

write_legacy_recovery_observation() {
  local state_file="$1" run_json="$2" result="$3"
  local temporary="${state_file}.tmp"
  if ! jq -n \
    --arg result "${result}" \
    --slurpfile state "${state_file}" \
    --argjson run "${run_json}" \
    '$state[0] + {result:$result, run_id:$run.id, run_url:$run.html_url,
                  run_attempt:$run.run_attempt,
                  status:$run.status, conclusion:$run.conclusion}' > "${temporary}"; then
    rm -f "${temporary}"
    return 1
  fi
  mv "${temporary}" "${state_file}"
}

ensure_legacy_recovery_dispatch() {
  local workflow="$1" state_file workflow_id run_id dispatch_json
  if ! state_file="$(legacy_recovery_state_file "${workflow}")"; then
    return 1
  fi
  if ! workflow_id="$(legacy_recovery_workflow_id "${workflow}")"; then
    return 1
  fi
  [[ "${CONTROL_REVISION:-}" =~ ^[0-9a-f]{40}$ ]] || {
    echo "Certified control revision is unavailable for legacy recovery." >&2
    return 1
  }

  if [[ -e "${state_file}" ]]; then
    if ! jq -e --arg workflow "${workflow}" --argjson workflow_id "${workflow_id}" \
      --arg control_revision "${CONTROL_REVISION}" \
      'type == "object" and .schema_version == 1 and .workflow == $workflow and
       .workflow_id == $workflow_id and .control_revision == $control_revision and
       .dispatch_attempted == true and
       (.result == "legacy_recovery_dispatch_pending" or
        .result == "legacy_recovery_dispatch_accepted" or
        .result == "legacy_recovery_run_succeeded") and
       ((.result == "legacy_recovery_dispatch_pending" and .run_id == null) or
        (.result != "legacy_recovery_dispatch_pending" and (.run_id | type) == "number" and .run_id > 0))' \
      "${state_file}" >/dev/null; then
      echo "Legacy recovery dispatch state is invalid for ${workflow}." >&2
      return 1
    fi
    run_id="$(jq -r '.run_id // empty' "${state_file}")" || return 1
    if [[ -n "${run_id}" ]]; then
      printf '%s\n' "${run_id}"
      return 0
    fi
    echo "Legacy recovery dispatch remains ambiguous for ${workflow}; refusing to retry it." >&2
    return 1
  fi

  write_legacy_recovery_pending "${workflow}" "${workflow_id}" "${state_file}" || return 1
  if ! dispatch_json="$(gh api \
    "repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow}/dispatches" \
    --method POST \
    -H 'Accept: application/vnd.github+json' \
    -H 'X-GitHub-Api-Version: 2026-03-10' \
    -f ref=main)"; then
    echo "Legacy recovery dispatch failed or is ambiguous for ${workflow}; refusing to retry it." >&2
    return 1
  fi
  if ! jq -e --arg repository "${GITHUB_REPOSITORY}" \
    'type == "object" and (.workflow_run_id | type) == "number" and .workflow_run_id > 0 and
     .run_url == ("https://api.github.com/repos/" + $repository + "/actions/runs/" + (.workflow_run_id | tostring)) and
     .html_url == ("https://github.com/" + $repository + "/actions/runs/" + (.workflow_run_id | tostring))' \
    <<<"${dispatch_json}" >/dev/null; then
    echo "Legacy recovery dispatch did not return an exact canonical run for ${workflow}." >&2
    return 1
  fi
  write_legacy_recovery_acceptance "${state_file}" "${dispatch_json}" || return 1
  jq -r '.workflow_run_id' <<<"${dispatch_json}"
}

wait_legacy_recovery_success() {
  local workflow="$1" run_id="$2" state_file workflow_id response status conclusion
  if ! state_file="$(legacy_recovery_state_file "${workflow}")"; then
    return 1
  fi
  if ! workflow_id="$(legacy_recovery_workflow_id "${workflow}")"; then
    return 1
  fi
  for attempt in $(seq 1 180); do
    if response="$(gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${run_id}")"; then
      if jq -e --arg workflow "${workflow}" --argjson workflow_id "${workflow_id}" \
        --argjson run_id "${run_id}" --arg control_revision "${CONTROL_REVISION}" \
        'type == "object" and .id == $run_id and .event == "workflow_dispatch" and
         .head_branch == "main" and .path == (".github/workflows/" + $workflow) and
         .workflow_id == $workflow_id and .head_sha == $control_revision and
         .run_attempt == 1 and
         .head_repository.id == 1349678672 and
         ((.head_repository.full_name // "") == env.GITHUB_REPOSITORY) and
         (.status | type) == "string" and (.conclusion == null or (.conclusion | type) == "string")' \
        <<<"${response}" >/dev/null; then
        status="$(jq -r '.status' <<<"${response}")" || return 1
        conclusion="$(jq -r '.conclusion // empty' <<<"${response}")" || return 1
        if [[ "${status}" == "completed" ]]; then
          if [[ "${conclusion}" != "success" ]]; then
            echo "Legacy recovery run ${run_id} for ${workflow} concluded ${conclusion:-unknown}." >&2
            return 1
          fi
          write_legacy_recovery_observation \
            "${state_file}" "${response}" legacy_recovery_run_succeeded || return 1
          return 0
        fi
      fi
    fi
    sleep 10
  done
  echo "Legacy recovery run ${run_id} for ${workflow} did not complete successfully." >&2
  return 1
}

dispatch_legacy_recovery_tracked() {
  local workflow run_id state_file
  local workflows=(legislative_trade_tracker_v2.yml executive_trade_tracker.yml)
  local -A run_ids=()
  for workflow in "${workflows[@]}"; do
    if ! run_id="$(ensure_legacy_recovery_dispatch "${workflow}")"; then
      echo "Legacy recovery dispatch could not be proven for ${workflow}." >&2
      return 1
    fi
    run_ids[${workflow}]="${run_id}"
  done
  for workflow in "${workflows[@]}"; do
    wait_legacy_recovery_success "${workflow}" "${run_ids[${workflow}]}" || return 1
  done

  local temporary="${EVIDENCE_DIR}/legacy-recovery-dispatch.json.tmp"
  local legislative_state executive_state
  legislative_state="$(legacy_recovery_state_file legislative_trade_tracker_v2.yml)" || return 1
  executive_state="$(legacy_recovery_state_file executive_trade_tracker.yml)" || return 1
  if ! jq -n \
    --slurpfile legislative "${legislative_state}" \
    --slurpfile executive "${executive_state}" \
    '{schema_version:1, result:"legacy_recovery_runs_succeeded",
      workflows:[$legislative[0], $executive[0]]}' > "${temporary}"; then
    rm -f "${temporary}"
    return 1
  fi
  mv "${temporary}" "${EVIDENCE_DIR}/legacy-recovery-dispatch.json"
}

dispatch_legacy_recovery() {
  dispatch_legacy_recovery_tracked
}

verify_public_web() {
  local expected_digest="$1" url
  if ! url="$(gcloud run services describe "${WEB_SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --format='value(status.url)')"; then
    echo "Unable to resolve the Runtime v2 web URL." >&2
    return 1
  fi
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
  jq -e '.status == "ok" and .service == "polititrack-runtime-v2"' \
    "${EVIDENCE_DIR}/healthz.json" >/dev/null || {
      echo "Runtime v2 health response is invalid." >&2
      return 1
    }
  jq -e --arg digest "${expected_digest}" \
    '.status == "ready" and .dashboard == true and .snapshot_sha256 == $digest' \
    "${EVIDENCE_DIR}/readyz.json" >/dev/null || {
      echo "Runtime v2 readiness response is invalid." >&2
      return 1
    }
  local served
  served="$(awk 'BEGIN{IGNORECASE=1} /^X-PolitiTrack-Snapshot:/ {gsub("\r", "", $2); print $2}' "${EVIDENCE_DIR}/dashboard.headers" | tail -1)"
  [[ "${served}" == "${expected_digest}" ]] || { echo "Served dashboard digest mismatch." >&2; return 1; }
  printf '%s\n' "${served}" > "${EVIDENCE_DIR}/served-dashboard-sha256.txt"
}
