"""
File: test_workflow_loader.py
Path: tests/unit/test_workflow_loader.py
Role: Unit tests for workflow file loading and versioned registry behavior.
Used By:
 - pytest
Depends On:
 - src/core/workflow_loader.py
Notes:
 - Verifies deterministic error envelopes for load-time failures.
"""

from pathlib import Path

from src.core.workflow_loader import WorkflowLoadError, WorkflowLoader
from src.schemas.workflow_schema import WORKFLOW_SCHEMA_VERSION


def _write_json(path: Path, workflow_id: str = "wf_orders", version: str = "1.0.0") -> None:
    path.write_text(
        (
            "{\n"
            f'  "schema_version": "{WORKFLOW_SCHEMA_VERSION}",\n'
            f'  "workflow_id": "{workflow_id}",\n'
            f'  "version": "{version}",\n'
            '  "nodes": [\n'
            '    {"node_id": "start", "agent_role": "dispatcher"}\n'
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )


def test_workflow_loader_loads_json_and_registers_handle(tmp_path: Path) -> None:
    source = tmp_path / "orders.json"
    _write_json(source)
    loader = WorkflowLoader()

    handle = loader.load_workflow(source)
    listed = loader.list_workflows()
    fetched = loader.get_workflow("wf_orders", "1.0.0")

    assert handle.workflow_id == "wf_orders"
    assert handle.version == "1.0.0"
    assert len(listed) == 1
    assert fetched.source.endswith("orders.json")


def test_workflow_loader_rejects_duplicate_workflow_version(tmp_path: Path) -> None:
    source = tmp_path / "orders.json"
    _write_json(source)
    loader = WorkflowLoader()
    loader.load_workflow(source)

    try:
        loader.load_workflow(source)
        assert False, "Expected WorkflowLoadError for duplicate workflow version"
    except WorkflowLoadError as exc:
        assert exc.code == "WORKFLOW_VERSION_EXISTS"


def test_workflow_loader_rejects_invalid_json_payload(tmp_path: Path) -> None:
    source = tmp_path / "broken.json"
    source.write_text("{not valid json", encoding="utf-8")
    loader = WorkflowLoader()

    try:
        loader.load_workflow(source)
        assert False, "Expected WorkflowLoadError for malformed JSON"
    except WorkflowLoadError as exc:
        assert exc.code == "WORKFLOW_JSON_INVALID"


def test_workflow_loader_rejects_unsupported_extension(tmp_path: Path) -> None:
    source = tmp_path / "workflow.txt"
    source.write_text("{}", encoding="utf-8")
    loader = WorkflowLoader()

    try:
        loader.load_workflow(source)
        assert False, "Expected WorkflowLoadError for unsupported format"
    except WorkflowLoadError as exc:
        assert exc.code == "WORKFLOW_SOURCE_UNSUPPORTED"
