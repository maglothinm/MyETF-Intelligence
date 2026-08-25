#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/repo-files"
TARGET_DIR="${1:-}"

usage() {
  echo "Usage: $0 /path/to/MyETF" >&2
}

if [[ -z "$TARGET_DIR" ]]; then
  usage
  exit 2
fi
if [[ ! -d "$SOURCE_DIR/scripts" || ! -d "$SOURCE_DIR/.github/workflows" ]]; then
  echo "Bundle is incomplete: expected repo-files/scripts and repo-files/.github/workflows." >&2
  exit 1
fi
if [[ ! -d "$TARGET_DIR" ]]; then
  echo "Target directory does not exist: $TARGET_DIR" >&2
  exit 1
fi
if [[ ! -d "$TARGET_DIR/scripts" ]]; then
  echo "Target does not look like MyETF: missing $TARGET_DIR/scripts" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR/.github/workflows"

# Preserve the repository's July assessment before installing the superseding report.
if [[ -f "$TARGET_DIR/RECOVERY_REPORT.md" && ! -f "$TARGET_DIR/RECOVERY_REPORT_2026-07-22.md" ]]; then
  cp "$TARGET_DIR/RECOVERY_REPORT.md" "$TARGET_DIR/RECOVERY_REPORT_2026-07-22.md"
fi

# Remove the workflows/scripts that were disabled, false-positive, or single-keyword only.
rm -f \
  "$TARGET_DIR/.github/workflows/house_check.yml" \
  "$TARGET_DIR/.github/workflows/senate_check.yml" \
  "$TARGET_DIR/.github/workflows/disclosure_monitor.yml" \
  "$TARGET_DIR/scripts/check_house_disclosures.py" \
  "$TARGET_DIR/scripts/parse_unh_disclosures.py"

# Copy the operational overlay. This is intentionally idempotent.
cp -a "$SOURCE_DIR/." "$TARGET_DIR/"
chmod +x \
  "$TARGET_DIR/scripts/government_trade_tracker.py" \
  "$TARGET_DIR/scripts/oge_disclosures.py" \
  "$TARGET_DIR/scripts/monitor_disclosures.py"

python - "$TARGET_DIR/.gitignore" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
start = "# >>> MyETF government trade tracker >>>"
end = "# <<< MyETF government trade tracker <<<"
block = """# >>> MyETF government trade tracker >>>
.trade-tracker/
legislative-result.json
executive-result.json
oge-listings.json
legislative-latest-purchases.csv
executive-latest-purchases.csv
oge-diagnostics/
# <<< MyETF government trade tracker <<<
"""
text = path.read_text(encoding="utf-8") if path.exists() else ""
if start in text and end in text:
    before, remainder = text.split(start, 1)
    _, after = remainder.split(end, 1)
    text = before.rstrip() + "\n\n" + block + after.lstrip("\n")
else:
    text = text.rstrip() + ("\n\n" if text.strip() else "") + block
path.write_text(text.rstrip() + "\n", encoding="utf-8")
PY

python - "$TARGET_DIR/README.md" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
start = "<!-- MYETF-GOVERNMENT-TRADE-TRACKER:START -->"
end = "<!-- MYETF-GOVERNMENT-TRADE-TRACKER:END -->"
block = """<!-- MYETF-GOVERNMENT-TRADE-TRACKER:START -->
## Government purchase disclosure tracker

The operational House, Senate, and OGE monitoring path is documented in
[`README_GOVERNMENT_TRADES.md`](README_GOVERNMENT_TRADES.md). It runs independently
of the historical dashboard and writes durable JSONL ledgers plus latest-purchase CSVs.
<!-- MYETF-GOVERNMENT-TRADE-TRACKER:END -->
"""
text = path.read_text(encoding="utf-8") if path.exists() else "# MyETF\n"
if start in text and end in text:
    before, remainder = text.split(start, 1)
    _, after = remainder.split(end, 1)
    text = before.rstrip() + "\n\n" + block + after.lstrip("\n")
else:
    text = text.rstrip() + "\n\n" + block
path.write_text(text.rstrip() + "\n", encoding="utf-8")
PY

if git -C "$TARGET_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C "$TARGET_DIR" diff --check
fi

cat <<EOF2
Installed the government trade tracker into:
  $TARGET_DIR

Next:
  1. Review README_GOVERNMENT_TRADES.md and the disclosure-use restrictions.
  2. Run: cd "$TARGET_DIR" && python -m pytest -q tests/test_monitor_disclosures.py tests/test_government_trade_tracker.py tests/test_oge_disclosures.py
  3. Review: git status --short && git diff
  4. Configure the GitHub Actions variable/secrets, commit, push, and initialize both workflow baselines.
EOF2
