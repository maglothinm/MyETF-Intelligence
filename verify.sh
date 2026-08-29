#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_FILES="$SCRIPT_DIR/repo-files"
REPORT="$SCRIPT_DIR/VERIFICATION.txt"
TEMP_ROOT="$(mktemp -d)"
BASH_BIN="${BASH:-bash}"
trap 'rm -rf "$TEMP_ROOT"' EXIT

if command -v tee >/dev/null 2>&1; then
  exec > >(tee "$REPORT") 2>&1
else
  exec > "$REPORT" 2>&1
fi

echo "PolitiTrack government trade tracker verification"
echo "UTC: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
echo "Python: $(python --version 2>&1)"
echo

"$BASH_BIN" -n "$SCRIPT_DIR/apply.sh" "$SCRIPT_DIR/verify.sh"
echo "[pass] shell syntax"

python -m compileall -q "$REPO_FILES/scripts" "$REPO_FILES/tests"
echo "[pass] Python compilation"

(
  cd "$REPO_FILES"
  python -m pytest -q \
    tests/test_monitor_disclosures.py \
    tests/test_government_trade_tracker.py \
    tests/test_oge_disclosures.py
)
echo "[pass] 23 parser, source, state, ledger, and OGE-table tests"

python - "$REPO_FILES" <<'PY'
from pathlib import Path
import re
import sys
import yaml

root = Path(sys.argv[1])
expected_actions = {
    "actions/checkout@v6",
    "actions/setup-python@v7",
    "actions/cache/restore@v5",
    "actions/cache/save@v5",
    "actions/upload-artifact@v7",
}
expected = {
    "legislative_trade_tracker.yml": ("7,22,37,52 * * * *", "America/New_York"),
    "executive_trade_tracker.yml": ("13 * * * *", "America/New_York"),
}
for filename, (expected_cron, expected_timezone) in expected.items():
    path = root / ".github" / "workflows" / filename
    text = path.read_text(encoding="utf-8")
    workflow = yaml.load(text, Loader=yaml.BaseLoader)
    assert isinstance(workflow, dict), path
    schedules = workflow["on"]["schedule"]
    assert len(schedules) == 1, path
    schedule = schedules[0]
    assert schedule["cron"] == expected_cron, (path, schedule)
    assert schedule["timezone"] == expected_timezone, (path, schedule)
    minute_field = schedule["cron"].split()[0]
    minutes = [int(value) for value in minute_field.split(",")]
    assert 0 not in minutes, (path, "schedule must avoid minute zero")

    top_env = workflow.get("env", {})
    assert "DISCLOSURE_TERMS_ACKNOWLEDGED" in top_env
    assert all("secrets." not in str(value) for value in top_env.values())

    jobs = workflow.get("jobs", {})
    serialized_jobs = str(jobs)
    for action in expected_actions:
        assert action in serialized_jobs, (path, action)
    assert "tracker-state" in text
    assert "PUSHOVER_API_TOKEN" in text and "PUSHOVER_USER_KEY" in text
    assert "pytest" in text
    assert re.search(r"hashFiles\('\.trade-tracker/.+?/state\.json'\)", text)

print("[pass] workflow YAML, schedules, current action majors, state restoration, and secret scoping")
PY

MOCK_REPO="$TEMP_ROOT/PolitiTrack"
mkdir -p "$MOCK_REPO/.git" "$MOCK_REPO/scripts" "$MOCK_REPO/.github/workflows"
printf '# Mock PolitiTrack\n' > "$MOCK_REPO/README.md"
printf '# Old report\n\nAssessment date: 2026-07-22\n' > "$MOCK_REPO/RECOVERY_REPORT.md"
printf 'print("obsolete")\n' > "$MOCK_REPO/scripts/check_house_disclosures.py"
printf 'print("obsolete")\n' > "$MOCK_REPO/scripts/parse_unh_disclosures.py"
printf 'name: obsolete\n' > "$MOCK_REPO/.github/workflows/house_check.yml"
printf 'name: obsolete\n' > "$MOCK_REPO/.github/workflows/senate_check.yml"
printf 'name: obsolete\n' > "$MOCK_REPO/.github/workflows/disclosure_monitor.yml"

"$BASH_BIN" "$SCRIPT_DIR/apply.sh" "$MOCK_REPO" >/dev/null
"$BASH_BIN" "$SCRIPT_DIR/apply.sh" "$MOCK_REPO" >/dev/null

test -f "$MOCK_REPO/scripts/government_trade_tracker.py"
test -f "$MOCK_REPO/scripts/oge_disclosures.py"
test -f "$MOCK_REPO/.github/workflows/legislative_trade_tracker.yml"
test -f "$MOCK_REPO/.github/workflows/executive_trade_tracker.yml"
test -f "$MOCK_REPO/RECOVERY_REPORT_2026-07-22.md"
test ! -e "$MOCK_REPO/scripts/check_house_disclosures.py"
test ! -e "$MOCK_REPO/scripts/parse_unh_disclosures.py"
test ! -e "$MOCK_REPO/.github/workflows/house_check.yml"
test ! -e "$MOCK_REPO/.github/workflows/senate_check.yml"
test ! -e "$MOCK_REPO/.github/workflows/disclosure_monitor.yml"
[[ "$(grep -c 'MYETF-GOVERNMENT-TRADE-TRACKER:START' "$MOCK_REPO/README.md")" == "1" ]]
[[ "$(grep -c '>>> MyETF government trade tracker >>>' "$MOCK_REPO/.gitignore")" == "1" ]]
python -m compileall -q "$MOCK_REPO/scripts" "$MOCK_REPO/tests"
echo "[pass] clean mock-repository install, obsolete-file removal, preservation, and idempotency"

INTEGRATION="$TEMP_ROOT/integration"
mkdir -p "$INTEGRATION"
cat > "$INTEGRATION/oge-listings.json" <<'JSON'
{
  "success": true,
  "count": 1,
  "listings": [
    {
      "listing_id": "oge:synthetic-request-only",
      "date": "08/25/2026",
      "document_type": "278-T Periodic Transaction Report",
      "name": "Synthetic Official",
      "title": "Test Official",
      "agency": "Test Agency",
      "level": "PAS",
      "document_url": "",
      "request_url": "https://example.invalid/form-201",
      "access_mode": "request",
      "row_text": "synthetic request-only row"
    }
  ]
}
JSON

run_integration() {
  local allow_initialization="$1"
  (
    cd "$REPO_FILES"
    ALLOW_STATE_INITIALIZATION="$allow_initialization" \
    REQUIRE_PUSHOVER=false \
    python scripts/government_trade_tracker.py \
      --branch executive \
      --oge-listings-file "$INTEGRATION/oge-listings.json" \
      --state-file "$INTEGRATION/state.json" \
      --ledger-file "$INTEGRATION/purchases.jsonl" \
      --pending-file "$INTEGRATION/pending-review.jsonl" \
      --result-file "$INTEGRATION/result.json" \
      --latest-csv "$INTEGRATION/latest.csv" \
      --bootstrap-alerts \
      --no-notify \
      --acknowledge-terms >/dev/null
  )
}
run_integration true
run_integration false

python - "$INTEGRATION" <<'PY'
from pathlib import Path
import json
import sys

root = Path(sys.argv[1])
result = json.loads((root / "result.json").read_text(encoding="utf-8"))
state = json.loads((root / "state.json").read_text(encoding="utf-8"))
pending_lines = [line for line in (root / "pending-review.jsonl").read_text(encoding="utf-8").splitlines() if line]
assert result["success"] is True
assert result["new_filing_counts"]["oge"] == 0
assert len(pending_lines) == 1
assert "oge:synthetic-request-only" in state["seen_filings"]["oge"]
assert (root / "latest.csv").read_text(encoding="utf-8").startswith("trade_id,")
print("[pass] end-to-end Executive request queue, durable state, and no-duplicate second run")
PY

echo
echo "VERIFICATION PASSED"
