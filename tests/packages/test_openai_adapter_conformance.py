"""
File: test_openai_adapter_conformance.py
Path: tests/packages/test_openai_adapter_conformance.py
Role: Validate provider package wrapper and runtime contract conformance helper.
Used By:
 - CI test suite
Depends On:
 - tests.adapter_package_paths (staging or legacy packages dir)
 - exo-brain-adapter-sdk, exo-adapter-openai trees
Notes:
 - Contract check is structural and does not require network/API keys.
 - External install path tests use scripts/packages/external_install_smoke.py as subprocess gate.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys

import pytest

from tests.adapter_package_paths import REPO_ROOT, local_portable_adapters_present, package_src

requires_local_adapter_packages = pytest.mark.skipif(
    not local_portable_adapters_present(),
    reason="Portable adapter sources live in eXo_adapters; add a local packages/ tree or sibling checkout to run these tests.",
)


def _add_package_paths() -> None:
    paths = [
        package_src("exo-brain-core-contracts"),
        package_src("exo-brain-adapter-sdk"),
        package_src("exo-adapter-openai"),
    ]
    for path in reversed(paths):
        sys.path.insert(0, str(path))


@requires_local_adapter_packages
def test_openai_adapter_package_conformance() -> None:
    _add_package_paths()

    from exo_adapter_openai import OpenAIAgentsRuntimeAdapter
    from exo_brain_adapter_sdk import assert_runtime_adapter_contract

    adapter = OpenAIAgentsRuntimeAdapter(provider_id="openai-test")
    assert_runtime_adapter_contract(adapter)


@requires_local_adapter_packages
def test_openai_adapter_load_adapter_factory() -> None:
    _add_package_paths()

    from exo_adapter_openai import load_adapter

    adapter = load_adapter(provider_id="openai-factory")
    assert adapter.get_capabilities().provider_id == "openai-factory"


@requires_local_adapter_packages
def test_openai_adapter_package_has_no_monorepo_imports() -> None:
    base = package_src("exo-adapter-openai") / "exo_adapter_openai"
    package_files = [
        base / "__init__.py",
        base / "runtime.py",
        base / "tool_wiring.py",
    ]
    for file_path in package_files:
        for line in file_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            assert not stripped.startswith("from src."), f"Monorepo import found in {file_path}: {stripped}"
            assert not stripped.startswith("import src."), f"Monorepo import found in {file_path}: {stripped}"


@requires_local_adapter_packages
def test_openai_adapter_portability_smoke_run_turn() -> None:
    _add_package_paths()

    from exo_adapter_openai import OpenAIAgentsRuntimeAdapter

    adapter = OpenAIAgentsRuntimeAdapter(provider_id="openai-test")
    assert adapter.__class__.__module__.startswith("exo_adapter_openai.")

    async def _collect_event_types() -> list[str]:
        await adapter.start_session("sess-portability", metadata={"agent_id": "smoke-agent"})
        event_types: list[str] = []
        async for event in adapter.run_turn(
            session_id="sess-portability",
            user_input="hello",
            context={"run_id": "run-portability"},
        ):
            event_types.append(str(getattr(event.event_type, "value", event.event_type)))
        return event_types

    event_types = asyncio.run(_collect_event_types())
    assert "output_delta" in event_types
    assert "run_complete" in event_types


@requires_local_adapter_packages
def test_adapter_sdk_has_no_monorepo_imports() -> None:
    """Verify exo-brain-adapter-sdk has no monorepo-relative fallback imports."""
    sdk_files = list(package_src("exo-brain-adapter-sdk").rglob("*.py"))
    assert sdk_files, "No SDK source files found"
    for file_path in sdk_files:
        for line in file_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            assert not stripped.startswith("from src."), (
                f"Monorepo import found in {file_path}: {stripped}"
            )
            assert not stripped.startswith("import src."), (
                f"Monorepo import found in {file_path}: {stripped}"
            )


@requires_local_adapter_packages
def test_core_contracts_has_no_monorepo_imports() -> None:
    """Verify exo-brain-core-contracts has no monorepo-relative imports."""
    contracts_files = list(package_src("exo-brain-core-contracts").rglob("*.py"))
    assert contracts_files, "No core-contracts source files found"
    for file_path in contracts_files:
        for line in file_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            assert not stripped.startswith("from src."), (
                f"Monorepo import found in {file_path}: {stripped}"
            )
            assert not stripped.startswith("import src."), (
                f"Monorepo import found in {file_path}: {stripped}"
            )


@requires_local_adapter_packages
def test_external_install_smoke_script_passes() -> None:
    """Run external install smoke in isolated venv to certify standalone installability."""
    smoke_script = REPO_ROOT / "scripts" / "packages" / "external_install_smoke.py"
    assert smoke_script.exists(), f"Smoke script not found: {smoke_script}"

    result = subprocess.run(
        [sys.executable, str(smoke_script)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, (
        f"External install smoke failed:\n{result.stdout}\n{result.stderr}"
    )
