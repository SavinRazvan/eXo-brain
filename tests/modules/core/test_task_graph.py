"""
File: test_task_graph.py
Path: tests/modules/core/test_task_graph.py
Role: Unit tests for task graph validation and dependency readiness.
Used By:
 - pytest
Depends On:
 - src/core/task_graph.py
Notes:
 - Ensures deterministic graph topology constraints before scheduler execution.
"""

from __future__ import annotations

import pytest

from src.core.task_graph import TaskGraph, TaskNode


async def _noop(_: dict) -> dict:
    return {}


def test_task_graph_rejects_unknown_dependency() -> None:
    with pytest.raises(ValueError, match="unknown nodes"):
        TaskGraph(
            [
                TaskNode(node_id="a", handler=_noop),
                TaskNode(node_id="b", handler=_noop, depends_on=["missing"]),
            ]
        )


def test_task_graph_ready_nodes_respect_dependencies() -> None:
    graph = TaskGraph(
        [
            TaskNode(node_id="fetch", handler=_noop),
            TaskNode(node_id="process", handler=_noop, depends_on=["fetch"]),
            TaskNode(node_id="store", handler=_noop, depends_on=["process"]),
        ]
    )

    ready_1 = [node.node_id for node in graph.ready_nodes(completed=set(), running=set(), failed=set())]
    assert ready_1 == ["fetch"]

    ready_2 = [
        node.node_id
        for node in graph.ready_nodes(completed={"fetch"}, running=set(), failed=set())
    ]
    assert ready_2 == ["process"]
