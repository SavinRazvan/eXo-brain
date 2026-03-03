#!/usr/bin/env bash
# File: build.sh
# Path: scripts/ui/build.sh
# Role: Build the TypeScript dashboard into ui/dist for FastAPI static serving.
# Used By:
#  - local developers
#  - CI jobs that need prebuilt UI artifacts
# Depends On:
#  - npm + typescript (preferred path), OR
#  - python fallback transpiler (scripts/ui/build_ts_fallback.py)
# Notes:
#  - Set UI_BUILD_MODE=fallback to force the Python fallback transpiler.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UI_DIR="${ROOT_DIR}/ui"

cd "${UI_DIR}"

if [[ "${UI_BUILD_MODE:-}" != "fallback" ]] && command -v npm >/dev/null 2>&1; then
  if [[ ! -d "node_modules" ]]; then
    npm install --no-audit --no-fund
  fi
  npm run build
  echo "UI build complete via TypeScript compiler: ${UI_DIR}/dist"
  exit 0
fi

python "${ROOT_DIR}/scripts/ui/build_ts_fallback.py" \
  --src "${UI_DIR}/src" \
  --dist "${UI_DIR}/dist"
echo "UI build complete via fallback transpiler: ${UI_DIR}/dist"
