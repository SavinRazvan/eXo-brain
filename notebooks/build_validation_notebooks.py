"""
File: build_validation_notebooks.py
Path: notebooks/build_validation_notebooks.py
Role: Build canonical and module-focused validation notebooks for deterministic execution workflows.
Used By:
 - notebooks/01_idea_validation.ipynb
 - notebooks/10_core_orchestrator_checks.ipynb
 - notebooks/11_policy_middleware_checks.ipynb
 - notebooks/12_runtime_adapter_checks.ipynb
 - notebooks/13_tenant_and_limits_checks.ipynb
Depends On:
 - nbformat
 - pathlib
 - textwrap
Notes:
 - Generates notebooks idempotently; rerun after content updates.
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


def build_01_idea_validation() -> nbf.NotebookNode:
    nb = new_notebook()
    nb.cells = [
        md(
            """
            # 01 Idea Validation (Canonical)

            One end-to-end workflow proving that tool calls are executed by your local Python code through eXo-brain's deterministic path.

            - Local smoke test works without `OPENAI_API_KEY`
            - Live model run requires `OPENAI_API_KEY`
            """
        ),
        code(
            """
            import os
            import pathlib
            import random
            import sys
            import uuid
            from typing import Optional

            _root = pathlib.Path.cwd().parent if pathlib.Path.cwd().name == "notebooks" else pathlib.Path.cwd()
            sys.path.insert(0, str(_root))

            _env = _root / ".env"
            if _env.exists():
                try:
                    from dotenv import load_dotenv
                    load_dotenv(_env, override=False)
                    print(f"Loaded .env from {_env}")
                except Exception as exc:
                    print(f"Could not load .env via dotenv: {exc}")

            from src.policies.middleware import DeterministicFirstPolicyMiddleware
            from src.schemas.tool_io import RiskTier, ToolCallContext, ToolStatus
            from src.tools.executor import DeterministicToolExecutor
            from src.tools.registry import ToolDescriptor, ToolRegistry
            from agents import Agent, ModelSettings, Runner, function_tool

            HAS_KEY = bool(os.getenv("OPENAI_API_KEY"))
            print("OPENAI_API_KEY set:", HAS_KEY)
            """
        ),
        md(
            """
            ## Define deterministic local function

            `operand3` is server-side secret and is never trusted from model input.
            """
        ),
        code(
            """
            SECRET_OPERAND3 = random.randint(1, 101)

            def _calculate_result(operation: str, operand1: float, operand2: float, operand3: float = SECRET_OPERAND3) -> dict:
                if operation == "add":
                    value = operand1 + operand2 + operand3
                elif operation == "subtract":
                    value = operand1 - operand2 + operand3
                elif operation == "multiply":
                    value = operand1 * operand2 + operand3
                elif operation == "divide":
                    if operand2 == 0:
                        raise ValueError("Cannot divide by zero")
                    value = operand1 / operand2 + operand3
                else:
                    raise ValueError(f"Unknown operation: {operation}")

                return {
                    "operation": operation,
                    "operand1": operand1,
                    "operand2": operand2,
                    "operand3": operand3,
                    "result": value,
                }

            print("SECRET_OPERAND3:", SECRET_OPERAND3)
            print("Local smoke add(5,7):", _calculate_result("add", 5, 7)["result"])
            """
        ),
        md("## Wire registry + policy + deterministic executor"),
        code(
            """
            registry = ToolRegistry()
            registry.register(
                ToolDescriptor(
                    name="calculate_result",
                    handler=_calculate_result,
                    risk_tier=RiskTier.LOW,
                    is_state_changing=False,
                )
            )
            policy = DeterministicFirstPolicyMiddleware()
            executor = DeterministicToolExecutor(registry=registry, policy=policy)
            print("Registered tools:", registry.list_tools())
            """
        ),
        md("## Mirror tool schema for model, but inject server secret"),
        code(
            """
            @function_tool
            def calculate_result(operation: str, operand1: float, operand2: float, operand3: Optional[float] = None):
                print(f"[intercepted] model operand3={operand3!r}; server operand3={SECRET_OPERAND3}")
                call = ToolCallContext(
                    schema_version="1.0",
                    call_id=str(uuid.uuid4()),
                    session_id="sess_idea",
                    run_id="run_idea",
                    job_id="job_idea",
                    task_id="task_idea",
                    agent_id="idea-agent",
                    provider_id="openai",
                    tool_name="calculate_result",
                    arguments={
                        "operation": operation,
                        "operand1": operand1,
                        "operand2": operand2,
                        "operand3": SECRET_OPERAND3,
                    },
                    risk_tier=RiskTier.LOW,
                    is_state_changing=False,
                )
                result = executor.execute(call)
                if result.status != ToolStatus.SUCCESS:
                    raise ValueError(result.error.message or "tool call failed")
                payload = result.result.get("value", {}) if isinstance(result.result, dict) else {}
                out = payload.get("result", payload)
                print(f"[intercepted] returned result={out}")
                return out
            """
        ),
        md("## Single live workflow run (`OPENAI_API_KEY` required)"),
        code(
            """
            if not HAS_KEY:
                print("Skip live run: OPENAI_API_KEY not set.")
            else:
                instructions = (
                    "You are a math assistant. Always call calculate_result for arithmetic. "
                    "Use operand3=0 as placeholder; server controls true operand3."
                )
                agent = Agent(
                    name="idea-agent",
                    instructions=instructions,
                    model="gpt-4o-mini",
                    tools=[calculate_result],
                    model_settings=ModelSettings(parallel_tool_calls=False),
                )

                question = "What is 5 plus 7?"
                print("USER:", question)
                run = await Runner.run(agent, question)
                print("AGENT:", run.final_output)
            """
        ),
        md(
            """
            ## Expected Output Checklist

            - You see `[intercepted]` lines printed by local Python function
            - Server secret operand is injected and differs from model placeholder
            - Agent final response reflects returned deterministic result
            """
        ),
    ]
    return nb


def build_10_core_orchestrator_checks() -> nbf.NotebookNode:
    nb = new_notebook()
    nb.cells = [
        md("# 10 Core Orchestrator Checks"),
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


def build_11_policy_middleware_checks() -> nbf.NotebookNode:
    nb = new_notebook()
    nb.cells = [
        md("# 11 Policy Middleware Checks"),
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


def build_12_runtime_adapter_checks() -> nbf.NotebookNode:
    nb = new_notebook()
    nb.cells = [
        md("# 12 Runtime Adapter Checks"),
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
            """
        ),
    ]
    return nb


def build_13_tenant_and_limits_checks() -> nbf.NotebookNode:
    nb = new_notebook()
    nb.cells = [
        md("# 13 Tenant and Limits Checks"),
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
        (NB_DIR / "01_idea_validation.ipynb", build_01_idea_validation()),
        (NB_DIR / "10_core_orchestrator_checks.ipynb", build_10_core_orchestrator_checks()),
        (NB_DIR / "11_policy_middleware_checks.ipynb", build_11_policy_middleware_checks()),
        (NB_DIR / "12_runtime_adapter_checks.ipynb", build_12_runtime_adapter_checks()),
        (NB_DIR / "13_tenant_and_limits_checks.ipynb", build_13_tenant_and_limits_checks()),
    ]
    for path, notebook in outputs:
        nbf.write(notebook, path)
        print(f"wrote: {path}")


if __name__ == "__main__":
    main()
