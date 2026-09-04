#!/usr/bin/env bash
# Apply the one missing, bucket-scoped metadata permission required by the
# Runtime v2 schema-admin job. This controller does not execute a Cloud Run job,
# enable a scheduler, expose the web service, or transfer production authority.

set -Eeuo pipefail

: "${PROJECT_ID:?PROJECT_ID is required}"
: "${PROJECT_NUMBER:?PROJECT_NUMBER is required}"
: "${REGION:?REGION is required}"
: "${VAULT_BUCKET:?VAULT_BUCKET is required}"
: "${ADMIN_SERVICE_ACCOUNT:?ADMIN_SERVICE_ACCOUNT is required}"
: "${REQUIRED_ROLE:?REQUIRED_ROLE is required}"
: "${WEB_SERVICE:?WEB_SERVICE is required}"
: "${SQL_INSTANCE:?SQL_INSTANCE is required}"
: "${EVIDENCE_DIR:?EVIDENCE_DIR is required}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
: "${GITHUB_SHA:?GITHUB_SHA is required}"

mkdir -p "${EVIDENCE_DIR}"

[[ "$(git rev-parse HEAD)" == "${GITHUB_SHA}" ]] || {
  echo "Checkout drifted from the triggering revision." >&2
  exit 1
}
live_sha="$(gh api "repos/${GITHUB_REPOSITORY}/commits/main" --jq '.sha')"
[[ "${live_sha}" == "${GITHUB_SHA}" ]] || {
  echo "Canonical main advanced before the IAM repair." >&2
  exit 1
}
actual_number="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
[[ "${actual_number}" == "${PROJECT_NUMBER}" ]] || {
  echo "Immutable project boundary mismatch." >&2
  exit 1
}

: > "${EVIDENCE_DIR}/scheduler-states.ndjson"
for scheduler in \
  polititrack-legislative \
  polititrack-executive \
  polititrack-ai \
  polititrack-dashboard \
  polititrack-vault-lifecycle; do
  state="$(gcloud scheduler jobs describe "${scheduler}" \
    --project "${PROJECT_ID}" --location "${REGION}" --format='value(state)')"
  jq -cn --arg scheduler "${scheduler}" --arg state "${state}" \
    '{scheduler:$scheduler,state:$state}' >> "${EVIDENCE_DIR}/scheduler-states.ndjson"
  [[ "${state}" == "PAUSED" ]] || {
    echo "Scheduler ${scheduler} is ${state}, expected PAUSED." >&2
    exit 1
  }
done

gcloud run services get-iam-policy "${WEB_SERVICE}" \
  --project "${PROJECT_ID}" --region "${REGION}" --format=json \
  > "${EVIDENCE_DIR}/web-iam.json"
if jq -e '[.bindings[]? | select(.role == "roles/run.invoker") | .members[]?] | any(. == "allUsers")' \
  "${EVIDENCE_DIR}/web-iam.json" >/dev/null; then
  echo "Runtime v2 web service is public; refusing the repair." >&2
  exit 1
fi

gcloud sql instances describe "${SQL_INSTANCE}" --project "${PROJECT_ID}" --format=json \
  > "${EVIDENCE_DIR}/cloud-sql.json"
jq -e '(.settings.ipConfiguration.ipv4Enabled // false) == false and
       ((.settings.ipConfiguration.privateNetwork // "") | length > 0)' \
  "${EVIDENCE_DIR}/cloud-sql.json" >/dev/null || {
    echo "Cloud SQL is not private-only." >&2
    exit 1
  }

: > "${EVIDENCE_DIR}/legacy-workflow-states.ndjson"
for workflow in \
  legislative_trade_tracker_v2.yml \
  executive_trade_tracker.yml \
  ai_filing_analyst.yml \
  publish_trade_dashboard.yml; do
  state="$(gh api "repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow}" --jq '.state')"
  case "${state}" in
    active|disabled_manually) ;;
    *)
      echo "Unsupported legacy workflow state ${workflow}=${state}." >&2
      exit 1
      ;;
  esac
  jq -cn --arg key "${workflow}" --arg value "${state}" \
    '{key:$key,value:$value}' >> "${EVIDENCE_DIR}/legacy-workflow-states.ndjson"
done
jq -s 'from_entries' "${EVIDENCE_DIR}/legacy-workflow-states.ndjson" \
  > "${EVIDENCE_DIR}/legacy-workflow-states.json"
jq -e '.["legislative_trade_tracker_v2.yml"] == "active" and
       .["executive_trade_tracker.yml"] == "active"' \
  "${EVIDENCE_DIR}/legacy-workflow-states.json" >/dev/null || {
    echo "The two legacy collectors are not available as the rollback route." >&2
    exit 1
  }

gcloud storage buckets describe "gs://${VAULT_BUCKET}" --format=json \
  > "${EVIDENCE_DIR}/bucket.json"
python - "${EVIDENCE_DIR}/bucket.json" "${VAULT_BUCKET}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    data = json.load(stream)
expected = sys.argv[2]
name = str(data.get("name") or data.get("id") or "").removeprefix("gs://")
iam = data.get("iamConfiguration") or data.get("iam_configuration") or {}

uniform = data.get("uniform_bucket_level_access")
if uniform is None:
    uniform = data.get("uniformBucketLevelAccess")
if uniform is None:
    uniform = iam.get("uniformBucketLevelAccess") or iam.get("uniform_bucket_level_access")
if isinstance(uniform, dict):
    uniform = uniform.get("enabled")

prevention = data.get("public_access_prevention")
if prevention is None:
    prevention = data.get("publicAccessPrevention")
if prevention is None:
    prevention = iam.get("publicAccessPrevention") or iam.get("public_access_prevention")

if name != expected:
    raise SystemExit(f"Vault bucket mismatch: {name!r} != {expected!r}")
if uniform is not True:
    raise SystemExit("Vault bucket does not enforce uniform bucket-level access")
if str(prevention).lower() != "enforced":
    raise SystemExit("Vault bucket does not enforce public-access prevention")
PY

gcloud projects get-iam-policy "${PROJECT_ID}" --format=json \
  > "${EVIDENCE_DIR}/project-iam.json"
python - "${EVIDENCE_DIR}/project-iam.json" "serviceAccount:${ADMIN_SERVICE_ACCOUNT}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    policy = json.load(stream)
member = sys.argv[2]
forbidden = []
for binding in policy.get("bindings", []):
    if member not in binding.get("members", []):
        continue
    role = binding.get("role", "")
    if role.startswith("roles/storage.") or role in {"roles/owner", "roles/editor", "roles/viewer"}:
        forbidden.append(role)
if forbidden:
    raise SystemExit(
        f"Admin service account already has broader project storage access: {sorted(forbidden)}"
    )
PY

gcloud storage buckets get-iam-policy "gs://${VAULT_BUCKET}" --format=json \
  > "${EVIDENCE_DIR}/bucket-iam-before.json"
gcloud storage buckets add-iam-policy-binding "gs://${VAULT_BUCKET}" \
  --member "serviceAccount:${ADMIN_SERVICE_ACCOUNT}" \
  --role "${REQUIRED_ROLE}" --quiet --format=none
gcloud storage buckets get-iam-policy "gs://${VAULT_BUCKET}" --format=json \
  > "${EVIDENCE_DIR}/bucket-iam-after.json"

python - \
  "${EVIDENCE_DIR}/bucket-iam-before.json" \
  "${EVIDENCE_DIR}/bucket-iam-after.json" \
  "serviceAccount:${ADMIN_SERVICE_ACCOUNT}" \
  "${REQUIRED_ROLE}" \
  "${EVIDENCE_DIR}/policy-change.json" <<'PY'
import json
import sys

before_path, after_path, member, role, output_path = sys.argv[1:]
with open(before_path, encoding="utf-8") as stream:
    before = json.load(stream)
with open(after_path, encoding="utf-8") as stream:
    after = json.load(stream)


def canonical(policy):
    result = {}
    for binding in policy.get("bindings", []):
        condition = json.dumps(
            binding.get("condition") or {}, sort_keys=True, separators=(",", ":")
        )
        key = (binding.get("role", ""), condition)
        result.setdefault(key, set()).update(binding.get("members", []))
    return result


old = canonical(before)
new = canonical(after)
keys = set(old) | set(new)
added = {
    (key, value)
    for key in keys
    for value in new.get(key, set()) - old.get(key, set())
}
removed = {
    (key, value)
    for key in keys
    for value in old.get(key, set()) - new.get(key, set())
}
expected_key = (role, "{}")
already_present = member in old.get(expected_key, set())
expected_added = set() if already_present else {(expected_key, member)}
if added != expected_added or removed:
    raise SystemExit(
        f"Unexpected bucket-IAM mutation: added={sorted(added)!r} removed={sorted(removed)!r}"
    )
if member not in new.get(expected_key, set()):
    raise SystemExit("Required direct bucket metadata grant is absent after repair")

direct_roles = sorted(key[0] for key, members in new.items() if member in members)
forbidden_roles = {
    "roles/storage.admin",
    "roles/storage.objectAdmin",
    "roles/storage.objectCreator",
    "roles/storage.objectUser",
    "roles/storage.objectViewer",
    "roles/storage.legacyBucketOwner",
    "roles/storage.legacyBucketReader",
    "roles/storage.legacyBucketWriter",
    "roles/storage.legacyObjectOwner",
    "roles/storage.legacyObjectReader",
}
unexpected = sorted(set(direct_roles) & forbidden_roles)
if unexpected:
    raise SystemExit(
        f"Admin service account has unintended object or legacy access: {unexpected}"
    )

receipt = {
    "already_present": already_present,
    "added_member": None if already_present else member,
    "role": role,
    "direct_roles_after": direct_roles,
    "only_expected_policy_change": True,
}
with open(output_path, "w", encoding="utf-8") as stream:
    json.dump(receipt, stream, indent=2, sort_keys=True)
    stream.write("\n")
PY

python - "${EVIDENCE_DIR}" "${GITHUB_SHA}" "${PROJECT_ID}" "${PROJECT_NUMBER}" \
  "${VAULT_BUCKET}" "${ADMIN_SERVICE_ACCOUNT}" "${REQUIRED_ROLE}" <<'PY'
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(sys.argv[1])
files = [
    "bucket.json",
    "bucket-iam-before.json",
    "bucket-iam-after.json",
    "project-iam.json",
    "cloud-sql.json",
    "web-iam.json",
    "legacy-workflow-states.json",
    "scheduler-states.ndjson",
    "policy-change.json",
]
digests = {
    name: hashlib.sha256((root / name).read_bytes()).hexdigest()
    for name in files
}
manifest = {
    "schema_version": 1,
    "result": "phase5_vault_admin_bucket_metadata_repaired",
    "repository_id": 1349678672,
    "control_revision": sys.argv[2],
    "project_id": sys.argv[3],
    "project_number": sys.argv[4],
    "bucket": sys.argv[5],
    "principal": "serviceAccount:" + sys.argv[6],
    "role": sys.argv[7],
    "scope": "bucket",
    "object_access_granted": False,
    "all_runtime_schedulers_paused": True,
    "vault_scheduler_paused": True,
    "runtime_web_public": False,
    "cloud_sql_private_only": True,
    "legacy_collectors_available": True,
    "producer_execution_performed": False,
    "production_authority_transferred": False,
    "phase4_dispatch_eligible": True,
    "created_at": datetime.now(timezone.utc).isoformat(),
    "evidence_sha256": digests,
}
(root / "manifest.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

(cd "${EVIDENCE_DIR}" && sha256sum manifest.json > manifest.sha256)
jq -e '.result == "phase5_vault_admin_bucket_metadata_repaired" and
       .role == "roles/storage.bucketViewer" and
       .object_access_granted == false and
       .phase4_dispatch_eligible == true' \
  "${EVIDENCE_DIR}/manifest.json" >/dev/null
(cd "${EVIDENCE_DIR}" && sha256sum -c manifest.sha256)
