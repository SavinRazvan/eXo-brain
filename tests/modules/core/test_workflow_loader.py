"""
File: test_workflow_loader.py
Path: tests/modules/core/test_workflow_loader.py
Role: Unit tests for workflow loader registry behavior and source parsing errors.
Used By:
 - pytest
Depends On:
 - src/core/workflow_loader.py
 - src/schemas/workflow_schema.py
Notes:
 - Validates structured error codes used by higher-level orchestration flows.
"""

from pathlib import Path

from src.core.workflow_loader import WorkflowLoadError, WorkflowLoader
from src.schemas.workflow_schema import WORKFLOW_SCHEMA_VERSION


def _write_valid_workflow(path: Path) -> None:
    path.write_text(
        (
            "{\n"
            f'  "schema_version": "{WORKFLOW_SCHEMA_VERSION}",\n'
            '  "workflow_id": "workflow.sample",\n'
            '  "version": "1.0.0",\n'
            '  "nodes": [\n'
            '    {"node_id": "plan", "agent_role": "planner"}\n'
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )


def test_workflow_loader_loads_and_registers_json_workflow(tmp_path: Path) -> None:
    loader = WorkflowLoader()
    source = tmp_path / "workflow.json"
    _write_valid_workflow(source)

    handle = loader.load_workflow(source)

    assert handle.workflow_id == "workflow.sample"
    assert handle.version == "1.0.0"
    assert loader.get_workflow("workflow.sample", "1.0.0").source == str(source)
    assert len(loader.list_workflows()) == 1


def test_workflow_loader_rejects_invalid_json(tmp_path: Path) -> None:
    loader = WorkflowLoader()
    source = tmp_path / "broken.json"
    source.write_text("{invalid}", encoding="utf-8")

    try:
        loader.load_workflow(source)
        assert False, "Expected WorkflowLoadError for invalid JSON"
    except WorkflowLoadError as exc:
        assert exc.code == "WORKFLOW_JSON_INVALID"


def test_workflow_loader_rejects_unsupported_extension(tmp_path: Path) -> None:
    loader = WorkflowLoader()
    source = tmp_path / "workflow.txt"
    source.write_text("{}", encoding="utf-8")

    try:
        loader.load_workflow(source)
        assert False, "Expected WorkflowLoadError for unsupported extension"
    except WorkflowLoadError as exc:
        assert exc.code == "WORKFLOW_EXTENSION_UNSUPPORTED"


def test_workflow_loader_requires_replace_for_duplicate_registration(tmp_path: Path) -> None:
    loader = WorkflowLoader()
    source = tmp_path / "workflow.json"
    _write_valid_workflow(source)

    loader.load_workflow(source)

    try:
        loader.load_workflow(source)
        assert False, "Expected WorkflowLoadError for duplicate workflow registration"
    except WorkflowLoadError as exc:
        assert exc.code == "WORKFLOW_ALREADY_REGISTERED"

    replaced = loader.load_workflow(source, replace_existing=True)
    assert replaced.workflow_id == "workflow.sample"
