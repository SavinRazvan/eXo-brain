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

if "$PYTHON" -m pip install "exo-brain-core-contracts==0.1.1" 2>/dev/null; then
  echo "Installed exo-brain-core-contracts from PyPI"
else
  echo "Installing exo-brain-core-contracts from packages/repo_for_pipy"
  "$PYTHON" -m pip install -e packages/repo_for_pipy/packages/exo-brain-core-contracts
fi

if "$PYTHON" -m pip install -r requirements-adapters.txt 2>/dev/null; then
  echo "Installed adapter packages from PyPI"
else
  echo "Installing adapter packages from packages/repo_for_pipy"
  "$PYTHON" -m pip install \
    -e packages/repo_for_pipy/packages/exo-brain-adapter-sdk \
    -e packages/repo_for_pipy/packages/exo-adapter-echo \
    -e packages/repo_for_pipy/packages/exo-adapter-openai
fi

"$PYTHON" -c "import exo_brain_core_contracts, exo_adapter_openai, exo_adapter_echo"
