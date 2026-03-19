"""
File: test_process_runner.py
Path: tests/modules/tools/test_process_runner.py
Role: Deterministic unit tests for child-process sandbox runner behavior.
Used By:
 - pytest
Depends On:
 - src/tools/sandbox/process_runner.py
Notes:
 - Uses fake process/context doubles to cover timeout/crash/error branches without real subprocesses.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.tools.sandbox.process_runner import (
    ProcessRunnerTimeoutError,
    ProcessSandboxRunner,
    _run_handler_in_child,
)


class _QueueDouble:
    def __init__(self, *, payload: dict | None = None, raise_empty: bool = False) -> None:
        self.payload = payload
        self.raise_empty = raise_empty
        self.put_items: list[dict] = []
        self.closed = False

    def put(self, item: dict) -> None:
        self.put_items.append(item)

    def get_nowait(self) -> dict:
        if self.raise_empty:
            from queue import Empty

            raise Empty()
        if self.payload is None:
            return {}
        return self.payload

    def close(self) -> None:
        self.closed = True


@dataclass
class _ProcessPlan:
    alive_after_join: bool
    exitcode: int | None = 0
    alive_after_terminate: bool = False


class _ProcessDouble:
    def __init__(self, plan: _ProcessPlan) -> None:
        self.plan = plan
        self.started = False
        self.terminated = False
        self.killed = False
        self.join_calls: list[float] = []

    def start(self) -> None:
        self.started = True

    def join(self, timeout: float) -> None:
        self.join_calls.append(timeout)

    def is_alive(self) -> bool:
        if not self.terminated:
            return self.plan.alive_after_join
        return self.plan.alive_after_terminate and not self.killed

    @property
    def exitcode(self) -> int | None:
        return self.plan.exitcode

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


class _ContextDouble:
    def __init__(self, queue: _QueueDouble, plan: _ProcessPlan) -> None:
        self._queue = queue
        self._plan = plan
        self.created_process: _ProcessDouble | None = None

    def Queue(self, maxsize: int = 1) -> _QueueDouble:  # noqa: N802 - mirrors multiprocessing API.
        _ = maxsize
        return self._queue

    def Process(self, target, args, daemon: bool):  # noqa: N802 - mirrors multiprocessing API.
        _ = (target, args, daemon)
        proc = _ProcessDouble(self._plan)
        self.created_process = proc
        return proc


def test_run_handler_in_child_puts_success_payload() -> None:
    queue = _QueueDouble()
    _run_handler_in_child(lambda a, b: a + b, {"a": 2, "b": 3}, queue)
    assert queue.put_items == [{"ok": True, "result": 5}]


def test_run_handler_in_child_puts_error_payload() -> None:
    queue = _QueueDouble()

    def _boom() -> None:
        raise ValueError("bad input")

    _run_handler_in_child(_boom, {}, queue)
    assert queue.put_items[0]["ok"] is False
    assert queue.put_items[0]["error_type"] == "ValueError"
    assert "bad input" in queue.put_items[0]["error"]


def test_runner_init_prefers_spawn_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel_ctx = object()
    monkeypatch.setattr("src.tools.sandbox.process_runner.multiprocessing.get_all_start_methods", lambda: ["fork", "spawn"])
    monkeypatch.setattr("src.tools.sandbox.process_runner.multiprocessing.get_context", lambda method: (method, sentinel_ctx))
    runner = ProcessSandboxRunner()
    assert runner.start_method == "spawn"
    assert runner._context == ("spawn", sentinel_ctx)  # type: ignore[attr-defined]


def test_runner_raises_timeout_and_terminates_process(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = ProcessSandboxRunner(start_method="spawn")
    queue = _QueueDouble(payload={"ok": True, "result": "ignored"})
    ctx = _ContextDouble(queue=queue, plan=_ProcessPlan(alive_after_join=True, alive_after_terminate=True))
    monkeypatch.setattr(runner, "_context", ctx, raising=False)
    with pytest.raises(ProcessRunnerTimeoutError):
        runner.run(lambda: "ok", {}, timeout_ms=5)
    assert ctx.created_process is not None
    assert ctx.created_process.terminated is True
    assert ctx.created_process.killed is True


def test_runner_raises_when_process_exits_non_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = ProcessSandboxRunner(start_method="spawn")
    queue = _QueueDouble(payload={"ok": True, "result": "ignored"})
    ctx = _ContextDouble(queue=queue, plan=_ProcessPlan(alive_after_join=False, exitcode=13))
    monkeypatch.setattr(runner, "_context", ctx, raising=False)
    with pytest.raises(RuntimeError, match="exit code 13"):
        runner.run(lambda: "ok", {}, timeout_ms=50)
    assert ctx.created_process is not None
    assert ctx.created_process.terminated is True


def test_runner_raises_when_child_finishes_without_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = ProcessSandboxRunner(start_method="spawn")
    queue = _QueueDouble(raise_empty=True)
    ctx = _ContextDouble(queue=queue, plan=_ProcessPlan(alive_after_join=False, exitcode=0))
    monkeypatch.setattr(runner, "_context", ctx, raising=False)
    with pytest.raises(RuntimeError, match="without returning a result"):
        runner.run(lambda: "ok", {}, timeout_ms=50)
    assert queue.closed is True


def test_runner_raises_when_payload_reports_error(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = ProcessSandboxRunner(start_method="spawn")
    queue = _QueueDouble(payload={"ok": False, "error_type": "ValueError", "error": "bad"})
    ctx = _ContextDouble(queue=queue, plan=_ProcessPlan(alive_after_join=False, exitcode=0))
    monkeypatch.setattr(runner, "_context", ctx, raising=False)
    with pytest.raises(RuntimeError, match="ValueError: bad"):
        runner.run(lambda: "ok", {}, timeout_ms=50)
    assert queue.closed is True


def test_runner_returns_payload_result(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = ProcessSandboxRunner(start_method="spawn")
    queue = _QueueDouble(payload={"ok": True, "result": {"value": 7}})
    ctx = _ContextDouble(queue=queue, plan=_ProcessPlan(alive_after_join=False, exitcode=0))
    monkeypatch.setattr(runner, "_context", ctx, raising=False)
    result = runner.run(lambda: "ok", {}, timeout_ms=100)
    assert result == {"value": 7}
    assert queue.closed is True
