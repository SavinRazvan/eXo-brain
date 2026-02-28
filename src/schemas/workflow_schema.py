"""
File: workflow_schema.py
Path: src/schemas/workflow_schema.py
Role: Versioned schema contracts and validation for workflow definitions.
Used By:
 - src/core/workflow_loader.py
Depends On:
 - dataclasses
Notes:
 - Keep validation deterministic so invalid workflows fail with stable reason codes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

WORKFLOW_SCHEMA_VERSION = "1.0"


class WorkflowSchemaError(ValueError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(slots=True)
class WorkflowNode:
    node_id: str
    agent_role: str
    depends_on: list[str] = field(default_factory=list)
    timeout_s: int = 30
    retry_limit: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkflowNode":
        if not isinstance(payload, dict):
            raise WorkflowSchemaError(
                code="WORKFLOW_NODE_TYPE_INVALID",
                message="Workflow node must be an object",
                details={"received_type": type(payload).__name__},
            )
        node_id = payload.get("node_id")
        agent_role = payload.get("agent_role")
        if not isinstance(node_id, str) or not node_id.strip():
            raise WorkflowSchemaError(
                code="WORKFLOW_NODE_ID_INVALID",
                message="Workflow node 'node_id' must be a non-empty string",
            )
        if not isinstance(agent_role, str) or not agent_role.strip():
            raise WorkflowSchemaError(
                code="WORKFLOW_NODE_AGENT_ROLE_INVALID",
                message="Workflow node 'agent_role' must be a non-empty string",
                details={"node_id": node_id},
            )
        depends_on = payload.get("depends_on", [])
        if not isinstance(depends_on, list) or any(not isinstance(dep, str) or not dep.strip() for dep in depends_on):
            raise WorkflowSchemaError(
                code="WORKFLOW_NODE_DEPENDENCIES_INVALID",
                message="Workflow node 'depends_on' must be a list of non-empty strings",
                details={"node_id": node_id},
            )
        timeout_s = payload.get("timeout_s", 30)
        if not isinstance(timeout_s, int) or timeout_s <= 0:
            raise WorkflowSchemaError(
                code="WORKFLOW_NODE_TIMEOUT_INVALID",
                message="Workflow node 'timeout_s' must be a positive integer",
                details={"node_id": node_id},
            )
        retry_limit = payload.get("retry_limit", 0)
        if not isinstance(retry_limit, int) or retry_limit < 0:
            raise WorkflowSchemaError(
                code="WORKFLOW_NODE_RETRY_LIMIT_INVALID",
                message="Workflow node 'retry_limit' must be an integer >= 0",
                details={"node_id": node_id},
            )
        metadata = payload.get("metadata", {})
        if not isinstance(metadata, dict):
            raise WorkflowSchemaError(
                code="WORKFLOW_NODE_METADATA_INVALID",
                message="Workflow node 'metadata' must be an object",
                details={"node_id": node_id},
            )
        return cls(
            node_id=node_id.strip(),
            agent_role=agent_role.strip(),
            depends_on=[dep.strip() for dep in depends_on],
            timeout_s=timeout_s,
            retry_limit=retry_limit,
            metadata=dict(metadata),
        )


@dataclass(slots=True)
class WorkflowDefinition:
    schema_version: str
    workflow_id: str
    version: str
    nodes: list[WorkflowNode]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkflowDefinition":
        if not isinstance(payload, dict):
            raise WorkflowSchemaError(
                code="WORKFLOW_DEFINITION_TYPE_INVALID",
                message="Workflow definition must be an object",
                details={"received_type": type(payload).__name__},
            )
        schema_version = payload.get("schema_version")
        workflow_id = payload.get("workflow_id")
        version = payload.get("version")
        raw_nodes = payload.get("nodes")
        metadata = payload.get("metadata", {})
        if not isinstance(schema_version, str) or not schema_version.strip():
            raise WorkflowSchemaError(
                code="WORKFLOW_SCHEMA_VERSION_INVALID",
                message="Workflow 'schema_version' must be a non-empty string",
            )
        if not isinstance(workflow_id, str) or not workflow_id.strip():
            raise WorkflowSchemaError(
                code="WORKFLOW_ID_INVALID",
                message="Workflow 'workflow_id' must be a non-empty string",
            )
        if not isinstance(version, str) or not version.strip():
            raise WorkflowSchemaError(
                code="WORKFLOW_VERSION_INVALID",
                message="Workflow 'version' must be a non-empty string",
                details={"workflow_id": workflow_id},
            )
        if not isinstance(raw_nodes, list) or not raw_nodes:
            raise WorkflowSchemaError(
                code="WORKFLOW_NODES_INVALID",
                message="Workflow 'nodes' must be a non-empty list",
                details={"workflow_id": workflow_id},
            )
        if not isinstance(metadata, dict):
            raise WorkflowSchemaError(
                code="WORKFLOW_METADATA_INVALID",
                message="Workflow 'metadata' must be an object",
                details={"workflow_id": workflow_id},
            )

        nodes = [WorkflowNode.from_dict(node) for node in raw_nodes]
        definition = cls(
            schema_version=schema_version.strip(),
            workflow_id=workflow_id.strip(),
            version=version.strip(),
            nodes=nodes,
            metadata=dict(metadata),
        )
        definition.validate()
        return definition

    def validate(self) -> None:
        if self.schema_version != WORKFLOW_SCHEMA_VERSION:
            raise WorkflowSchemaError(
                code="WORKFLOW_SCHEMA_VERSION_UNSUPPORTED",
                message=(
                    f"Unsupported workflow schema version '{self.schema_version}'. "
                    f"Expected '{WORKFLOW_SCHEMA_VERSION}'."
                ),
                details={"schema_version": self.schema_version, "expected": WORKFLOW_SCHEMA_VERSION},
            )

        node_ids = [node.node_id for node in self.nodes]
        duplicate_ids = sorted({node_id for node_id in node_ids if node_ids.count(node_id) > 1})
        if duplicate_ids:
            raise WorkflowSchemaError(
                code="WORKFLOW_NODE_DUPLICATE_ID",
                message="Workflow contains duplicate node IDs",
                details={"duplicate_node_ids": duplicate_ids},
            )

        known = set(node_ids)
        for node in self.nodes:
            if node.node_id in node.depends_on:
                raise WorkflowSchemaError(
                    code="WORKFLOW_NODE_SELF_DEPENDENCY",
                    message="Workflow node cannot depend on itself",
                    details={"node_id": node.node_id},
                )
            unknown = sorted(set(node.depends_on) - known)
            if unknown:
                raise WorkflowSchemaError(
                    code="WORKFLOW_NODE_UNKNOWN_DEPENDENCY",
                    message="Workflow node dependency references unknown node ID",
                    details={"node_id": node.node_id, "unknown_dependencies": unknown},
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "workflow_id": self.workflow_id,
            "version": self.version,
            "nodes": [
                {
                    "node_id": node.node_id,
                    "agent_role": node.agent_role,
                    "depends_on": list(node.depends_on),
                    "timeout_s": node.timeout_s,
                    "retry_limit": node.retry_limit,
                    "metadata": dict(node.metadata),
                }
                for node in self.nodes
            ],
            "metadata": dict(self.metadata),
        }
