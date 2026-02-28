"""
File: workflow_schema.py
Path: src/schemas/workflow_schema.py
Role: Versioned workflow definition schema and validation helpers.
Used By:
 - src/core/workflow_loader.py
 - tests/unit/test_workflow_schema.py
Depends On:
 - dataclasses
 - typing
Notes:
 - Keep schema validation deterministic for stable replay and portability.
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
        node_id = str(payload.get("node_id", "")).strip()
        agent_role = str(payload.get("agent_role", "")).strip()
        depends_on_raw = payload.get("depends_on", [])
        timeout_s = int(payload.get("timeout_s", 30))
        retry_limit = int(payload.get("retry_limit", 0))
        metadata = payload.get("metadata", {})

        if not node_id:
            raise WorkflowSchemaError("WORKFLOW_NODE_ID_REQUIRED", "Workflow node requires a non-empty 'node_id'")
        if not agent_role:
            raise WorkflowSchemaError("WORKFLOW_AGENT_ROLE_REQUIRED", "Workflow node requires a non-empty 'agent_role'")
        if not isinstance(depends_on_raw, list) or any(not isinstance(item, str) for item in depends_on_raw):
            raise WorkflowSchemaError(
                "WORKFLOW_DEPENDS_ON_INVALID",
                "Workflow node 'depends_on' must be a list of strings",
                details={"node_id": node_id},
            )
        if timeout_s <= 0:
            raise WorkflowSchemaError(
                "WORKFLOW_TIMEOUT_INVALID",
                "Workflow node 'timeout_s' must be greater than 0",
                details={"node_id": node_id},
            )
        if retry_limit < 0:
            raise WorkflowSchemaError(
                "WORKFLOW_RETRY_INVALID",
                "Workflow node 'retry_limit' cannot be negative",
                details={"node_id": node_id},
            )
        if not isinstance(metadata, dict):
            raise WorkflowSchemaError(
                "WORKFLOW_NODE_METADATA_INVALID",
                "Workflow node 'metadata' must be an object",
                details={"node_id": node_id},
            )

        return cls(
            node_id=node_id,
            agent_role=agent_role,
            depends_on=[str(dep).strip() for dep in depends_on_raw],
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
            raise WorkflowSchemaError("WORKFLOW_PAYLOAD_INVALID", "Workflow payload must be an object")

        schema_version = str(payload.get("schema_version", "")).strip()
        workflow_id = str(payload.get("workflow_id", "")).strip()
        version = str(payload.get("version", "")).strip()
        nodes_raw = payload.get("nodes", [])
        metadata = payload.get("metadata", {})

        if schema_version != WORKFLOW_SCHEMA_VERSION:
            raise WorkflowSchemaError(
                "WORKFLOW_SCHEMA_VERSION_UNSUPPORTED",
                "Unsupported workflow schema version",
                details={"schema_version": schema_version, "supported": WORKFLOW_SCHEMA_VERSION},
            )
        if not workflow_id:
            raise WorkflowSchemaError("WORKFLOW_ID_REQUIRED", "Workflow requires non-empty 'workflow_id'")
        if not version:
            raise WorkflowSchemaError("WORKFLOW_VERSION_REQUIRED", "Workflow requires non-empty 'version'")
        if not isinstance(nodes_raw, list) or not nodes_raw:
            raise WorkflowSchemaError("WORKFLOW_NODES_REQUIRED", "Workflow requires a non-empty 'nodes' list")
        if not isinstance(metadata, dict):
            raise WorkflowSchemaError("WORKFLOW_METADATA_INVALID", "Workflow 'metadata' must be an object")

        nodes = [WorkflowNode.from_dict(node) for node in nodes_raw]
        definition = cls(
            schema_version=schema_version,
            workflow_id=workflow_id,
            version=version,
            nodes=nodes,
            metadata=dict(metadata),
        )
        definition.validate()
        return definition

    def validate(self) -> None:
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise WorkflowSchemaError("WORKFLOW_NODE_DUPLICATE", "Workflow node IDs must be unique")

        node_id_set = set(node_ids)
        for node in self.nodes:
            if node.node_id in node.depends_on:
                raise WorkflowSchemaError(
                    "WORKFLOW_SELF_DEPENDENCY",
                    "Workflow node cannot depend on itself",
                    details={"node_id": node.node_id},
                )
            unknown_dependencies = [dep for dep in node.depends_on if dep not in node_id_set]
            if unknown_dependencies:
                raise WorkflowSchemaError(
                    "WORKFLOW_DEPENDENCY_UNKNOWN",
                    "Workflow node has unknown dependencies",
                    details={"node_id": node.node_id, "unknown_dependencies": unknown_dependencies},
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
