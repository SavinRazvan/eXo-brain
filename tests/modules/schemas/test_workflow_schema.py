"""
File: test_workflow_schema.py
Path: tests/modules/schemas/test_workflow_schema.py
Role: Unit tests for workflow schema parsing and validation behavior.
Used By:
 - pytest
Depends On:
 - src/schemas/workflow_schema.py
Notes:
 - Guards schema invariants used by workflow loading and execution.
"""

from src.schemas.workflow_schema import (
    WORKFLOW_SCHEMA_VERSION,
    WorkflowDefinition,
    WorkflowSchemaError,
)


def test_workflow_definition_from_dict_valid_payload() -> None:
    payload = {
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "workflow_id": "workflow.sample",
        "version": "1.0.0",
        "nodes": [
            {"node_id": "plan", "agent_role": "planner"},
            {"node_id": "execute", "agent_role": "executor", "depends_on": ["plan"]},
        ],
    }

    definition = WorkflowDefinition.from_dict(payload)

    assert definition.workflow_id == "workflow.sample"
    assert definition.version == "1.0.0"
    assert [node.node_id for node in definition.nodes] == ["plan", "execute"]


def test_workflow_definition_rejects_unsupported_schema_version() -> None:
    payload = {
        "schema_version": "0.9",
        "workflow_id": "workflow.sample",
        "version": "1.0.0",
        "nodes": [{"node_id": "plan", "agent_role": "planner"}],
    }

    try:
        WorkflowDefinition.from_dict(payload)
        assert False, "Expected WorkflowSchemaError for unsupported schema version"
    except WorkflowSchemaError as exc:
        assert exc.code == "WORKFLOW_SCHEMA_VERSION_UNSUPPORTED"


def test_workflow_definition_rejects_unknown_dependencies() -> None:
    payload = {
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "workflow_id": "workflow.sample",
        "version": "1.0.0",
        "nodes": [
            {"node_id": "plan", "agent_role": "planner"},
            {"node_id": "execute", "agent_role": "executor", "depends_on": ["missing"]},
        ],
    }

    try:
        WorkflowDefinition.from_dict(payload)
        assert False, "Expected WorkflowSchemaError for unknown dependency"
    except WorkflowSchemaError as exc:
        assert exc.code == "WORKFLOW_NODE_UNKNOWN_DEPENDENCY"
        assert exc.details["node_id"] == "execute"
