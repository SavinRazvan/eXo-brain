#!/usr/bin/env bash
# File: safe_clean.sh
# Path: scripts/dev/safe_clean.sh
# Role: Safely remove generated local artifacts without deleting protected runtime data.
# Used By:
#  - maintainers running local cleanup before tests or release checks
# Depends On:
#  - bash
#  - find
#  - git
# Notes:
#  - Preserves `.exo_env`, `.exo_data`, `.coverage`, and tracked repository files.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

echo "Running safe cleanup in ${ROOT_DIR}"

prune_untracked_files_in_dir() {
  local dir_path="$1"
  if [[ ! -d "${dir_path}" ]]; then
    return 0
  fi

  local removed_count=0
  while IFS= read -r file_path; do
    if git ls-files --error-unmatch -- "${file_path}" >/dev/null 2>&1; then
      continue
    fi
    rm -f -- "${file_path}"
    removed_count=$((removed_count + 1))
  done < <(find "${dir_path}" -type f)

  echo "Pruned ${removed_count} untracked file(s) in ${dir_path}"
}

# Remove cache/build directories while protecting environments and local artifacts.
find . \
  \( -path "./.git" -o -path "./.exo_env" -o -path "./.exo_env_broken_*" -o -path "./.hydra_env" -o -path "./.venv" -o -path "./venv" -o -path "./env" -o -path "./.env" -o -path "./.exo_data" -o -path "./.local" \) -prune -o \
  -type d \( -name "__pycache__" -o -name ".pytest_cache" -o -name ".mypy_cache" -o -name ".hypothesis" -o -name ".tox" -o -name ".nox" -o -name ".ruff_cache" -o -name ".pytype" -o -name ".cache" -o -name "htmlcov" -o -name "build" -o -name "dist" -o -name "site" -o -name "*.egg-info" -o -name ".ipynb_checkpoints" \) \
  -exec rm -rf {} +

# Remove generated files and Windows zone-identifier artifacts.
find . \
  \( -path "./.git" -o -path "./.exo_env" -o -path "./.exo_env_broken_*" -o -path "./.hydra_env" -o -path "./.venv" -o -path "./venv" -o -path "./env" -o -path "./.env" -o -path "./.exo_data" -o -path "./.local" \) -prune -o \
  -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.pyd" -o -name "coverage.xml" -o -name "*.log" -o -name "*Zone.Identifier" -o -name "*:Zone.Identifier" \) \
  -exec rm -f {} +

# Prune generated runtime logs while preserving git-tracked fixtures.
prune_untracked_files_in_dir "./logs"
prune_untracked_files_in_dir "./relative-logs"
prune_untracked_files_in_dir "./relative-cwd"
find "./relative-logs" "./relative-cwd" -depth -type d -empty -delete 2>/dev/null || true

echo "Safe cleanup complete."
