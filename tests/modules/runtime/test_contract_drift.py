"""
File: test_contract_drift.py
Path: tests/modules/runtime/test_contract_drift.py
Role: Guard against silent breaking drift between PyPI contracts and eXo-brain re-exports.
Used By:
 - CI (architecture-fitness test job)
Depends On:
 - exo_brain_core_contracts
 - src/schemas/events.py
 - src/runtime/runtime_adapter.py
Notes:
 - Fails when installed contracts wheel diverges from pinned requirements without updating pins.
"""

from __future__ import annotations

import re
from pathlib import Path

from exo_brain_core_contracts.events import RuntimeEvent as ContractRuntimeEvent
from exo_brain_core_contracts.events import RuntimeEventType as ContractRuntimeEventType
from exo_brain_core_contracts.runtime_adapter import RuntimeAdapter as ContractRuntimeAdapter

from src.runtime.runtime_adapter import RuntimeAdapter
from src.schemas.events import RuntimeEvent, RuntimeEventType

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _pinned_contracts_version() -> str:
    req = (_REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    match = re.search(r"^exo-brain-core-contracts==(\S+)", req, re.MULTILINE)
    assert match, "requirements.txt must pin exo-brain-core-contracts==X.Y.Z"
    return match.group(1)


def test_runtime_event_reexport_is_canonical_contract_type() -> None:
    assert RuntimeEvent is ContractRuntimeEvent
    assert RuntimeEventType is ContractRuntimeEventType


def test_runtime_adapter_reexport_is_canonical_contract_type() -> None:
    assert RuntimeAdapter is ContractRuntimeAdapter


def test_installed_contracts_version_matches_requirements_pin() -> None:
    from importlib.metadata import version

    pinned = _pinned_contracts_version()
    installed = version("exo-brain-core-contracts")
    assert installed == pinned, (
        f"exo-brain-core-contracts {installed!r} != pinned {pinned!r}; "
        "reinstall adapters or bump requirements.txt and adapter repo lockstep version"
    )
