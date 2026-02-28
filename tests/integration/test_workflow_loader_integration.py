"""
File: test_workflow_loader_integration.py
Path: tests/integration/test_workflow_loader_integration.py
Role: Integration tests for workflow loading acceptance behavior.
Used By:
 - pytest
Depends On:
 - src/core/workflow_loader.py
Notes:
 - Covers valid load and invalid schema/version failure contract.
"""

from pathlib import Path

from src.core.workflow_loader import WorkflowLoadError, WorkflowLoader
from src.schemas.workflow_schema import WORKFLOW_SCHEMA_VERSION


def test_workflow_loader_acceptance_valid_load(tmp_path: Path) -> None:
    source = tmp_path / "support.json"
    source.write_text(
        (
            "{\n"
            f'  "schema_version": "{WORKFLOW_SCHEMA_VERSION}",\n'
            '  "workflow_id": "wf_support",\n'
            '  "version": "1.0.0",\n'
            '  "nodes": [\n'
            '    {"node_id": "triage", "agent_role": "triage"},\n'
            '    {"node_id": "answer", "agent_role": "answer", "depends_on": ["triage"]}\n'
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )
    loader = WorkflowLoader()

    handle = loader.load_workflow(source)
    assert handle.workflow_id == "wf_support"
    assert handle.version == "1.0.0"
    assert loader.get_workflow("wf_support", "1.0.0").definition.nodes[1].depends_on == ["triage"]


def test_workflow_loader_acceptance_invalid_version_fails_structured_error(tmp_path: Path) -> None:
    source = tmp_path / "invalid-version.json"
    source.write_text(
        (
            "{\n"
            '  "schema_version": "9.9",\n'
            '  "workflow_id": "wf_support",\n'
            '  "version": "1.0.0",\n'
            '  "nodes": [\n'
            '    {"node_id": "triage", "agent_role": "triage"}\n'
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )
    loader = WorkflowLoader()

    try:
        loader.load_workflow(source)
        assert False, "Expected WorkflowLoadError for invalid schema version"
    except WorkflowLoadError as exc:
        assert exc.code == "WORKFLOW_SCHEMA_VERSION_UNSUPPORTED"
        assert "source" in exc.details
