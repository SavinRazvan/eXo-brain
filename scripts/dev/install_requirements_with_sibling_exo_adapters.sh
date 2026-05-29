#!/usr/bin/env bash
#
# File: install_requirements_with_sibling_exo_adapters.sh
# Path: scripts/dev/install_requirements_with_sibling_exo_adapters.sh
# Role: Install eXo-brain deps; optionally override adapter packages from a sibling eXo_adapters checkout.
# Used By:
#  - Adapter maintainers developing wheels alongside the control plane
# Depends On:
#  - bash, pip, requirements.txt at repo root
# Notes:
#  - Default: pip install -r requirements.txt (PyPI pins).
#  - Override: EXO_ADAPTERS_ROOT=/path/to/eXo_adapters for editable installs from that repo.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REQ="${ROOT}/requirements.txt"
SIBLING_ROOT="${ROOT}/../eXo_adapters"

if [[ ! -f "$REQ" ]]; then
  echo "error: missing $REQ" >&2
  exit 1
fi

python -m pip install --upgrade pip

if [[ -n "${EXO_ADAPTERS_ROOT:-}" ]]; then
  ADAPTERS_ROOT="$EXO_ADAPTERS_ROOT"
elif [[ -d "${SIBLING_ROOT}/packages/exo-brain-core-contracts" ]]; then
  ADAPTERS_ROOT="$SIBLING_ROOT"
else
  echo "Installing from PyPI (requirements.txt)"
  python -m pip install -r "$REQ"
  echo "Done. Verify: python -c \"import exo_brain_core_contracts, exo_adapter_openai; print('ok')\""
  exit 0
fi

PKG_ROOT="${ADAPTERS_ROOT}/packages"
for pkg in exo-brain-core-contracts exo-brain-adapter-sdk exo-adapter-echo exo-adapter-openai; do
  if [[ ! -f "${PKG_ROOT}/${pkg}/pyproject.toml" ]]; then
    echo "error: missing ${PKG_ROOT}/${pkg}/pyproject.toml" >&2
    exit 1
  fi
done

TMP_REQ="$(mktemp)"
trap 'rm -f "$TMP_REQ"' EXIT
grep -vE '^exo-(brain-core-contracts|brain-adapter-sdk|adapter-echo|adapter-openai)' "$REQ" >"$TMP_REQ"

echo "Installing control-plane deps (adapter pins skipped; editable installs follow)"
python -m pip install -r "$TMP_REQ"

echo "Installing editable adapter packages from: ${PKG_ROOT}"
python -m pip install \
  -e "${PKG_ROOT}/exo-brain-core-contracts" \
  -e "${PKG_ROOT}/exo-brain-adapter-sdk" \
  -e "${PKG_ROOT}/exo-adapter-echo" \
  -e "${PKG_ROOT}/exo-adapter-openai"

echo "Done. Verify: python -c \"import exo_brain_core_contracts; print(exo_brain_core_contracts.__file__)\""
