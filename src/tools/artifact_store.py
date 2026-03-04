"""
File: artifact_store.py
Path: src/tools/artifact_store.py
Role: Persist tenant-uploaded tool bundle artifacts (tool.yaml + handler.py) on local filesystem.
Used By:
 - src/api/bootstrap.py
 - src/api/routers/tools.py
Depends On:
 - pathlib
 - src/persistence/contracts.py
Notes:
 - Artifact paths are deterministic by tenant/tool/version and stored in tool version metadata.
 - This adapter is local-filesystem based; future adapters can implement object storage.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from pathlib import Path

from src.persistence.contracts import ToolPackageManifest


ARTIFACT_HANDLER_PATH_METADATA_KEY = "artifact_handler_path"
ARTIFACT_MANIFEST_PATH_METADATA_KEY = "artifact_manifest_path"
ARTIFACT_BUNDLE_DIR_METADATA_KEY = "artifact_bundle_dir"
ARTIFACT_BUNDLE_HASH_METADATA_KEY = "artifact_bundle_hash_sha256"
ARTIFACT_BUNDLE_SIGNATURE_METADATA_KEY = "artifact_bundle_signature_hmac_sha256"
ARTIFACT_SIGNATURE_VERSION_METADATA_KEY = "artifact_signature_version"
DEFAULT_ARTIFACT_SIGNATURE_VERSION = "v1"


def _safe_segment(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    normalized = normalized.strip("._")
    return normalized or "unknown"


def render_tool_yaml(manifest: ToolPackageManifest) -> str:
    """Render a deterministic YAML-compatible manifest document."""
    requirements = manifest.requirements or []
    req_lines = "\n".join(f"  - {item}" for item in requirements) if requirements else "  []"
    return (
        f"tool_name: {manifest.tool_name}\n"
        f"version: {manifest.version}\n"
        f"description: {manifest.description}\n"
        f"entry_file: {manifest.entry_file}\n"
        f"entrypoint: {manifest.entrypoint}\n"
        f"risk_tier: {manifest.risk_tier}\n"
        f"timeout_ms: {int(manifest.timeout_ms)}\n"
        "requirements:\n"
        f"{req_lines}\n"
    )


def compute_bundle_hash(tool_yaml: str, handler_py: str) -> str:
    digest = hashlib.sha256()
    digest.update(tool_yaml.encode("utf-8"))
    digest.update(b"\n---\n")
    digest.update(handler_py.encode("utf-8"))
    return digest.hexdigest()


def compute_bundle_hash_from_files(manifest_path: str, handler_path: str) -> str:
    tool_yaml = Path(manifest_path).read_text(encoding="utf-8")
    handler_py = Path(handler_path).read_text(encoding="utf-8")
    return compute_bundle_hash(tool_yaml, handler_py)


def sign_bundle_hash(bundle_hash: str, signing_secret: str, version: str = DEFAULT_ARTIFACT_SIGNATURE_VERSION) -> str:
    if not signing_secret.strip():
        raise ValueError("tool artifact signing secret is required")
    payload = f"{version}:{bundle_hash}".encode("utf-8")
    return hmac.new(signing_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_bundle_signature(
    *,
    bundle_hash: str,
    signature: str,
    signing_secret: str,
    version: str = DEFAULT_ARTIFACT_SIGNATURE_VERSION,
) -> bool:
    expected = sign_bundle_hash(bundle_hash, signing_secret, version)
    return hmac.compare_digest(expected, signature)


@dataclass(slots=True)
class ToolArtifactBundlePaths:
    bundle_dir: str
    manifest_path: str
    handler_path: str


class FileSystemToolArtifactStore:
    """Persist tool bundle artifacts under a configured root directory."""

    def __init__(self, root_dir: str | Path) -> None:
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)

    def persist_bundle(
        self,
        *,
        tenant_id: str,
        tool_name: str,
        version: str,
        tool_yaml: str,
        handler_py: str,
    ) -> ToolArtifactBundlePaths:
        tenant_segment = _safe_segment(tenant_id)
        tool_segment = _safe_segment(tool_name)
        version_segment = _safe_segment(version)
        bundle_dir = self._root_dir / tenant_segment / tool_segment / version_segment
        bundle_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = bundle_dir / "tool.yaml"
        handler_path = bundle_dir / "handler.py"
        manifest_path.write_text(tool_yaml, encoding="utf-8")
        handler_path.write_text(handler_py, encoding="utf-8")
        return ToolArtifactBundlePaths(
            bundle_dir=str(bundle_dir),
            manifest_path=str(manifest_path),
            handler_path=str(handler_path),
        )
