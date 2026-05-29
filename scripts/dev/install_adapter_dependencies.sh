#!/usr/bin/env bash
# File: install_adapter_dependencies.sh
# Path: scripts/dev/install_adapter_dependencies.sh
# Role: Install requirements.txt including all four SavinRazvan/eXo_adapters PyPI wheels.
# Used By:
#  - CI, Dockerfile, local dev
# Notes:
#  - PyPI only. Pins must match published wheels on PyPI (see requirements.txt).
#  - Adapter maintainers developing both repos: use install_requirements_with_sibling_exo_adapters.sh
#    with EXO_ADAPTERS_ROOT set explicitly (never auto-detected from ../eXo_adapters).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  PYTHON=python
fi

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
        errors.append(f"{pkg} not installed (pip install -r requirements.txt)")
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

"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r requirements.txt
verify_adapter_pins
"$PYTHON" -c "import exo_brain_core_contracts, exo_brain_adapter_sdk, exo_adapter_openai, exo_adapter_echo"
