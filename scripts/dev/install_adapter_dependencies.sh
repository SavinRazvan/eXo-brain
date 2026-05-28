#!/usr/bin/env bash
# Install eXo-brain requirements plus adapter ecosystem packages (PyPI or local fallback).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  PYTHON=python
fi

"$PYTHON" -m pip install --upgrade pip

TMP_REQ="$(mktemp)"
grep -v '^exo-brain-core-contracts' requirements.txt | grep -v '^#.*exo-brain-core-contracts' >"$TMP_REQ" || true
"$PYTHON" -m pip install -r "$TMP_REQ"
rm -f "$TMP_REQ"

_install_editable_if_present() {
  local label="$1"
  shift
  for path in "$@"; do
    if [[ -f "${path}/pyproject.toml" ]]; then
      echo "Installing ${label} from ${path}"
      "$PYTHON" -m pip install -e "${path}"
      return 0
    fi
  done
  return 1
}

if "$PYTHON" -m pip install "exo-brain-core-contracts==0.1.1"; then
  echo "Installed exo-brain-core-contracts from PyPI"
elif _install_editable_if_present "exo-brain-core-contracts" \
  packages/eXo_adapters/packages/exo-brain-core-contracts \
  packages/repo_for_pipy/packages/exo-brain-core-contracts; then
  :
else
  echo "ERROR: exo-brain-core-contracts not on PyPI and no local package tree found" >&2
  exit 1
fi

if "$PYTHON" -m pip install -r requirements-adapters.txt; then
  echo "Installed adapter packages from PyPI"
else
  adapter_roots=(
    packages/eXo_adapters/packages
    packages/repo_for_pipy/packages
  )
  installed_adapters=false
  for root in "${adapter_roots[@]}"; do
    if [[ -f "${root}/exo-adapter-openai/pyproject.toml" ]]; then
      echo "Installing adapter packages from ${root}"
      "$PYTHON" -m pip install \
        -e "${root}/exo-brain-adapter-sdk" \
        -e "${root}/exo-adapter-echo" \
        -e "${root}/exo-adapter-openai"
      installed_adapters=true
      break
    fi
  done
  if [[ "${installed_adapters}" != true ]]; then
    echo "ERROR: adapter packages not on PyPI and no local adapter package tree found" >&2
    exit 1
  fi
fi

"$PYTHON" -c "import exo_brain_core_contracts, exo_adapter_openai, exo_adapter_echo"
