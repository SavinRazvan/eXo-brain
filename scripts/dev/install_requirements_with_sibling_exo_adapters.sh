#!/usr/bin/env bash
#
# File: install_requirements_with_sibling_exo_adapters.sh
# Path: scripts/dev/install_requirements_with_sibling_exo_adapters.sh
# Role: Install exo-brain-core-contracts from a local path, then install remaining requirements without duplicating that pin.
# Used By:
#  - Maintainers when requirements.txt git URL is unreachable, or when overriding with a custom eXo_adapters checkout.
# Depends On:
#  - bash, pip, requirements.txt at repo root
# Notes:
#  - Prefers in-tree bundle: packages/eXo_adapters/packages/exo-brain-core-contracts (same as default requirements.txt -e line).
#  - Otherwise: sibling eXo_adapters (../eXo_adapters). Override: EXO_ADAPTERS_ROOT=/path/to/eXo_adapters repo root.
#  - WSL: Windows UNC for sibling is the same tree as $HOME/.../eXo_adapters in Linux.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REQ="${ROOT}/requirements.txt"
INTREE_CONTRACTS="${ROOT}/packages/eXo_adapters/packages/exo-brain-core-contracts"
SIBLING_ROOT="${ROOT}/../eXo_adapters"
SIBLING_CONTRACTS="${SIBLING_ROOT}/packages/exo-brain-core-contracts"

if [[ -n "${EXO_ADAPTERS_ROOT:-}" ]]; then
  CONTRACTS_PKG="${EXO_ADAPTERS_ROOT}/packages/exo-brain-core-contracts"
elif [[ -d "$INTREE_CONTRACTS" ]]; then
  CONTRACTS_PKG="$INTREE_CONTRACTS"
elif [[ -d "$SIBLING_CONTRACTS" ]]; then
  CONTRACTS_PKG="$SIBLING_CONTRACTS"
else
  echo "error: exo-brain-core-contracts not found at:" >&2
  echo "  $INTREE_CONTRACTS (in-tree) or $SIBLING_CONTRACTS (sibling)" >&2
  echo "  Set EXO_ADAPTERS_ROOT to a clone root that contains packages/exo-brain-core-contracts." >&2
  exit 1
fi

if [[ ! -f "$REQ" ]]; then
  echo "error: missing $REQ" >&2
  exit 1
fi

echo "Installing editable exo-brain-core-contracts from: $CONTRACTS_PKG"
python -m pip install -e "$CONTRACTS_PKG"

# Install everything else; skip the contracts pin line(s) (already satisfied by -e).
TMP_REQ="$(mktemp)"
trap 'rm -f "$TMP_REQ"' EXIT
grep -vE '^(-e \./packages/eXo_adapters/packages/exo-brain-core-contracts|exo-brain-core-contracts @ git)' "$REQ" >"$TMP_REQ"

echo "Installing remaining dependencies from requirements.txt (git contracts line skipped)"
python -m pip install -r "$TMP_REQ"

echo "Done. Verify: python -c \"import exo_brain_core_contracts; print(exo_brain_core_contracts.__file__)\""
