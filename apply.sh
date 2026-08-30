#!/usr/bin/env bash
set -euo pipefail

cat >&2 <<'EOF'
This recovery installer was retired on 2026-08-29 and cannot apply files.

Its payload predates the canonical PolitiTrack workflow set and could recreate a
duplicate Legislative state writer. Use the checked-in repository files and restore
protected state from the existing GitHub Actions artifacts instead.

No files were changed.
EOF
exit 64
