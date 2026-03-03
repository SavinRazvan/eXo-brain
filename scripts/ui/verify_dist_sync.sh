#!/usr/bin/env bash
# File: verify_dist_sync.sh
# Path: scripts/ui/verify_dist_sync.sh
# Role: Verifies ui/dist is synchronized with ui/src generated output.
# Used By:
#  - .github/workflows/architecture-fitness.yml
# Depends On:
#  - scripts/ui/build.sh
#  - git
# Notes:
#  - Forces fallback build mode for deterministic output across environments.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "${ROOT_DIR}"
UI_BUILD_MODE=fallback ./scripts/ui/build.sh

if ! git diff --quiet -- ui/dist; then
  echo "ui/dist is out of sync with ui/src." >&2
  echo "Run: ./scripts/ui/build.sh and commit the updated ui/dist files." >&2
  git --no-pager diff -- ui/dist
  exit 1
fi

echo "ui/dist is synchronized with ui/src."
