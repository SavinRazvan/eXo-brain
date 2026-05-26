"""
File: process_runner.py
Path: src/tools/sandbox/process_runner.py
Role: Execute hosted sandbox tool handlers in short-lived child processes.
Used By:
 - src/tools/sandbox/runtime.py
Depends On:
 - multiprocessing
 - queue
Notes:
 - This is a process-isolation baseline with hard timeout termination semantics.
 - Handlers must be serializable by the selected multiprocessing start method.
"""

from __future__ import annotations

import multiprocessing
from queue import Empty
from typing import Any, Callable, cast


class ProcessRunnerTimeoutError(TimeoutError):
    """Raised when a process-isolated invocation exceeds timeout."""


def _run_handler_in_child(
    handler: Callable[..., Any],
    arguments: dict[str, Any],
    result_queue: Any,
) -> None:
    try:
        result = handler(**arguments)
        result_queue.put({"ok": True, "result": result})
    except Exception as exc:  # pragma: no cover - defensive child boundary
        result_queue.put({"ok": False, "error": str(exc), "error_type": type(exc).__name__})


class ProcessSandboxRunner:
    """Run a single tool invocation in a child process."""

    def __init__(self, start_method: str | None = None) -> None:
        methods = multiprocessing.get_all_start_methods()
        selected = start_method or ("spawn" if "spawn" in methods else methods[0])
        self._context = multiprocessing.get_context(selected)
        self._start_method = selected

    @property
    def start_method(self) -> str:
        return self._start_method

    def run(
        self,
        handler: Callable[..., Any],
        arguments: dict[str, Any],
        timeout_ms: int,
    ) -> Any:
        timeout_seconds = max(int(timeout_ms), 1) / 1000.0
        queue: Any = self._context.Queue(maxsize=1)
        process_factory = cast(Any, self._context).Process
        process = process_factory(target=_run_handler_in_child, args=(handler, arguments, queue), daemon=True)
        process.start()
        process.join(timeout_seconds)

        if process.is_alive():
            self._terminate(process)
            raise ProcessRunnerTimeoutError(f"Process-isolated runtime timed out after {timeout_ms}ms.")

        if process.exitcode not in (0, None):
            self._terminate(process)
            raise RuntimeError(f"Process-isolated runtime crashed with exit code {process.exitcode}.")

        try:
            payload = queue.get_nowait()
        except Empty as exc:
            raise RuntimeError("Process-isolated runtime finished without returning a result.") from exc
        finally:
            queue.close()

        if not payload.get("ok", False):
            error_type = payload.get("error_type", "RuntimeError")
            message = payload.get("error", "Unknown child-process execution error.")
            raise RuntimeError(f"{error_type}: {message}")
        return payload.get("result")

    @staticmethod
    def _terminate(process: multiprocessing.Process) -> None:
        process.terminate()
        process.join(0.2)
        if process.is_alive() and hasattr(process, "kill"):
            process.kill()
            process.join(0.2)
