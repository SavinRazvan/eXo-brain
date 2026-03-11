"""
File: test_byoc_non_blocking_execute.py
Path: tests/modules/tools/test_byoc_non_blocking_execute.py
Role: Validate non-blocking BYOC submit path for data-plane decoupling mode.
Used By:
 - CI test suite
Depends On:
 - src/tools/byoc/connector_runtime.py
 - src/tools/registry.py
 - src/schemas/tool_io.py
Notes:
 - Confirms immediate queued response without waiting for worker callback.
"""

from __future__ import annotations

from src.schemas.tool_io import ToolCallContext, ToolStatus
from src.tools.byoc.connector_runtime import TenantByocConnectorRuntime
from src.tools.registry import ToolDescriptor


def test_byoc_execute_non_blocking_returns_queued_payload() -> None:
    runtime = TenantByocConnectorRuntime(
        worker_jwt_secret="dev-secret",
        non_blocking_execute=True,
    )
    call = ToolCallContext(
        schema_version="1.0",
        call_id="call-1",
        session_id="session-1",
        run_id="run-1",
        job_id="job-1",
        task_id="task-1",
        agent_id="agent-1",
        provider_id="provider-1",
        tool_name="sum",
        arguments={"a": 1, "b": 2},
        tenant_id="tenant-1",
    )
    descriptor = ToolDescriptor(name="sum", handler=lambda **_: 3)
    result = runtime.execute(call, descriptor)
    assert result.status == ToolStatus.SUCCESS
    assert result.result is not None
    assert result.result["value"]["queued"] is True
    assert result.result["runtime"]["mode"] == "non_blocking_submit"
