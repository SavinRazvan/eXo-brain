"""
File: service.py
Path: src/modules/tool_management/service.py
Role: Public module facade for tool metadata, versions, and artifact storage ownership.
Used By:
 - src/modules/platform_bootstrap/service.py
 - src/api/routers/tools.py
Depends On:
 - src/persistence/contracts.py
 - src/tools/artifact_store.py
Notes:
 - Deterministic execution remains in the turn-execution/session-runtime path.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.persistence.contracts import ToolStore, ToolVersionStore
from src.tools.artifact_store import FileSystemToolArtifactStore


@dataclass(slots=True)
class ToolManagementModule:
    tool_store: ToolStore | None
    tool_version_store: ToolVersionStore | None
    tool_artifact_store: FileSystemToolArtifactStore
    artifact_signing_secret: str
