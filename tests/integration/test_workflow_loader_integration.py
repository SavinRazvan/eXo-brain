"""
File: test_workflow_loader_integration.py
Path: tests/integration/test_workflow_loader_integration.py
Role: Integration tests for workflow loader acceptance and schema-error propagation.
Used By:
 - pytest
Depends On:
 - src/core/workflow_loader.py
 - src/schemas/workflow_schema.py
Notes:
 - Ensures loader surfaces schema failures with stable error codes.
"""

from pathlib import Path

from src.core.workflow_loader import WorkflowLoadError, WorkflowLoader
from src.schemas.workflow_schema import WORKFLOW_SCHEMA_VERSION


def test_workflow_loader_accepts_valid_json_definition(tmp_path: Path) -> None:
    source = tmp_path / "workflow.json"
    source.write_text(
        (
            "{\n"
            f'  "schema_version": "{WORKFLOW_SCHEMA_VERSION}",\n'
            '  "workflow_id": "workflow.integration",\n'
            '  "version": "2.1.0",\n'
            '  "nodes": [\n'
            '    {"node_id": "collect", "agent_role": "collector"},\n'
            '    {"node_id": "summarize", "agent_role": "summarizer", "depends_on": ["collect"]}\n'
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    loader = WorkflowLoader()
    handle = loader.load_workflow(source)

    assert handle.workflow_id == "workflow.integration"
    assert handle.version == "2.1.0"
    assert len(handle.definition.nodes) == 2


def test_workflow_loader_returns_structured_error_for_invalid_schema_version(tmp_path: Path) -> None:
    source = tmp_path / "workflow.json"
    source.write_text(
        (
            "{\n"
            '  "schema_version": "0.1",\n'
            '  "workflow_id": "workflow.integration",\n'
            '  "version": "2.1.0",\n'
            '  "nodes": [\n'
            '    {"node_id": "collect", "agent_role": "collector"}\n'
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    loader = WorkflowLoader()
    try:
        loader.load_workflow(source)
        assert False, "Expected WorkflowLoadError for unsupported schema version"
    except WorkflowLoadError as exc:
        assert exc.code == "WORKFLOW_SCHEMA_VERSION_UNSUPPORTED"
        assert exc.details["source"] == str(source)
