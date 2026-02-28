"""
File: test_workflow_schema.py
Path: tests/unit/test_workflow_schema.py
Role: Unit tests for workflow schema parsing and validation behavior.
Used By:
 - pytest
Depends On:
 - src/schemas/workflow_schema.py
Notes:
 - Ensures invalid schema/version cases fail with stable error codes.
"""

from src.schemas.workflow_schema import WORKFLOW_SCHEMA_VERSION, WorkflowDefinition, WorkflowSchemaError


def test_workflow_definition_from_dict_parses_valid_payload() -> None:
    payload = {
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "workflow_id": "wf_customer_support",
        "version": "1.0.0",
        "nodes": [
            {"node_id": "collect", "agent_role": "intake"},
            {"node_id": "resolve", "agent_role": "resolver", "depends_on": ["collect"]},
        ],
        "metadata": {"owner": "ops"},
    }

    definition = WorkflowDefinition.from_dict(payload)
    assert definition.workflow_id == "wf_customer_support"
    assert definition.version == "1.0.0"
    assert [node.node_id for node in definition.nodes] == ["collect", "resolve"]


def test_workflow_definition_rejects_unsupported_schema_version() -> None:
    payload = {
        "schema_version": "2.0",
        "workflow_id": "wf_a",
        "version": "1.0.0",
        "nodes": [{"node_id": "n1", "agent_role": "worker"}],
    }

    try:
        WorkflowDefinition.from_dict(payload)
        assert False, "Expected WorkflowSchemaError for unsupported schema version"
    except WorkflowSchemaError as exc:
        assert exc.code == "WORKFLOW_SCHEMA_VERSION_UNSUPPORTED"


def test_workflow_definition_rejects_unknown_dependency() -> None:
    payload = {
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "workflow_id": "wf_b",
        "version": "1.0.0",
        "nodes": [
            {"node_id": "n1", "agent_role": "worker", "depends_on": ["n_missing"]},
        ],
    }

    try:
        WorkflowDefinition.from_dict(payload)
        assert False, "Expected WorkflowSchemaError for unknown dependency"
    except WorkflowSchemaError as exc:
        assert exc.code == "WORKFLOW_DEPENDENCY_UNKNOWN"
