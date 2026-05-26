"""
File: external_install_smoke.py
Path: scripts/packages/external_install_smoke.py
Role: Validates that all eXo packages install and import cleanly in an isolated virtualenv.
Used By:
 - CI gates
 - scripts/release/rc_signoff.py (optional gate)
 - make targets
Depends On:
 - Optional local workspace: ``packages/eXo_adapters/packages/``, ``eXo_adapters/packages/``, ``moving_to_adapters_project/packages/``, or legacy ``packages/`` (with ``exo-brain-core-contracts`` at the root).
Notes:
 - **Canonical** multi-package smoke lives in **eXo_adapters**; this script is a no-op (exit 0) when no local tree exists.
 - Creates a throwaway venv in /tmp, installs all four packages, runs import + conformance assertions.
 - Exit code 0 = pass, non-zero = fail.
 - Safe to run repeatedly; cleans up the temp venv on exit.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _local_adapter_workspace() -> Path | None:
    for candidate in (
        REPO_ROOT / "eXo_adapters" / "packages",
        REPO_ROOT / "packages" / "eXo_adapters" / "packages",
        REPO_ROOT / "moving_to_adapters_project" / "packages",
        REPO_ROOT / "packages",
    ):
        if (candidate / "exo-brain-core-contracts" / "pyproject.toml").is_file():
            return candidate
    return None


def _packages_install_order(root: Path) -> list[Path]:
    return [
        root / "exo-brain-core-contracts",
        root / "exo-brain-adapter-sdk",
        root / "exo-adapter-echo",
        root / "exo-adapter-openai",
    ]

ASSERTION_SCRIPT = textwrap.dedent(
    """
    import sys, json

    results = {}

    # --- core contracts import ---
    try:
        from exo_brain_core_contracts import (
            RuntimeAdapter, ProviderCapabilityMap, ToolCallContext,
            RuntimeEvent, RuntimeEventType,
        )
        results["core_contracts_import"] = "PASS"
    except Exception as exc:
        results["core_contracts_import"] = f"FAIL: {exc}"

    # --- adapter sdk import ---
    try:
        from exo_brain_adapter_sdk import (
            assert_runtime_adapter_contract,
            AdapterToolDescriptor,
            ToolExecutionAdapterContract,
        )
        results["adapter_sdk_import"] = "PASS"
    except Exception as exc:
        results["adapter_sdk_import"] = f"FAIL: {exc}"

    # --- openai adapter import ---
    try:
        from exo_adapter_openai import OpenAIAgentsRuntimeAdapter, load_adapter, build_agent_tools
        results["openai_adapter_import"] = "PASS"
    except Exception as exc:
        results["openai_adapter_import"] = f"FAIL: {exc}"

    # --- echo adapter import (second portable package) ---
    try:
        from exo_adapter_echo import EchoRuntimeAdapter, load_adapter as load_echo_adapter
        results["echo_adapter_import"] = "PASS"
    except Exception as exc:
        results["echo_adapter_import"] = f"FAIL: {exc}"

    # --- module origin check (must NOT start with src.) ---
    try:
        from exo_adapter_openai import OpenAIAgentsRuntimeAdapter
        module = OpenAIAgentsRuntimeAdapter.__module__
        if module.startswith("src."):
            results["module_origin"] = f"FAIL: monorepo path leaked: {module}"
        else:
            results["module_origin"] = f"PASS (module={module})"
    except Exception as exc:
        results["module_origin"] = f"FAIL: {exc}"

    # --- conformance contract check ---
    try:
        from exo_adapter_openai import load_adapter
        from exo_brain_adapter_sdk import assert_runtime_adapter_contract
        adapter = load_adapter(provider_id="exo-smoke")
        assert_runtime_adapter_contract(adapter)
        caps = adapter.get_capabilities()
        assert caps.provider_id == "exo-smoke", f"provider_id mismatch: {caps.provider_id}"
        results["conformance_contract"] = "PASS"
    except Exception as exc:
        results["conformance_contract"] = f"FAIL: {exc}"

    # --- echo adapter conformance ---
    try:
        from exo_adapter_echo import load_adapter as load_echo_adapter
        from exo_brain_adapter_sdk import assert_runtime_adapter_contract
        echo = load_echo_adapter(provider_id="echo-smoke")
        assert_runtime_adapter_contract(echo)
        assert echo.get_capabilities().provider_id == "echo-smoke"
        results["echo_conformance_contract"] = "PASS"
    except Exception as exc:
        results["echo_conformance_contract"] = f"FAIL: {exc}"

    # --- async run_turn event shape ---
    try:
        import asyncio
        from exo_adapter_openai import OpenAIAgentsRuntimeAdapter
        adapter = OpenAIAgentsRuntimeAdapter(provider_id="exo-smoke")

        async def _collect():
            await adapter.start_session("smoke-session", metadata={"agent_id": "smoke"})
            events = []
            async for ev in adapter.run_turn("smoke-session", "hello", {"run_id": "r1"}):
                events.append(str(getattr(ev.event_type, "value", ev.event_type)))
            return events

        event_types = asyncio.run(_collect())
        assert "output_delta" in event_types, f"missing output_delta: {event_types}"
        assert "run_complete" in event_types, f"missing run_complete: {event_types}"
        results["run_turn_event_shape"] = "PASS"
    except Exception as exc:
        results["run_turn_event_shape"] = f"FAIL: {exc}"

    print(json.dumps(results, indent=2))
    failed = [k for k, v in results.items() if str(v).startswith("FAIL")]
    sys.exit(1 if failed else 0)
    """
).strip()


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def main() -> int:
    workspace = _local_adapter_workspace()
    if workspace is None:
        print(
            "[smoke] SKIP: no local adapter package workspace under eXo_adapters/packages/, "
            "moving_to_adapters_project/packages/, or packages/. Run from eXo_adapters repo root instead."
        )
        return 0

    venv_dir = Path(tempfile.mkdtemp(prefix="exo_external_smoke_"))
    try:
        print(f"[smoke] Creating isolated venv: {venv_dir}")
        _run([sys.executable, "-m", "venv", str(venv_dir)])

        pip = str(venv_dir / "bin" / "pip")
        python = str(venv_dir / "bin" / "python3")

        for pkg_path in _packages_install_order(workspace):
            print(f"[smoke] Installing {pkg_path.name} ...")
            result = _run([pip, "install", "-e", str(pkg_path), "-q"], check=False)
            if result.returncode != 0:
                print(f"[smoke] FAIL: pip install {pkg_path.name}")
                print(result.stderr)
                return 1

        print("[smoke] Running assertion script ...")
        result = _run([python, "-c", ASSERTION_SCRIPT], check=False)
        print(result.stdout)
        if result.returncode != 0:
            print("[smoke] FAIL: one or more assertion checks failed")
            if result.stderr:
                print(result.stderr)
            return 1

        print("[smoke] PASS: all checks passed")
        return 0

    finally:
        shutil.rmtree(venv_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
