#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASH_BIN="${BASH:-bash}"
TEMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEMP_ROOT"' EXIT

echo "PolitiTrack retired recovery-overlay verification"
echo

"$BASH_BIN" -n "$SCRIPT_DIR/apply.sh" "$SCRIPT_DIR/verify.sh"
echo "[pass] shell syntax"

MOCK_TARGET="$TEMP_ROOT/target"
mkdir -p "$MOCK_TARGET"
printf 'preserve me\n' > "$MOCK_TARGET/user-data.txt"
BEFORE_HASH="$(sha256sum "$MOCK_TARGET/user-data.txt")"
if "$BASH_BIN" "$SCRIPT_DIR/apply.sh" "$MOCK_TARGET" >/dev/null 2>&1; then
  echo "Retired apply.sh unexpectedly returned success." >&2
  exit 1
fi
AFTER_HASH="$(sha256sum "$MOCK_TARGET/user-data.txt")"
[[ "$BEFORE_HASH" == "$AFTER_HASH" ]]
[[ "$(find "$MOCK_TARGET" -mindepth 1 -maxdepth 1 -printf '%f\n')" == "user-data.txt" ]]
echo "[pass] retired installer fails closed without changing target data"

mapfile -t BUNDLE_FILES < <(
  find "$SCRIPT_DIR/repo-files" -type f -printf '%P\n' | LC_ALL=C sort
)
[[ "${#BUNDLE_FILES[@]}" -eq 1 ]]
[[ "${BUNDLE_FILES[0]}" == "RETIRED.md" ]]
[[ -z "$(find "$SCRIPT_DIR/repo-files" -type l -print -quit)" ]]
echo "[pass] retired payload contains no installable files or symlinks"

test ! -e "$SCRIPT_DIR/.github/workflows/legislative_trade_tracker.yml"
test ! -e "$SCRIPT_DIR/.github/workflows/import_migrated_state.yml"

python - "$SCRIPT_DIR" <<'PY'
from pathlib import Path
import sys
import yaml

root = Path(sys.argv[1])
workflow_dir = root / ".github" / "workflows"
expected_names = {
    "ai_filing_analyst.yml": "AI filing analyst and paper portfolio",
    "executive_trade_tracker.yml": "Executive purchase tracker",
    "filing_simulation.yml": "Run $10K portfolio simulator",
    "investor_edge_tests.yml": "Investor Edge tests",
    "legislative_trade_tracker_v2.yml": "Legislative purchase tracker v2",
    "manual_test.yml": "Run Simulation",
    "publish_trade_dashboard.yml": "Publish government trade dashboard",
}
available = {path.name for path in workflow_dir.glob("*.yml")}
missing = set(expected_names) - available
assert not missing, f"Missing canonical workflows: {sorted(missing)}"

parsed = {}
for filename, expected_name in expected_names.items():
    path = workflow_dir / filename
    workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(workflow, dict), path
    assert workflow.get("name") == expected_name, (path, workflow.get("name"))
    assert isinstance(workflow.get("on"), dict), path
    assert isinstance(workflow.get("jobs"), dict), path
    parsed[filename] = workflow

expected_schedules = {
    "legislative_trade_tracker_v2.yml": ("7,22,37,52 * * * *", "America/New_York"),
    "executive_trade_tracker.yml": ("13,43 * * * *", "America/New_York"),
}
for filename, (cron, timezone) in expected_schedules.items():
    schedules = parsed[filename]["on"]["schedule"]
    assert schedules == [{"cron": cron, "timezone": timezone}], (filename, schedules)

legislative_triggers = parsed["legislative_trade_tracker_v2.yml"]["on"]
assert set(legislative_triggers) == {"schedule", "workflow_dispatch"}, legislative_triggers
trigger_input = legislative_triggers["workflow_dispatch"]["inputs"]["trigger_source"]
assert trigger_input["required"] == "false"
assert trigger_input["default"] == "workflow_dispatch"
assert trigger_input["type"] == "choice"
assert trigger_input["options"] == ["workflow_dispatch", "external_scheduler"]

texts = {
    filename: (workflow_dir / filename).read_text(encoding="utf-8")
    for filename in expected_names
}
legislative = texts["legislative_trade_tracker_v2.yml"]
executive = texts["executive_trade_tracker.yml"]
analyst = texts["ai_filing_analyst.yml"]
publisher = texts["publish_trade_dashboard.yml"]
manual = texts["manual_test.yml"]
simulator = texts["filing_simulation.yml"]

assert "--branch legislative --source all" in legislative
assert "--no-notify" not in legislative
assert "--validate-durable" in legislative
assert "--require-restore-receipt" in legislative
assert "--validate-protected-upload" not in legislative
assert "--require-controlled-validation-receipt" not in legislative
assert "--require-run-provenance" not in legislative
assert "--require-notifications-suppressed" not in legislative
assert "--require-no-notification-eligible-records" not in legislative
assert 'POLITITRACK_CONTROLLED_VALIDATION: "false"' in legislative
assert "inputs.validation_acknowledged" not in legislative
assert ".trade-tracker/legislative/source-status.json" in legislative
assert ".trade-tracker/legislative/restore-receipt.json" in legislative
assert ".trade-tracker/legislative/controlled-validation-receipt.json" in legislative
for marker in (
    "predecessor_artifact_id",
    "predecessor_artifact_api_digest",
    "downloaded_zip_sha256",
    "predecessor_run_id",
    "predecessor_run_attempt",
    "predecessor_head_sha",
    "predecessor_workflow_id",
    "restored_state_sha256",
):
    assert marker in legislative
assert "LEGISLATIVE_HEALTHCHECKS_PING_URL" in legislative
assert "PUSHOVER_API_TOKEN" in legislative
assert "PUSHOVER_USER_KEY" in legislative
assert "github.event.workflow_run.name != 'Legislative purchase tracker v2'" not in analyst
assert "github.event.workflow_run.name == 'Legislative purchase tracker v2'" not in publisher
assert "github.event.workflow_run.event == 'workflow_dispatch'" not in publisher

legislative_steps = parsed["legislative_trade_tracker_v2.yml"]["jobs"]["track"]["steps"]
durable_step = next(step for step in legislative_steps if step.get("id") == "durable_validation")
state_upload = next(step for step in legislative_steps if step.get("name") == "Upload protected tracker state")
diagnostic_upload = next(step for step in legislative_steps if step.get("name") == "Upload run outputs")
assert durable_step.get("continue-on-error", "false") == "false"
assert not any(step.get("id") == "state_validation" for step in legislative_steps)
assert "steps.tracker.outcome == 'success'" in state_upload["if"]
assert "steps.durable_validation.outcome == 'success'" in state_upload["if"]
assert "hashFiles" not in state_upload["if"]
assert state_upload["with"]["if-no-files-found"] == "error"
assert "always()" in diagnostic_upload["if"]
assert diagnostic_upload.get("continue-on-error") == "true"
assert any(step.get("name") == "Signal tracker start" for step in legislative_steps)
assert any(step.get("name") == "Signal tracker terminal result" for step in legislative_steps)
assert any(step.get("name") == "Send Pushover failure notification" for step in legislative_steps)

# Protected state is artifact-only. Dependency caching configured through setup-python
# is acceptable; direct Actions cache restoration or promotion is not.
all_workflows = "\n".join(texts.values())
assert "actions/cache/restore" not in all_workflows
assert "actions/cache/save" not in all_workflows

for text, artifact in (
    (legislative, "legislative-tracker-state"),
    (executive, "executive-tracker-state"),
):
    assert "initialize_state:" not in text
    assert "bootstrap_alerts:" not in text
    assert 'ALLOW_STATE_INITIALIZATION: "false"' in text
    assert 'BOOTSTRAP_ALERTS: "false"' in text
    assert "refusing to initialize protected state" in text
    assert f"name: {artifact}" in text

assert "No authoritative ${artifact_name} artifact is available; refusing to initialize protected state." in analyst
assert "name: ai-analysis-state" in analyst
assert "Legislative purchase tracker v2" in analyst
assert "Legislative purchase tracker\n" not in analyst

# Every protected-state consumer must bind candidates to one exact producer workflow,
# repository, default branch, successful attempt/job, compatible producer commit, and
# the artifact's creation-time window. It must also reject a predecessor when a later
# successful writer attempt exists without a consumable artifact.
protected_consumers = {
    "legislative": legislative,
    "executive": executive,
    "analyst": analyst,
    "manual simulation": manual,
    "$10K simulator": simulator,
    "publisher": publisher,
}
for label, text in protected_consumers.items():
    for marker in (
        ".workflow_run.id",
        ".run_attempt // 1",
        ".run_started_at // \"\"",
        "next_attempt_started_at",
        ".name // \"\"",
        ".path // \"\"",
        ".head_branch // \"\"",
        ".conclusion // \"\"",
        ".repository.id // \"\"",
        ".head_sha // \"\"",
        "GITHUB_REPOSITORY_ID",
        "/compare/${run_head_sha}...${consumer_sha}",
        "high-water violation",
    ):
        assert marker in text, (label, marker)

# Most consumers query one artifact page and order it in jq. The persistent simulator
# deliberately scans every page and then applies one global newest-first order, avoiding
# the false authority boundary created by a 100-artifact page.
for label, text in protected_consumers.items():
    if label != "$10K simulator":
        assert "sort_by(.created_at)" in text, (label, "newest-first artifact order")
for marker in (
    "list_artifacts_newest_first()",
    '"/repos/${GITHUB_REPOSITORY}/actions/artifacts"',
    '-f name="$requested_name"',
    "-f per_page=100",
    '-f page="$artifact_page"',
    ".artifacts[] | select(.expired == false) | [.id, .workflow_run.id, .created_at] | @tsv",
    "artifact_count < 100",
    "((artifact_page += 1))",
    "LC_ALL=C sort -t $'\\t' -k3,3r -k1,1nr",
    'list_artifacts_newest_first "$artifact_name"',
    "list_artifacts_newest_first simulation-state",
):
    assert marker in simulator, ("$10K simulator paginated ordering", marker)
assert simulator.count("list_artifacts_newest_first()") == 2

for text in (legislative, executive, analyst):
    assert '"$run_path" != ".github/workflows/${workflow_file}"' in text
    assert '"$run_conclusion" != "success"' in text
    assert "successful_state_jobs" in text
    assert "producer_attempt" in text

for text in (manual, simulator, publisher):
    assert '"$run_path" == ".github/workflows/${workflow_file}"' in text
    assert '"$run_conclusion" == "success"' in text
    assert "successful_" in text and "_jobs" in text

producer_bindings = {
    "legislative_trade_tracker_v2.yml": "Legislative purchase tracker v2",
    "executive_trade_tracker.yml": "Executive purchase tracker",
    "ai_filing_analyst.yml": "AI filing analyst and paper portfolio",
}
for consumer in (analyst, manual, simulator, publisher):
    for workflow_file, workflow_name in producer_bindings.items():
        assert workflow_file in consumer, (workflow_file, "missing consumer binding")
        assert workflow_name in consumer, (workflow_name, "missing consumer binding")

for artifact in ("legislative-tracker-state", "executive-tracker-state", "ai-analysis-state"):
    for consumer in (analyst, manual, simulator, publisher):
        assert artifact in consumer, (artifact, "missing consumer restore")

assert "github.event.workflow_run.conclusion == 'success'" in publisher
assert "github.event.workflow_run.head_branch == github.event.repository.default_branch" in publisher

# Both simulations are present and write only simulation-namespaced artifacts. The
# persistent $10K simulation is an exact publisher trigger/input; the one-run Investor
# Edge acceptance dashboard remains short-lived and separate.
assert "name: simulation-dashboard-${{ github.run_id }}-${{ github.run_attempt }}" in manual
assert "name: simulation-state" in simulator
assert "pages: write" not in manual
assert "pages: write" not in simulator
for artifact in ("legislative-tracker-state", "executive-tracker-state", "ai-analysis-state"):
    assert f"name: {artifact}" not in manual
    assert f"name: {artifact}" not in simulator

for marker in (
    "Run $10K portfolio simulator",
    "actions/artifacts?name=simulation-state",
    '"$run_path" == ".github/workflows/filing_simulation.yml"',
    '[.jobs[] | select(.name == "simulate" and .conclusion == "success")] | length',
    "simulation result run URL does not match its producer",
    "--simulation-dir dashboard-input/simulation",
    "trade-dashboard-site/data/simulation.json",
):
    assert marker in publisher, marker

print("[pass] artifact-only authority, paginated newest-first provenance/high-water guards, dual simulations, and publisher integration")
PY

(
  cd "$SCRIPT_DIR"
  sha256sum --check MANIFEST.sha256
)
echo "[pass] deterministic recovery-record manifest"

echo
echo "VERIFICATION PASSED"
