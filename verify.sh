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

(
  cd "$SCRIPT_DIR"
  python -m pytest -q tests/test_protected_state.py tests/test_workflow_contract.py
  python scripts/verify_repository.py --require-shell --bash "$BASH_BIN"
)

(
  cd "$SCRIPT_DIR"
  sha256sum --check MANIFEST.sha256
)
echo "[pass] deterministic recovery-record manifest"

echo
echo "VERIFICATION PASSED"
