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
    WorkflowNode,
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


def test_workflow_node_rejects_non_object_payload() -> None:
    try:
        WorkflowNode.from_dict(["not", "an", "object"])  # type: ignore[arg-type]
        assert False, "Expected WorkflowSchemaError for non-object node"
    except WorkflowSchemaError as exc:
        assert exc.code == "WORKFLOW_NODE_TYPE_INVALID"
        assert exc.details["received_type"] == "list"


def test_workflow_node_rejects_invalid_required_and_optional_fields() -> None:
    invalid_payloads = (
        ({"agent_role": "planner"}, "WORKFLOW_NODE_ID_INVALID"),
        ({"node_id": "plan"}, "WORKFLOW_NODE_AGENT_ROLE_INVALID"),
        (
            {"node_id": "plan", "agent_role": "planner", "depends_on": [None]},
            "WORKFLOW_NODE_DEPENDENCIES_INVALID",
        ),
        (
            {"node_id": "plan", "agent_role": "planner", "timeout_s": 0},
            "WORKFLOW_NODE_TIMEOUT_INVALID",
        ),
        (
            {"node_id": "plan", "agent_role": "planner", "retry_limit": -1},
            "WORKFLOW_NODE_RETRY_LIMIT_INVALID",
        ),
        (
            {"node_id": "plan", "agent_role": "planner", "metadata": []},
            "WORKFLOW_NODE_METADATA_INVALID",
        ),
    )

    for payload, expected_code in invalid_payloads:
        try:
            WorkflowNode.from_dict(payload)
            assert False, f"Expected WorkflowSchemaError with code {expected_code}"
        except WorkflowSchemaError as exc:
            assert exc.code == expected_code


def test_workflow_node_from_dict_strips_strings_and_copies_metadata() -> None:
    payload = {
        "node_id": "  plan  ",
        "agent_role": "  planner  ",
        "depends_on": ["  pre  "],
        "timeout_s": 45,
        "retry_limit": 2,
        "metadata": {"tier": "gold"},
    }

    node = WorkflowNode.from_dict(payload)

    assert node.node_id == "plan"
    assert node.agent_role == "planner"
    assert node.depends_on == ["pre"]
    assert node.timeout_s == 45
    assert node.retry_limit == 2
    assert node.metadata == {"tier": "gold"}
    assert node.metadata is not payload["metadata"]


def test_workflow_definition_rejects_non_object_and_invalid_metadata() -> None:
    try:
        WorkflowDefinition.from_dict("not-an-object")  # type: ignore[arg-type]
        assert False, "Expected WorkflowSchemaError for non-object workflow payload"
    except WorkflowSchemaError as exc:
        assert exc.code == "WORKFLOW_DEFINITION_TYPE_INVALID"
        assert exc.details["received_type"] == "str"

    payload = {
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "workflow_id": "workflow.sample",
        "version": "1.0.0",
        "nodes": [{"node_id": "plan", "agent_role": "planner"}],
        "metadata": [],
    }
    try:
        WorkflowDefinition.from_dict(payload)
        assert False, "Expected WorkflowSchemaError for invalid metadata"
    except WorkflowSchemaError as exc:
        assert exc.code == "WORKFLOW_METADATA_INVALID"


def test_workflow_definition_rejects_invalid_required_top_level_fields() -> None:
    invalid_payloads = (
        (
            {"workflow_id": "workflow.sample", "version": "1.0.0", "nodes": [{"node_id": "n1", "agent_role": "planner"}]},
            "WORKFLOW_SCHEMA_VERSION_INVALID",
        ),
        (
            {"schema_version": WORKFLOW_SCHEMA_VERSION, "version": "1.0.0", "nodes": [{"node_id": "n1", "agent_role": "planner"}]},
            "WORKFLOW_ID_INVALID",
        ),
        (
            {"schema_version": WORKFLOW_SCHEMA_VERSION, "workflow_id": "workflow.sample", "nodes": [{"node_id": "n1", "agent_role": "planner"}]},
            "WORKFLOW_VERSION_INVALID",
        ),
        (
            {"schema_version": WORKFLOW_SCHEMA_VERSION, "workflow_id": "workflow.sample", "version": "1.0.0", "nodes": []},
            "WORKFLOW_NODES_INVALID",
        ),
    )

    for payload, expected_code in invalid_payloads:
        try:
            WorkflowDefinition.from_dict(payload)
            assert False, f"Expected WorkflowSchemaError with code {expected_code}"
        except WorkflowSchemaError as exc:
            assert exc.code == expected_code


def test_workflow_definition_rejects_duplicate_and_self_dependency_nodes() -> None:
    duplicate_payload = {
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "workflow_id": "workflow.sample",
        "version": "1.0.0",
        "nodes": [
            {"node_id": "plan", "agent_role": "planner"},
            {"node_id": "plan", "agent_role": "executor"},
        ],
    }
    try:
        WorkflowDefinition.from_dict(duplicate_payload)
        assert False, "Expected WorkflowSchemaError for duplicate node IDs"
    except WorkflowSchemaError as exc:
        assert exc.code == "WORKFLOW_NODE_DUPLICATE_ID"
        assert exc.details["duplicate_node_ids"] == ["plan"]

    self_dep_payload = {
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "workflow_id": "workflow.sample",
        "version": "1.0.0",
        "nodes": [{"node_id": "plan", "agent_role": "planner", "depends_on": ["plan"]}],
    }
    try:
        WorkflowDefinition.from_dict(self_dep_payload)
        assert False, "Expected WorkflowSchemaError for self dependency"
    except WorkflowSchemaError as exc:
        assert exc.code == "WORKFLOW_NODE_SELF_DEPENDENCY"
        assert exc.details["node_id"] == "plan"


def test_workflow_definition_to_dict_round_trips_and_copies_metadata() -> None:
    payload = {
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "workflow_id": "workflow.sample",
        "version": "2.0.0",
        "nodes": [{"node_id": "plan", "agent_role": "planner"}],
        "metadata": {"scope": "tenant"},
    }
    definition = WorkflowDefinition.from_dict(payload)

    serialized = definition.to_dict()

    assert serialized["workflow_id"] == "workflow.sample"
    assert serialized["version"] == "2.0.0"
    assert serialized["nodes"][0]["node_id"] == "plan"
    assert serialized["metadata"] == {"scope": "tenant"}
    assert serialized["metadata"] is not definition.metadata
