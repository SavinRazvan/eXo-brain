"""
File: build_checks.py
Path: notebooks/build_checks.py
Role: Generates module smoke-check notebooks (check_01 through check_04) from source.
Used By:
 - notebooks/check_01_core_orchestrator.ipynb
 - notebooks/check_02_policy_middleware.ipynb
 - notebooks/check_03_runtime_adapter.ipynb
 - notebooks/check_04_tenant_and_limits.ipynb
Depends On:
 - nbformat
 - pathlib
 - textwrap
Notes:
 - Generates notebooks idempotently; rerun after content updates.
 - Does not preserve existing cell outputs; re-run the notebook to refresh them.
"""

from __future__ import annotations

from pathlib import Path
import textwrap

import nbformat as nbf


NB_DIR = Path(__file__).parent


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(textwrap.dedent(text).strip())


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(textwrap.dedent(text).strip())


def new_notebook() -> nbf.NotebookNode:
    nb = nbf.v4.new_notebook()
    nb.metadata["kernelspec"] = {
        "display_name": "eXo-brain (.exo_env)",
        "language": "python",
        "name": "exo-brain",
    }
    nb.metadata["language_info"] = {"name": "python", "version": "3.13"}
    return nb


def build_check_01_core_orchestrator() -> nbf.NotebookNode:
    nb = new_notebook()
    nb.cells = [
        md("# Check 01 — Core Orchestrator"),
        code(
            """
            import pathlib
            import sys

            _root = pathlib.Path.cwd().parent if pathlib.Path.cwd().name == "notebooks" else pathlib.Path.cwd()
            sys.path.insert(0, str(_root))

            from src.core.orchestrator import Orchestrator
            from src.policies.middleware import DeterministicFirstPolicyMiddleware
            from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter
            from src.schemas.events import RuntimeEventType
            from src.schemas.tool_io import RiskTier
            from src.tools.executor import DeterministicToolExecutor
            from src.tools.registry import ToolDescriptor, ToolRegistry
            """
        ),
        code(
            """
            registry = ToolRegistry()
            registry.register(
                ToolDescriptor(
                    name="double_value",
                    handler=lambda x: x * 2,
                    risk_tier=RiskTier.HIGH,
                    is_state_changing=True,
                )
            )
            policy = DeterministicFirstPolicyMiddleware()
            orchestrator = Orchestrator(
                runtime_adapter=OpenAIAgentsRuntimeAdapter(),
                policy_middleware=policy,
                tool_executor=DeterministicToolExecutor(registry=registry, policy=policy),
            )

            context = {
                "run_id": "run_core_nb",
                "job_id": "job_core_nb",
                "task_id": "task_core_nb",
                "agent_id": "agent_core_nb",
                "planned_tool_call": {
                    "call_id": "tc_core_nb",
                    "tool_name": "double_value",
                    "arguments": {"x": 11},
                    "risk_tier": "high",
                    "is_state_changing": True,
                },
            }

            events = []
            async for event in orchestrator.run_turn("sess_core_nb", "run deterministic", context):
                events.append(event)
                print(event.event_type.value, event.payload)

            event_types = [e.event_type for e in events]
            assert RuntimeEventType.RUN_COMPLETE in event_types, "Missing RUN_COMPLETE event"
            tool_progress_states = [
                e.payload.get("state")
                for e in events
                if e.event_type == RuntimeEventType.TOOL_PROGRESS
            ]
            assert "completed" in tool_progress_states, "Missing completed TOOL_PROGRESS state"
            print("PASS: orchestrator deterministic tool path")
            """
        ),
        md("Troubleshooting: if assertions fail, verify `planned_tool_call` and `tool_name` registration match."),
    ]
    return nb


def build_check_02_policy_middleware() -> nbf.NotebookNode:
    nb = new_notebook()
    nb.cells = [
        md("# Check 02 — Policy Middleware"),
        code(
            """
            import pathlib
            import sys

            _root = pathlib.Path.cwd().parent if pathlib.Path.cwd().name == "notebooks" else pathlib.Path.cwd()
            sys.path.insert(0, str(_root))

            from src.policies.middleware import DeterministicFirstPolicyMiddleware
            from src.schemas.tool_io import (
                ExecutionMetadata,
                RiskTier,
                ToolAudit,
                ToolCallContext,
                ToolExecutionMode,
                ToolResult,
                ToolStatus,
            )
            """
        ),
        code(
            """
            policy = DeterministicFirstPolicyMiddleware()

            call = ToolCallContext(
                schema_version="1.0",
                call_id="call_policy_nb",
                session_id="sess_policy_nb",
                run_id="run_policy_nb",
                job_id="job_policy_nb",
                task_id="task_policy_nb",
                agent_id="agent_policy_nb",
                provider_id="openai",
                tool_name="safe_tool",
                arguments={"value": 1},
                risk_tier=RiskTier.LOW,
                is_state_changing=False,
            )
            decision = policy.before_tool_call(call)
            assert decision.decision.value in {"allow", "deny", "escalate"}
            print("before_tool_call:", decision.decision.value, decision.reason_code)

            bad_result = ToolResult(
                schema_version="1.0",
                call_id="call_policy_nb",
                tool_name="safe_tool",
                status=ToolStatus.SUCCESS,
                result=None,  # triggers post-check failure for success payload missing
                execution=ExecutionMetadata(mode_used=ToolExecutionMode.DETERMINISTIC),
                audit=ToolAudit(correlation_id="call_policy_nb"),
            )
            checked = policy.after_tool_call(bad_result)
            assert checked.status == ToolStatus.ERROR
            assert checked.error.code == "POLICY_POSTCHECK_FAILED"
            print("after_tool_call post-check:", checked.error.code)
            print("PASS: policy middleware checks")
            """
        ),
    ]
    return nb


def build_check_03_runtime_adapter() -> nbf.NotebookNode:
    nb = new_notebook()
    nb.cells = [
        md("# Check 03 — Runtime Adapter"),
        code(
            """
            import pathlib
            import sys

            _root = pathlib.Path.cwd().parent if pathlib.Path.cwd().name == "notebooks" else pathlib.Path.cwd()
            sys.path.insert(0, str(_root))

            from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter
            from src.schemas.events import RuntimeEventType
            """
        ),
        code(
            """
            import asyncio

            async def _run_check():
                adapter = OpenAIAgentsRuntimeAdapter()
                handle = await adapter.start_session("sess_runtime_nb", {"agent_id": "runtime-nb"})
                assert handle.session_id == "sess_runtime_nb"

                health = await adapter.healthcheck()
                caps = adapter.get_capabilities()
                print("health:", health.state.value, health.reason)
                print("capabilities provider:", caps.provider_id)

                context = {
                    "run_id": "run_runtime_nb",
                    "job_id": "job_runtime_nb",
                    "task_id": "task_runtime_nb",
                    "agent_id": "agent_runtime_nb",
                    "planned_tool_call": {
                        "call_id": "tc_runtime_nb",
                        "tool_name": "fake_tool",
                        "arguments": {"x": 1},
                        "risk_tier": "low",
                        "is_state_changing": False,
                    },
                }
                events = []
                async for event in adapter.run_turn("sess_runtime_nb", "hello", context):
                    events.append(event)
                    print(event.event_type.value, event.payload)

                assert any(e.event_type == RuntimeEventType.TOOL_INTENT for e in events)
                print("PASS: runtime adapter planned tool-intent path")

            # Works in both async-native kernels and standard synchronous kernels
            try:
                loop = asyncio.get_running_loop()
                import nest_asyncio
                nest_asyncio.apply()
                loop.run_until_complete(_run_check())
            except RuntimeError:
                asyncio.run(_run_check())
            """
        ),
    ]
    return nb


def build_check_04_tenant_and_limits() -> nbf.NotebookNode:
    nb = new_notebook()
    nb.cells = [
        md("# Check 04 — Tenant and Limits"),
        code(
            """
            import pathlib
            import sys
            import tempfile

            _root = pathlib.Path.cwd().parent if pathlib.Path.cwd().name == "notebooks" else pathlib.Path.cwd()
            sys.path.insert(0, str(_root))

            from src.tenancy.quotas import TenantQuotaManager
            from src.tenancy.rate_limiter import TenantRateLimiter, SQLiteTenantRateLimiter
            """
        ),
        code(
            """
            quota = TenantQuotaManager(max_active_jobs_per_tenant=2, hard_enforcement=True)
            assert quota.check_submission("tenant-a", active_jobs=0).allowed
            assert quota.check_submission("tenant-a", active_jobs=1).allowed
            denied = quota.check_submission("tenant-a", active_jobs=2)
            assert not denied.allowed
            print("quota denial:", denied.reason_code)

            mem_limiter = TenantRateLimiter(max_requests=2, window_seconds=60)
            a1, _ = mem_limiter.allow("tenant-a")
            a2, _ = mem_limiter.allow("tenant-a")
            a3, retry = mem_limiter.allow("tenant-a")
            assert a1 and a2 and (not a3) and retry > 0
            print("memory limiter ok")

            with tempfile.TemporaryDirectory() as tmp:
                db_path = str(pathlib.Path(tmp) / "limits.db")
                sqlite_limiter = SQLiteTenantRateLimiter(
                    db_path=db_path, max_requests=1, window_seconds=60, limiter_id="turns"
                )
                ok1, _ = sqlite_limiter.allow("tenant-b")
                ok2, retry2 = sqlite_limiter.allow("tenant-b")
                assert ok1 and (not ok2) and retry2 > 0
                print("sqlite limiter ok")

            print("PASS: tenancy and limits checks")
            """
        ),
    ]
    return nb


def main() -> None:
    outputs: list[tuple[Path, nbf.NotebookNode]] = [
        (NB_DIR / "check_01_core_orchestrator.ipynb", build_check_01_core_orchestrator()),
        (NB_DIR / "check_02_policy_middleware.ipynb", build_check_02_policy_middleware()),
        (NB_DIR / "check_03_runtime_adapter.ipynb", build_check_03_runtime_adapter()),
        (NB_DIR / "check_04_tenant_and_limits.ipynb", build_check_04_tenant_and_limits()),
    ]
    for path, notebook in outputs:
        nbf.write(notebook, path)
        print(f"wrote: {path}")


if __name__ == "__main__":
    main()
