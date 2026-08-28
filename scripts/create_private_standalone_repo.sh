#!/usr/bin/env bash
set -euo pipefail

NEW_NAME="${1:-MyETF-Intelligence}"
OWNER="${2:-}"

if [[ ! "$NEW_NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Repository name may contain only letters, numbers, periods, underscores, and hyphens: $NEW_NAME" >&2
  exit 2
fi

for command in git gh python unzip; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Required command is unavailable: $command" >&2
    exit 2
  fi
done

if [[ ! -d .git ]]; then
  echo "Run this script from the root of the current MyETF Git repository." >&2
  exit 2
fi
if [[ ! -f .github/workflows/import_migrated_state.yml ]]; then
  echo "The state-import workflow is missing. Apply the wallboard/private-repository overlay first." >&2
  exit 2
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo "The working tree is not clean. Commit and push the wallboard changes before creating the private repository." >&2
  git status --short >&2
  exit 2
fi
if ! gh auth status >/dev/null 2>&1; then
  echo "GitHub CLI is not authenticated in this Codespace. Run: gh auth login" >&2
  exit 2
fi

CURRENT_REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
if [[ -z "$OWNER" ]]; then
  OWNER="$(gh api user --jq .login)"
fi
TARGET_REPO="$OWNER/$NEW_NAME"

if gh repo view "$TARGET_REPO" >/dev/null 2>&1; then
  echo "The target repository already exists: $TARGET_REPO" >&2
  exit 2
fi
if git remote get-url private >/dev/null 2>&1; then
  echo "A Git remote named 'private' already exists. Remove or rename it before continuing." >&2
  exit 2
fi
if git remote get-url public-fork >/dev/null 2>&1; then
  echo "A Git remote named 'public-fork' already exists. This migration appears to have been started before." >&2
  exit 2
fi

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
MIGRATION_TAG="state-migration-$TIMESTAMP"
INVENTORY_DIR="$HOME/myetf-private-migration-$TIMESTAMP"
STATE_DIR="$INVENTORY_DIR/state-artifacts"
mkdir -p "$STATE_DIR"

{
  echo "Source repository: $CURRENT_REPO"
  echo "Target repository: $TARGET_REPO"
  echo "Created UTC: $TIMESTAMP"
  echo "Migration release: $MIGRATION_TAG"
  echo
  echo "Git remotes before migration:"
  git remote -v
} > "$INVENTORY_DIR/repository.txt"

gh secret list -R "$CURRENT_REPO" > "$INVENTORY_DIR/secret-names.txt" 2>&1 || true
if ! gh variable list -R "$CURRENT_REPO" --json name,value,updatedAt > "$INVENTORY_DIR/variables.json" 2> "$INVENTORY_DIR/variables-error.txt"; then
  echo '[]' > "$INVENTORY_DIR/variables.json"
fi

artifact_assets=()
for artifact_name in legislative-tracker-state executive-tracker-state ai-analysis-state; do
  artifact_id="$(
    gh api \
      -H "Accept: application/vnd.github+json" \
      "/repos/${CURRENT_REPO}/actions/artifacts?name=${artifact_name}&per_page=100" \
      --jq '[.artifacts[] | select(.expired == false)] | max_by(.created_at) | .id // empty' \
      2>/dev/null || true
  )"
  if [[ -z "$artifact_id" ]]; then
    echo "No unexpired ${artifact_name} artifact was found in ${CURRENT_REPO}."
    continue
  fi
  archive="$STATE_DIR/${artifact_name}.zip"
  echo "Exporting ${artifact_name} artifact ${artifact_id}..."
  gh api \
    -H "Accept: application/vnd.github+json" \
    "/repos/${CURRENT_REPO}/actions/artifacts/${artifact_id}/zip" \
    > "$archive"
  unzip -tq "$archive" >/dev/null
  if ! unzip -Z1 "$archive" | grep -Eq '(^|/)state\.json$'; then
    echo "Exported artifact ${artifact_name} contains no state.json." >&2
    exit 1
  fi
  artifact_assets+=("$archive")
done

printf 'Creating standalone private repository %s...\n' "$TARGET_REPO"
gh repo create "$TARGET_REPO" \
  --private \
  --description "Private government financial-disclosure monitoring, AI research, and paper-portfolio system" \
  --source=. \
  --remote=private \
  --push

if git remote get-url origin >/dev/null 2>&1; then
  git remote rename origin public-fork
fi
git remote rename private origin
CURRENT_BRANCH="$(git branch --show-current)"
git push --all origin
git push --tags origin
git branch --set-upstream-to="origin/$CURRENT_BRANCH" "$CURRENT_BRANCH" >/dev/null 2>&1 || git push -u origin "$CURRENT_BRANCH"
gh repo set-default "$TARGET_REPO"

# Repository variables are not secret and can be transferred. Stored secret values
# cannot be retrieved from GitHub and are intentionally left for manual recreation.
python - "$TARGET_REPO" "$INVENTORY_DIR/variables.json" <<'PY'
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

target = sys.argv[1]
path = Path(sys.argv[2])
try:
    rows = json.loads(path.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"Could not read repository variables for automatic transfer: {exc}", file=sys.stderr)
    rows = []

for row in rows if isinstance(rows, list) else []:
    name = str(row.get("name") or "").strip()
    value = str(row.get("value") or "")
    if not name:
        continue
    subprocess.run(
        ["gh", "variable", "set", name, "-R", target, "--body", value],
        check=True,
    )
    print(f"Copied Actions variable: {name}")
PY

# Prevent production collectors from running before secrets and heartbeat ownership
# are deliberately moved. The one-time state importer remains enabled.
sleep 3
for workflow in \
  legislative_trade_tracker.yml \
  executive_trade_tracker.yml \
  ai_filing_analyst.yml \
  publish_trade_dashboard.yml; do
  gh workflow disable "$workflow" -R "$TARGET_REPO" >/dev/null 2>&1 || \
    echo "Warning: could not yet disable ${workflow}; verify its status in Actions."
done

migration_dispatched=false
if (( ${#artifact_assets[@]} > 0 )); then
  echo "Uploading exported state to a private migration release..."
  gh release create "$MIGRATION_TAG" "${artifact_assets[@]}" \
    --repo "$TARGET_REPO" \
    --title "MyETF state migration $TIMESTAMP" \
    --notes "Private one-time migration assets exported from ${CURRENT_REPO}. Keep until the imported workflows have completed successfully."

  for attempt in 1 2 3 4 5; do
    if gh workflow run import_migrated_state.yml \
      -R "$TARGET_REPO" \
      --ref "$CURRENT_BRANCH" \
      -f "migration_tag=$MIGRATION_TAG"; then
      migration_dispatched=true
      break
    fi
    sleep $((attempt * 2))
  done
fi

IS_PRIVATE="$(gh repo view "$TARGET_REPO" --json isPrivate --jq .isPrivate)"
IS_FORK="$(gh repo view "$TARGET_REPO" --json isFork --jq .isFork)"
if [[ "$IS_PRIVATE" != "true" || "$IS_FORK" != "false" ]]; then
  echo "Repository creation completed, but verification returned private=$IS_PRIVATE fork=$IS_FORK." >&2
  exit 1
fi

cat <<EOF2

Standalone private repository created successfully:
  https://github.com/$TARGET_REPO

Verified:
  private = $IS_PRIVATE
  fork = $IS_FORK

The current checkout now uses the private repository as 'origin'.
The previous public fork remains available as the 'public-fork' remote for rollback.

Configuration inventory and exported state were written to:
  $INVENTORY_DIR

Actions variables were copied where GitHub CLI exposed them. Secret values cannot be
read back from GitHub; recreate the secret names listed in:
  $INVENTORY_DIR/secret-names.txt
EOF2

if [[ "$migration_dispatched" == "true" ]]; then
  cat <<EOF2

The state-import workflow was dispatched using private release:
  $MIGRATION_TAG

Open the new repository's Actions tab and confirm "Import migrated MyETF state" is green.
Do not initialize a new baseline if Legislative and Executive state imported successfully.
EOF2
elif (( ${#artifact_assets[@]} > 0 )); then
  cat <<EOF2

The migration release was created, but the import workflow could not be dispatched yet.
Run "Import migrated MyETF state" manually in the new repository and enter:
  $MIGRATION_TAG
EOF2
else
  cat <<'EOF2'

No restorable state artifact was exported. After recreating secrets, initialize the
Legislative and Executive trackers once with silent-baseline enabled.
EOF2
fi

cat <<EOF2

The production tracker and dashboard workflows were disabled in the new repository to
prevent premature scheduled runs. After secrets are recreated and state import is green:

1. Disable the four production workflows in the old public fork.
2. Enable Legislative, Executive, AI, and dashboard workflows in the private repository.
3. Run Legislative and Executive manually with both initialization/alert-history boxes
   unchecked when migrated state is present.
4. Run the dashboard publisher and AI acceptance workflow.
5. Create a new Codespace from the private repository. This Codespace remains associated
   with $CURRENT_REPO even though its Git remote now points to the private repository.
EOF2
