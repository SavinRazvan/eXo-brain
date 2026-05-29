#!/usr/bin/env bash
# File: install_adapter_dependencies.sh
# Path: scripts/dev/install_adapter_dependencies.sh
# Role: Install requirements.txt including all four adapter PyPI wheels.
# Used By:
#  - CI, Dockerfile, local dev
# Notes:
#  - PyPI wheels only. No git, editable, or sibling-repo installs.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  PYTHON=python
fi

"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r requirements.txt

"$PYTHON" <<'PY'
import re
import sys
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

req = Path("requirements.txt").read_text(encoding="utf-8")
packages = (
    ("exo-brain-core-contracts", "exo_brain_core_contracts"),
    ("exo-brain-adapter-sdk", "exo_brain_adapter_sdk"),
    ("exo-adapter-echo", "exo_adapter_echo"),
    ("exo-adapter-openai", "exo_adapter_openai"),
)
errors: list[str] = []
for dist, module_name in packages:
    match = re.search(rf"^{re.escape(dist)}==(\S+)", req, re.MULTILINE)
    if not match:
        errors.append(f"missing pin for {dist} in requirements.txt")
        continue
    pinned = match.group(1)
    try:
        installed = version(dist)
    except PackageNotFoundError:
        errors.append(f"{dist} not installed (pip install -r requirements.txt)")
        continue
    if installed != pinned:
        errors.append(f"{dist} installed {installed!r} != pinned {pinned!r}")
        continue
    mod = import_module(module_name)
    mod_file = (mod.__file__ or "").replace("\\", "/")
    if "site-packages" not in mod_file and "dist-packages" not in mod_file:
        errors.append(f"{dist} must be a PyPI wheel in site-packages, got {mod.__file__}")
    if "/eXo_adapters/" in mod_file or mod_file.endswith("/eXo_adapters"):
        errors.append(f"{dist} must not load from sibling eXo_adapters checkout: {mod.__file__}")

if errors:
    print("Adapter PyPI verification failed:", file=sys.stderr)
    for err in errors:
        print(f"  - {err}", file=sys.stderr)
    sys.exit(1)
print("Adapter wheels OK (PyPI only; all four match requirements.txt pins)")
PY
