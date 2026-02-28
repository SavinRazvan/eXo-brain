"""
File: task_graph.py
Path: src/core/task_graph.py
Role: Directed acyclic task graph contracts and validation for background execution.
Used By:
 - src/core/scheduler.py
 - src/core/background_runtime.py
Depends On:
 - dataclasses
Notes:
 - Graph must remain deterministic for replay and checkpoint recovery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable

TaskHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class TaskNode:
    node_id: str
    handler: TaskHandler
    depends_on: list[str] = field(default_factory=list)
    retry_limit: int = 0
    timeout_ms: int = 30000
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TaskOutcome:
    node_id: str
    status: TaskStatus
    output: dict[str, Any] = field(default_factory=dict)
    reason_code: str = ""
    error_message: str = ""
    attempts: int = 1


class TaskGraph:
    def __init__(self, nodes: list[TaskNode]) -> None:
        self._nodes = {node.node_id: node for node in nodes}
        if len(self._nodes) != len(nodes):
            raise ValueError("TaskGraph contains duplicate node_id values")
        self._validate_dependencies()
        self._validate_acyclic()

    def node_ids(self) -> list[str]:
        return list(self._nodes.keys())

    def get_node(self, node_id: str) -> TaskNode:
        try:
            return self._nodes[node_id]
        except KeyError as exc:
            raise KeyError(f"Task node '{node_id}' is not defined") from exc

    def ready_nodes(self, completed: set[str], running: set[str], failed: set[str]) -> list[TaskNode]:
        ready: list[TaskNode] = []
        for node in self._nodes.values():
            if node.node_id in completed or node.node_id in running or node.node_id in failed:
                continue
            if all(dep in completed for dep in node.depends_on):
                ready.append(node)
        return ready

    def _validate_dependencies(self) -> None:
        known_nodes = set(self._nodes.keys())
        for node in self._nodes.values():
            unknown = [dep for dep in node.depends_on if dep not in known_nodes]
            if unknown:
                raise ValueError(f"Task node '{node.node_id}' depends on unknown nodes: {unknown}")

    def _validate_acyclic(self) -> None:
        visited: set[str] = set()
        active: set[str] = set()

        def dfs(node_id: str) -> None:
            if node_id in active:
                raise ValueError(f"Cycle detected at task node '{node_id}'")
            if node_id in visited:
                return
            active.add(node_id)
            for dep in self._nodes[node_id].depends_on:
                dfs(dep)
            active.remove(node_id)
            visited.add(node_id)

        for node_id in self._nodes.keys():
            dfs(node_id)
