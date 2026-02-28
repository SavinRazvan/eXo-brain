"""
File: workflow_loader.py
Path: src/core/workflow_loader.py
Role: Loads JSON/YAML workflow definitions, validates schema, and keeps a versioned registry.
Used By:
 - TBD
Depends On:
 - src/schemas/workflow_schema.py
Notes:
 - Loader is deterministic and returns structured reason codes for invalid inputs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.schemas.workflow_schema import WorkflowDefinition, WorkflowSchemaError


class WorkflowLoadError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(slots=True)
class WorkflowHandle:
    workflow_id: str
    version: str
    definition: WorkflowDefinition
    source: str
    loaded_at_utc: str


class WorkflowLoader:
    def __init__(self) -> None:
        self._registry: dict[tuple[str, str], WorkflowHandle] = {}

    def load_workflow(self, source: str | Path, replace_existing: bool = False) -> WorkflowHandle:
        source_path = Path(source)
        if not source_path.exists() or not source_path.is_file():
            raise WorkflowLoadError(
                code="WORKFLOW_SOURCE_NOT_FOUND",
                message=f"Workflow source '{source_path}' was not found",
                details={"source": str(source_path)},
            )

        payload = self._read_payload(source_path)
        definition = self._parse_definition(payload=payload, source=source_path)
        key = (definition.workflow_id, definition.version)
        if key in self._registry and not replace_existing:
            raise WorkflowLoadError(
                code="WORKFLOW_ALREADY_REGISTERED",
                message=(
                    f"Workflow '{definition.workflow_id}' version '{definition.version}' "
                    "is already loaded"
                ),
                details={"workflow_id": definition.workflow_id, "version": definition.version},
            )

        handle = WorkflowHandle(
            workflow_id=definition.workflow_id,
            version=definition.version,
            definition=definition,
            source=str(source_path),
            loaded_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        self._registry[key] = handle
        return handle

    def reload_workflow(self, source: str | Path) -> WorkflowHandle:
        return self.load_workflow(source=source, replace_existing=True)

    def get_workflow(self, workflow_id: str, version: str) -> WorkflowHandle:
        key = (workflow_id, version)
        if key not in self._registry:
            raise WorkflowLoadError(
                code="WORKFLOW_NOT_FOUND",
                message=f"Workflow '{workflow_id}' version '{version}' is not loaded",
                details={"workflow_id": workflow_id, "version": version},
            )
        return self._registry[key]

    def list_workflows(self) -> list[WorkflowHandle]:
        return sorted(self._registry.values(), key=lambda handle: (handle.workflow_id, handle.version))

    def _read_payload(self, source: Path) -> dict[str, Any]:
        suffix = source.suffix.lower()
        raw = source.read_text(encoding="utf-8")
        if suffix == ".json":
            return self._load_json(raw=raw, source=source)
        if suffix in {".yaml", ".yml"}:
            return self._load_yaml(raw=raw, source=source)
        raise WorkflowLoadError(
            code="WORKFLOW_EXTENSION_UNSUPPORTED",
            message=f"Unsupported workflow source extension '{suffix}'",
            details={"source": str(source), "extension": suffix},
        )

    def _load_json(self, raw: str, source: Path) -> dict[str, Any]:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise WorkflowLoadError(
                code="WORKFLOW_JSON_INVALID",
                message=f"Invalid JSON workflow definition in '{source}'",
                details={"source": str(source), "error": str(exc)},
            ) from exc
        if not isinstance(payload, dict):
            raise WorkflowLoadError(
                code="WORKFLOW_PAYLOAD_TYPE_INVALID",
                message=f"Workflow payload in '{source}' must be an object",
                details={"source": str(source), "received_type": type(payload).__name__},
            )
        return payload

    def _load_yaml(self, raw: str, source: Path) -> dict[str, Any]:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError as exc:
            raise WorkflowLoadError(
                code="WORKFLOW_YAML_DEPENDENCY_MISSING",
                message="PyYAML is required to load YAML workflow definitions",
                details={"source": str(source)},
            ) from exc
        try:
            payload = yaml.safe_load(raw)
        except Exception as exc:  # pragma: no cover - yaml parser-specific exceptions
            raise WorkflowLoadError(
                code="WORKFLOW_YAML_INVALID",
                message=f"Invalid YAML workflow definition in '{source}'",
                details={"source": str(source), "error": str(exc)},
            ) from exc
        if not isinstance(payload, dict):
            raise WorkflowLoadError(
                code="WORKFLOW_PAYLOAD_TYPE_INVALID",
                message=f"Workflow payload in '{source}' must be an object",
                details={"source": str(source), "received_type": type(payload).__name__},
            )
        return payload

    def _parse_definition(self, payload: dict[str, Any], source: Path) -> WorkflowDefinition:
        try:
            return WorkflowDefinition.from_dict(payload)
        except WorkflowSchemaError as exc:
            raise WorkflowLoadError(
                code=exc.code,
                message=f"Workflow schema validation failed for '{source}': {exc}",
                details={"source": str(source), **exc.details},
            ) from exc
