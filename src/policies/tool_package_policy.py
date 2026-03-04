"""
File: tool_package_policy.py
Path: src/policies/tool_package_policy.py
Role: Validate tenant tool package uploads against security and scale controls.
Used By:
 - src/api/routers/tools.py
Depends On:
 - src/persistence/contracts.py
 - src/config/settings.py
Notes:
 - Validation is deterministic and side-effect free.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.config.settings import LimitsSettings
from src.persistence.contracts import ToolPackageManifest

_DANGEROUS_REQUIREMENT_TOKENS = (
    "git+",
    "http://",
    "https://",
    "file:",
    "../",
    "..\\",
    "--index-url",
    "--extra-index-url",
    "-e ",
)

_DANGEROUS_PACKAGE_REF_TOKENS = (
    "..",
    "\x00",
    "\n",
    "\r",
    "file://",
)

_REQ_NAME_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)")


@dataclass(slots=True)
class ToolPackagePolicyDecision:
    allowed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _extract_requirement_name(requirement: str) -> str:
    match = _REQ_NAME_RE.match(requirement or "")
    if not match:
        return ""
    return str(match.group(1)).strip().lower()


def validate_tool_package_upload(
    *,
    manifest: ToolPackageManifest,
    package_ref: str,
    artifact_size_bytes: int,
    limits: LimitsSettings,
) -> ToolPackagePolicyDecision:
    errors: list[str] = []
    warnings: list[str] = []

    size = max(int(artifact_size_bytes), 0)
    if size <= 0:
        warnings.append("artifact_size_bytes was not provided; size gate cannot be fully enforced")
    elif size > int(limits.max_tool_upload_size_bytes):
        errors.append(
            f"artifact_size_bytes exceeds max_tool_upload_size_bytes ({size} > {int(limits.max_tool_upload_size_bytes)})"
        )

    normalized_ref = str(package_ref or "").strip()
    if len(normalized_ref) > 2048:
        errors.append("package_ref length exceeds 2048 characters")
    lowered_ref = normalized_ref.lower()
    for token in _DANGEROUS_PACKAGE_REF_TOKENS:
        if token in lowered_ref:
            errors.append(f"package_ref contains blocked token '{token}'")
            break

    allowlist = [str(item).strip().lower() for item in limits.allowed_tool_dependency_prefixes if str(item).strip()]
    for raw_requirement in manifest.requirements:
        requirement = str(raw_requirement).strip()
        lowered_requirement = requirement.lower()
        for token in _DANGEROUS_REQUIREMENT_TOKENS:
            if token in lowered_requirement:
                errors.append(f"requirement '{requirement}' uses blocked token '{token}'")
                break
        name = _extract_requirement_name(requirement)
        if not name:
            errors.append(f"requirement '{requirement}' has invalid package name format")
            continue
        if allowlist and not any(name.startswith(prefix) for prefix in allowlist):
            errors.append(
                f"requirement '{requirement}' is not allowed by dependency allowlist"
            )

    return ToolPackagePolicyDecision(allowed=not errors, errors=errors, warnings=warnings)
