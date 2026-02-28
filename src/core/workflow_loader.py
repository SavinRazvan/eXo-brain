"""
File: workflow_loader.py
Path: src/core/workflow_loader.py
Role: Loads local workflow files with schema validation and versioned registry.
Used By:
 - src/core/background_runtime.py
 - tests/unit/test_workflow_loader.py
Depends On:
 - src/schemas/workflow_schema.py
 - json
 - pathlib
Notes:
 - Supports JSON by default and YAML when PyYAML is available.
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
        resolved_source = Path(source)
        payload = self._read_payload(resolved_source)
        definition = self._parse_definition(payload=payload, source=resolved_source)
        key = (definition.workflow_id, definition.version)

        if key in self._registry and not replace_existing:
            raise WorkflowLoadError(
                "WORKFLOW_VERSION_EXISTS",
                "Workflow version already loaded",
                details={"workflow_id": definition.workflow_id, "version": definition.version},
            )

        handle = WorkflowHandle(
            workflow_id=definition.workflow_id,
            version=definition.version,
            definition=definition,
            source=str(resolved_source),
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
                "WORKFLOW_NOT_FOUND",
                "Workflow version is not loaded",
                details={"workflow_id": workflow_id, "version": version},
            )
        return self._registry[key]

    def list_workflows(self) -> list[WorkflowHandle]:
        return sorted(self._registry.values(), key=lambda handle: (handle.workflow_id, handle.version))

    def _read_payload(self, source: Path) -> dict[str, Any]:
        if not source.exists():
            raise WorkflowLoadError("WORKFLOW_SOURCE_NOT_FOUND", "Workflow source file was not found", {"source": str(source)})
        if not source.is_file():
            raise WorkflowLoadError("WORKFLOW_SOURCE_INVALID", "Workflow source must be a file", {"source": str(source)})

        suffix = source.suffix.lower()
        raw = source.read_text(encoding="utf-8")

        if suffix == ".json":
            return self._load_json(raw=raw, source=source)
        if suffix in {".yaml", ".yml"}:
            return self._load_yaml(raw=raw, source=source)

        raise WorkflowLoadError(
            "WORKFLOW_SOURCE_UNSUPPORTED",
            "Unsupported workflow file extension",
            details={"source": str(source), "extension": suffix},
        )

    def _load_json(self, raw: str, source: Path) -> dict[str, Any]:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise WorkflowLoadError(
                "WORKFLOW_JSON_INVALID",
                "Workflow JSON parsing failed",
                details={"source": str(source), "error": str(exc)},
            ) from exc
        if not isinstance(parsed, dict):
            raise WorkflowLoadError(
                "WORKFLOW_PAYLOAD_INVALID",
                "Workflow payload must be a JSON object",
                details={"source": str(source)},
            )
        return parsed

    def _load_yaml(self, raw: str, source: Path) -> dict[str, Any]:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError as exc:
            raise WorkflowLoadError(
                "WORKFLOW_YAML_DEPENDENCY_MISSING",
                "PyYAML is required to load YAML workflow files",
                details={"source": str(source)},
            ) from exc

        try:
            parsed = yaml.safe_load(raw)
        except Exception as exc:
            raise WorkflowLoadError(
                "WORKFLOW_YAML_INVALID",
                "Workflow YAML parsing failed",
                details={"source": str(source), "error": str(exc)},
            ) from exc

        if not isinstance(parsed, dict):
            raise WorkflowLoadError(
                "WORKFLOW_PAYLOAD_INVALID",
                "Workflow payload must be a YAML object",
                details={"source": str(source)},
            )
        return parsed

    def _parse_definition(self, payload: dict[str, Any], source: Path) -> WorkflowDefinition:
        try:
            return WorkflowDefinition.from_dict(payload)
        except WorkflowSchemaError as exc:
            raise WorkflowLoadError(
                code=exc.code,
                message=str(exc),
                details={"source": str(source), **exc.details},
            ) from exc
