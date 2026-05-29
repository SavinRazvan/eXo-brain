#!/usr/bin/env bash
# File: install_adapter_dependencies.sh
# Path: scripts/dev/install_adapter_dependencies.sh
# Role: Install requirements.txt including all four SavinRazvan/eXo_adapters PyPI wheels.
# Used By:
#  - CI, Dockerfile, local dev
# Notes:
#  - Verifies installed versions match requirements.txt pins.
#  - Falls back to editable sibling ../eXo_adapters when PyPI lacks the pinned release.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  PYTHON=python
fi

SIBLING="${EXO_ADAPTERS_ROOT:-$ROOT/../eXo_adapters}"
SIBLING_PKG="${SIBLING}/packages"

verify_adapter_pins() {
  "$PYTHON" <<'PY'
import re
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

req = (Path("requirements.txt").read_text(encoding="utf-8"))
packages = (
    "exo-brain-core-contracts",
    "exo-brain-adapter-sdk",
    "exo-adapter-echo",
    "exo-adapter-openai",
)
errors: list[str] = []
for pkg in packages:
    match = re.search(rf"^{re.escape(pkg)}==(\S+)", req, re.MULTILINE)
    if not match:
        errors.append(f"missing pin for {pkg} in requirements.txt")
        continue
    pinned = match.group(1)
    try:
        installed = version(pkg)
    except PackageNotFoundError:
        errors.append(f"{pkg} not installed")
        continue
    if installed != pinned:
        errors.append(f"{pkg} installed {installed!r} != pinned {pinned!r}")
if errors:
    print("Adapter pin verification failed:", file=sys.stderr)
    for err in errors:
        print(f"  - {err}", file=sys.stderr)
    sys.exit(1)
print("Adapter wheels OK (all four distributions match requirements.txt pins)")
PY
}

install_editable_sibling() {
  if [[ ! -f "${SIBLING_PKG}/exo-brain-core-contracts/pyproject.toml" ]]; then
    echo "error: sibling eXo_adapters not found at ${SIBLING_PKG}" >&2
    return 1
  fi
  TMP_REQ="$(mktemp)"
  trap 'rm -f "$TMP_REQ"' RETURN
  grep -vE '^exo-(brain-core-contracts|brain-adapter-sdk|adapter-echo|adapter-openai)' requirements.txt >"$TMP_REQ"
  echo "Installing control-plane deps (adapter pins deferred for editable installs)"
  "$PYTHON" -m pip install -r "$TMP_REQ"
  echo "Installing editable adapter packages from ${SIBLING_PKG}"
  "$PYTHON" -m pip install \
    -e "${SIBLING_PKG}/exo-brain-core-contracts" \
    -e "${SIBLING_PKG}/exo-brain-adapter-sdk" \
    -e "${SIBLING_PKG}/exo-adapter-echo" \
    -e "${SIBLING_PKG}/exo-adapter-openai"
}

"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r requirements.txt || true

if verify_adapter_pins; then
  "$PYTHON" -c "import exo_brain_core_contracts, exo_brain_adapter_sdk, exo_adapter_openai, exo_adapter_echo"
  exit 0
fi

echo "PyPI install did not satisfy adapter pins; trying editable sibling at ${SIBLING}" >&2
install_editable_sibling
verify_adapter_pins
"$PYTHON" -c "import exo_brain_core_contracts, exo_brain_adapter_sdk, exo_adapter_openai, exo_adapter_echo"
