"""
File: notebook_common.py
Path: notebooks/notebook_common.py
Role: Shared bootstrap, adapter wheel probe, and notebook metadata for build scripts.
Used By:
 - notebooks/build_checks.py
 - notebooks/build_tutorials.py
 - scripts/dev/normalize_notebooks_for_github.py
Depends On:
 - nbformat (write helper)
Notes:
 - Single source for portable kernelspec, sys.path bootstrap, and PyPI adapter verification snippets.
 - GitHub preview prefers nbformat 4.4 (no cell ids); local Jupyter upgrades on open.
"""

from __future__ import annotations

import copy
import textwrap
from pathlib import Path
from typing import Any

import nbformat as nbf
from nbformat.validator import normalize, validate

PORTABLE_KERNELSPEC = {
    "display_name": "Python 3 (eXo-brain venv)",
    "language": "python",
    "name": "python3",
}

LANGUAGE_INFO = {"name": "python", "version": "3.12"}

BOOTSTRAP_CODE = """
import pathlib
import sys

_root = pathlib.Path.cwd().parent if pathlib.Path.cwd().name == "notebooks" else pathlib.Path.cwd()
sys.path.insert(0, str(_root))
"""

BOOTSTRAP_WITH_DOTENV = (
    BOOTSTRAP_CODE.strip()
    + """
try:
    from dotenv import load_dotenv
    load_dotenv(_root / ".env", override=False)
except ImportError:
    pass
"""
)

# Confirms SavinRazvan/eXo_adapters wheels are installed from PyPI (site-packages), not editable checkouts.
ADAPTER_WHEEL_PROBE = """
import importlib
import importlib.util

_ADAPTER_WHEELS = (
    ("exo-brain-core-contracts", "exo_brain_core_contracts"),
    ("exo-brain-adapter-sdk", "exo_brain_adapter_sdk"),
    ("exo-adapter-echo", "exo_adapter_echo"),
    ("exo-adapter-openai", "exo_adapter_openai"),
)


def _print_adapter_wheels() -> None:
    for dist, module_name in _ADAPTER_WHEELS:
        if importlib.util.find_spec(module_name) is None:
            print(f"warn: {dist} not installed — pip install -r requirements.txt")
            continue
        mod = importlib.import_module(module_name)
        mod_file = (mod.__file__ or "").replace("\\\\", "/")
        if "site-packages" not in mod_file and "dist-packages" not in mod_file:
            raise RuntimeError(f"{dist} must be a PyPI wheel in site-packages, got {mod.__file__}")
        if "/eXo_adapters/" in mod_file:
            raise RuntimeError(
                f"{dist} must not load from eXo_adapters checkout — "
                f"pip install -r requirements.txt: {mod.__file__}"
            )
        print(f"{dist}:", mod.__file__)


_print_adapter_wheels()
"""

OPENAI_ADAPTER_IDENTITY_ASSERT = """
from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter

assert OpenAIAgentsRuntimeAdapter.__module__.startswith("exo_adapter_openai."), (
    "OpenAIAgentsRuntimeAdapter must come from exo-adapter-openai (PyPI); "
    "reinstall: pip install -r requirements.txt"
)
"""

ECHO_ADAPTER_IDENTITY_ASSERT = """
from exo_adapter_echo.runtime import EchoRuntimeAdapter

assert EchoRuntimeAdapter.__module__.startswith("exo_adapter_echo."), (
    "EchoRuntimeAdapter must come from exo-adapter-echo (PyPI); "
    "reinstall: pip install -r requirements.txt"
)
"""


def join_notebook_code(*parts: str) -> str:
    """Join notebook code fragments; dedent each part separately before concatenation."""
    return "\n\n".join(textwrap.dedent(part).strip() for part in parts if part.strip())


def prepare_notebook_for_github(nb: Any) -> None:
    """Normalize notebook metadata for GitHub preview (nbformat 4.4, portable kernel)."""
    nb.metadata["kernelspec"] = dict(PORTABLE_KERNELSPEC)
    nb.metadata.setdefault("language_info", dict(LANGUAGE_INFO))
    nb.nbformat = 4
    nb.nbformat_minor = 4
    for cell in nb.cells:
        cell.metadata.pop("execution", None)
        if "id" in cell:
            del cell["id"]


def write_github_compatible_notebook(nb: Any, path: Path) -> None:
    """Write a notebook using GitHub-friendly nbformat 4.4 metadata."""
    prepared = copy.deepcopy(nb)
    prepare_notebook_for_github(prepared)
    normalize(prepared)
    validate(prepared)
    nbf.write(prepared, path, version=4)
