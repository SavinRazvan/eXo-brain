"""
File: external_install_smoke.py
Path: scripts/packages/external_install_smoke.py
Role: Validates that all eXo adapter packages install and import cleanly from PyPI in an isolated venv.
Used By:
 - CI gates
 - scripts/release/rc_signoff.py (optional gate)
 - make targets
Depends On:
 - PyPI distributions at pins matching requirements.txt
Notes:
 - Canonical multi-package smoke also lives in SavinRazvan/eXo_adapters.
 - Creates a throwaway venv in /tmp, installs all four packages from PyPI (or editable sibling fallback), runs assertions.
 - Exit code 0 = pass, non-zero = fail.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PACKAGE_DIRS = (
    "exo-brain-core-contracts",
    "exo-brain-adapter-sdk",
    "exo-adapter-echo",
    "exo-adapter-openai",
)


def _read_pypi_pins() -> tuple[str, ...]:
    req_path = REPO_ROOT / "requirements-adapters.txt"
    pins = [
        line.strip()
        for line in req_path.read_text(encoding="utf-8").splitlines()
        if re.match(r"^exo-(brain-|adapter-)", line.strip())
    ]
    if len(pins) != 4:
        raise RuntimeError(f"expected 4 adapter pins in {req_path}, got {len(pins)}")
    return tuple(pins)


def _sibling_adapter_packages_root() -> Path | None:
    for candidate in (
        REPO_ROOT.parent / "eXo_adapters" / "packages",
        Path.home() / "Projects" / "eXo_adapters" / "packages",
    ):
        if (candidate / "exo-brain-core-contracts" / "pyproject.toml").is_file():
            return candidate
    return None

ASSERTION_SCRIPT = textwrap.dedent(
    """
    import sys, json

    results = {}

    try:
        from exo_brain_core_contracts import (
            RuntimeAdapter, ProviderCapabilityMap, ToolCallContext,
            RuntimeEvent, RuntimeEventType,
        )
        results["core_contracts_import"] = "PASS"
    except Exception as exc:
        results["core_contracts_import"] = f"FAIL: {exc}"

    try:
        from exo_brain_adapter_sdk import (
            assert_runtime_adapter_contract,
            AdapterToolDescriptor,
            ToolExecutionAdapterContract,
        )
        results["adapter_sdk_import"] = "PASS"
    except Exception as exc:
        results["adapter_sdk_import"] = f"FAIL: {exc}"

    try:
        from exo_adapter_openai import OpenAIAgentsRuntimeAdapter, load_adapter, build_agent_tools
        results["openai_adapter_import"] = "PASS"
    except Exception as exc:
        results["openai_adapter_import"] = f"FAIL: {exc}"

    try:
        from exo_adapter_echo import EchoRuntimeAdapter, load_adapter as load_echo_adapter
        results["echo_adapter_import"] = "PASS"
    except Exception as exc:
        results["echo_adapter_import"] = f"FAIL: {exc}"

    try:
        from exo_adapter_openai import OpenAIAgentsRuntimeAdapter
        module = OpenAIAgentsRuntimeAdapter.__module__
        if module.startswith("src."):
            results["module_origin"] = f"FAIL: monorepo path leaked: {module}"
        else:
            results["module_origin"] = f"PASS (module={module})"
    except Exception as exc:
        results["module_origin"] = f"FAIL: {exc}"

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

    try:
        from exo_adapter_echo import load_adapter as load_echo_adapter
        from exo_brain_adapter_sdk import assert_runtime_adapter_contract
        echo = load_echo_adapter(provider_id="echo-smoke")
        assert_runtime_adapter_contract(echo)
        assert echo.get_capabilities().provider_id == "echo-smoke"
        results["echo_conformance_contract"] = "PASS"
    except Exception as exc:
        results["echo_conformance_contract"] = f"FAIL: {exc}"

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
    pypi_pins = _read_pypi_pins()
    venv_dir = Path(tempfile.mkdtemp(prefix="exo_external_smoke_"))
    install_mode = "pypi"
    try:
        print(f"[smoke] Creating isolated venv: {venv_dir}")
        _run([sys.executable, "-m", "venv", str(venv_dir)])

        pip = str(venv_dir / "bin" / "pip")
        python = str(venv_dir / "bin" / "python3")

        pypi_failed = False
        for pin in pypi_pins:
            print(f"[smoke] Installing {pin} from PyPI ...")
            result = _run([pip, "install", pin, "-q"], check=False)
            if result.returncode != 0:
                print(f"[smoke] PyPI install failed for {pin}")
                pypi_failed = True
                break

        if pypi_failed:
            sibling_root = _sibling_adapter_packages_root()
            if sibling_root is None:
                print("[smoke] FAIL: PyPI install failed and no sibling eXo_adapters/packages found")
                return 1
            install_mode = "editable-sibling"
            print(f"[smoke] Falling back to editable installs from {sibling_root}")
            for pkg_name in PACKAGE_DIRS:
                pkg_path = sibling_root / pkg_name
                result = _run([pip, "install", "-e", str(pkg_path), "-q"], check=False)
                if result.returncode != 0:
                    print(f"[smoke] FAIL: editable install {pkg_name}")
                    if result.stderr:
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

        print(f"[smoke] PASS: all checks passed ({install_mode} install)")
        return 0

    finally:
        shutil.rmtree(venv_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
