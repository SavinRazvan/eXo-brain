#!/usr/bin/env python3
"""
File: audit_local_workspace_deps.py
Path: scripts/dev/audit_local_workspace_deps.py
Role: Compare `.local/` paths referenced in versioned governance sources against on-disk files.
Used By:
 - Maintainers before archiving or pruning gitignored `.local/` content
Depends On:
 - pathlib
 - re
 - json
 - argparse
Notes:
 - Read-only; does not modify `.local/` or tracked files.
 - Scans scripts/, .agents/, .cursor/, AGENTS.md, Makefile, and docs/operations/.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LOCAL = REPO / ".local"

SCAN_TARGETS: tuple[str, ...] = (
    "scripts",
    ".agents",
    ".cursor",
    "AGENTS.md",
    "Makefile",
    "docs/operations",
    "docs/templates/local-workspace",
)

TEXT_SUFFIXES = {
    ".md",
    ".mdc",
    ".py",
    ".yml",
    ".yaml",
    ".json",
    ".sh",
    "",
}

# Paths that block prepare/merge workflows when missing (exact files or dirs).
GATE_CRITICAL: tuple[tuple[str, str], ...] = (
    (".local/index-and-planning/current", "prepare gate: planning dir"),
    (
        ".local/index-and-planning/current/test-plan.md",
        "prepare gate: check_testing_artifacts.py",
    ),
    (
        ".local/index-and-planning/current/test-index.md",
        "prepare gate: check_testing_artifacts.py",
    ),
    (
        ".local/workflow-artifacts/pr/review.md",
        "merge gate: active PR review artifact",
    ),
    (
        ".local/workflow-artifacts/pr/prep.md",
        "merge gate: active PR prepare artifact",
    ),
    (
        ".local/workflow-artifacts/alignment/alignment-audit.md",
        "merge gate (--arch-impacting): alignment audit",
    ),
    (
        ".local/workflow-artifacts/alignment/alignment-todos.md",
        "merge gate (--arch-impacting): alignment todos",
    ),
)

LOCAL_ELLIPSIS_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (".local/.../current/", ".local/index-and-planning/current/"),
    (".local/.../current", ".local/index-and-planning/current"),
    (".local/agents-control-center/config/pages.json", ".local/agents-control-center/config/pages.json"),
)

LOCAL_REF_RE = re.compile(
    r"\.local/"
    r"(?:"
    r"[A-Za-z0-9_./\-]+|\.\.\./[A-Za-z0-9_./\-]+|\*\*|\*"
    r")+"
)


@dataclass
class Reference:
    rel_path: str
    sources: set[str] = field(default_factory=set)
    is_glob: bool = False


def _normalize_local_ref(raw: str) -> tuple[str | None, bool]:
    cleaned = raw.strip().strip("`\"'")
    cleaned = cleaned.rstrip(".,;:)")
    if not cleaned.startswith(".local/"):
        return None, False
    suffix = cleaned[len(".local/") :]
    suffix = suffix.replace("\\", "/")
    is_glob = "*" in suffix
    for src, dst in LOCAL_ELLIPSIS_REPLACEMENTS:
        if cleaned.startswith(src.rstrip("/")) or cleaned == src.rstrip("/"):
            cleaned = dst.rstrip("/") if not is_glob else dst.rstrip("/")
            suffix = cleaned[len(".local/") :]
            break
    suffix = re.sub(r"/\*\*(?:/|$)", "/", suffix)
    suffix = suffix.replace("...", "index-and-planning")
    suffix = re.sub(r"/{2,}", "/", suffix)
    suffix = suffix.rstrip("/")
    if not suffix:
        return ".local", is_glob
    return f".local/{suffix}", is_glob


def _iter_scan_files() -> list[Path]:
    files: list[Path] = []
    for target in SCAN_TARGETS:
        path = REPO / target
        if path.is_file():
            files.append(path)
            continue
        if not path.is_dir():
            continue
        for candidate in path.rglob("*"):
            if not candidate.is_file():
                continue
            if candidate.suffix in TEXT_SUFFIXES or candidate.name in {
                "Makefile",
                "AGENTS.md",
            }:
                files.append(candidate)
    return sorted(files)


def _collect_text_references() -> dict[str, Reference]:
    refs: dict[str, Reference] = {}
    for file_path in _iter_scan_files():
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel_source = file_path.relative_to(REPO).as_posix()
        for match in LOCAL_REF_RE.finditer(text):
            normalized, is_glob = _normalize_local_ref(match.group(0))
            if normalized is None:
                continue
            entry = refs.setdefault(normalized, Reference(rel_path=normalized))
            entry.sources.add(rel_source)
            entry.is_glob = entry.is_glob or is_glob
    return refs


def _collect_pages_json_references() -> dict[str, Reference]:
    refs: dict[str, Reference] = {}
    pages_json = LOCAL / "agents-control-center" / "config" / "pages.json"
    if not pages_json.is_file():
        return refs
    try:
        payload = json.loads(pages_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return refs
    pages = payload.get("pages")
    if not isinstance(pages, list):
        return refs
    base = pages_json.parent
    for page in pages:
        if not isinstance(page, dict):
            continue
        rel_file = page.get("file")
        if not isinstance(rel_file, str):
            continue
        resolved = (base / rel_file).resolve()
        try:
            rel_local = resolved.relative_to(LOCAL.resolve())
        except ValueError:
            continue
        normalized = f".local/{rel_local.as_posix()}"
        entry = refs.setdefault(normalized, Reference(rel_path=normalized))
        entry.sources.add(".local/agents-control-center/config/pages.json")
    return refs


def _disk_paths() -> set[str]:
    if not LOCAL.is_dir():
        return set()
    paths: set[str] = set()
    for path in LOCAL.rglob("*"):
        rel = path.relative_to(REPO).as_posix()
        paths.add(rel)
        if path.is_dir():
            continue
    return paths


def _path_exists(normalized: str, disk: set[str]) -> bool:
    if normalized in disk:
        return True
    candidate = REPO / normalized.removeprefix("./")
    return candidate.exists()


def _expand_glob_reference(ref: Reference, disk_files: set[str]) -> set[str]:
    if not ref.is_glob:
        return {ref.rel_path}
    pattern = ref.rel_path.removeprefix(".local/")
    if pattern.endswith("*.md"):
        prefix = pattern[: -len("*.md")].rstrip("/")
        return {
            disk_path
            for disk_path in disk_files
            if disk_path.endswith(".md")
            and disk_path.removeprefix(".local/").startswith(prefix + "/")
        }
    if pattern.endswith("*"):
        prefix = pattern[:-1].rstrip("/")
        return {
            disk_path
            for disk_path in disk_files
            if disk_path.removeprefix(".local/").startswith(prefix + "/")
            or disk_path.removeprefix(".local/") == prefix
        }
    prefix = pattern.rstrip("/")
    return {
        disk_path
        for disk_path in disk_files
        if disk_path.removeprefix(".local/").startswith(prefix + "/")
        or disk_path.removeprefix(".local/") == prefix
    }


def _is_explicitly_referenced(disk_path: str, references: dict[str, Reference]) -> bool:
    if disk_path in references and not references[disk_path].is_glob:
        return True
    disk_no_prefix = disk_path.removeprefix(".local/")
    for ref_path, ref in references.items():
        if ref.is_glob:
            continue
        ref_no_prefix = ref_path.removeprefix(".local/").rstrip("/")
        if disk_no_prefix == ref_no_prefix:
            return True
        if ref_no_prefix and disk_no_prefix.startswith(ref_no_prefix + "/"):
            return True
    return False


def _is_covered_by_reference(
    disk_path: str,
    references: dict[str, Reference],
    disk_files: set[str],
) -> bool:
    if disk_path in references:
        return True
    disk_no_prefix = disk_path.removeprefix(".local/")
    for ref_path, ref in references.items():
        ref_no_prefix = ref_path.removeprefix(".local/").rstrip("/")
        if ref.is_glob:
            expanded = _expand_glob_reference(ref, disk_files)
            if disk_path in expanded:
                return True
            continue
        if disk_no_prefix == ref_no_prefix:
            return True
        if ref_no_prefix and disk_no_prefix.startswith(ref_no_prefix + "/"):
            return True
    return False


def _print_section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def _format_sources(sources: set[str], limit: int = 3) -> str:
    ordered = sorted(sources)
    if len(ordered) <= limit:
        return ", ".join(ordered)
    head = ", ".join(ordered[:limit])
    return f"{head}, +{len(ordered) - limit} more"


def run_audit(*, show_ok: bool) -> int:
    text_refs = _collect_text_references()
    pages_refs = _collect_pages_json_references()
    merged: dict[str, Reference] = {}
    for bucket in (text_refs, pages_refs):
        for path, ref in bucket.items():
            entry = merged.setdefault(path, Reference(rel_path=path))
            entry.sources.update(ref.sources)
            entry.is_glob = entry.is_glob or ref.is_glob

    disk = _disk_paths()
    disk_files = sorted(p for p in disk if not p.endswith("/") and Path(REPO / p).is_file())

    missing_referenced: list[tuple[str, Reference]] = []
    present_referenced: list[tuple[str, Reference]] = []
    for path, ref in sorted(merged.items()):
        if ref.is_glob:
            expanded = _expand_glob_reference(ref, set(disk_files))
            if expanded:
                present_referenced.append((path, ref))
            else:
                missing_referenced.append((path, ref))
            continue
        if _path_exists(path, disk):
            present_referenced.append((path, ref))
        else:
            missing_referenced.append((path, ref))

    unreferenced: list[str] = []
    glob_only: list[str] = []
    for disk_path in disk_files:
        covered = _is_covered_by_reference(disk_path, merged, set(disk_files))
        if not covered:
            unreferenced.append(disk_path)
            continue
        if not _is_explicitly_referenced(disk_path, merged):
            glob_only.append(disk_path)

    gate_rows: list[tuple[str, str, bool]] = []
    for gate_path, reason in GATE_CRITICAL:
        gate_rows.append((gate_path, reason, _path_exists(gate_path, disk)))

    _print_section("Local workspace dependency audit")
    print(f"Repo: {REPO}")
    print(f".local exists: {LOCAL.is_dir()}")
    print(f"Referenced paths (versioned sources + pages.json): {len(merged)}")
    print(f"On-disk files under .local/: {len(disk_files)}")

    _print_section("Gate-critical paths")
    for gate_path, reason, exists in gate_rows:
        status = "OK" if exists else "MISSING"
        print(f"[{status}] {gate_path}")
        print(f"         {reason}")

    _print_section(f"Referenced but missing ({len(missing_referenced)})")
    if not missing_referenced:
        print("(none)")
    else:
        for path, ref in missing_referenced:
            kind = "glob" if ref.is_glob else "path"
            print(f"- [{kind}] {path}")
            print(f"  sources: {_format_sources(ref.sources)}")

    if show_ok:
        _print_section(f"Referenced and present ({len(present_referenced)})")
        if not present_referenced:
            print("(none)")
        else:
            for path, ref in present_referenced:
                print(f"- {path}")
                print(f"  sources: {_format_sources(ref.sources)}")

    _print_section(f"On disk, not referenced ({len(unreferenced)}) — cleanup candidates")
    if not unreferenced:
        print("(none)")
    else:
        by_dir: dict[str, list[str]] = defaultdict(list)
        for path in unreferenced:
            parent = str(Path(path).parent)
            by_dir[parent].append(path)
        for parent in sorted(by_dir):
            print(f"\n{parent}/")
            for path in sorted(by_dir[parent]):
                print(f"  - {Path(path).name}")

    _print_section(
        f"On disk, glob-only reference ({len(glob_only)}) — weak cleanup candidates"
    )
    if not glob_only:
        print("(none)")
    else:
        by_dir = defaultdict(list)
        for path in glob_only:
            by_dir[str(Path(path).parent)].append(path)
        for parent in sorted(by_dir):
            print(f"\n{parent}/")
            for path in sorted(by_dir[parent]):
                print(f"  - {Path(path).name}")

    missing_gate = [row for row in gate_rows if not row[2]]
    exit_code = 1 if missing_gate else 0
    print()
    if missing_gate:
        print(
            f"Result: {len(missing_gate)} gate-critical path(s) missing "
            f"(expected when PR workflow is idle)."
        )
    else:
        print("Result: all gate-critical paths present.")
    print(
        f"Summary: {len(present_referenced)} referenced+present, "
        f"{len(missing_referenced)} referenced+missing, "
        f"{len(unreferenced)} unreferenced, "
        f"{len(glob_only)} glob-only on disk."
    )
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit `.local/` dependencies: compare versioned references "
            "against files on disk."
        )
    )
    parser.add_argument(
        "--show-ok",
        action="store_true",
        help="Also list referenced paths that exist on disk.",
    )
    parser.add_argument(
        "--strict-gates",
        action="store_true",
        help="Exit 1 when gate-critical paths are missing (default: always 0).",
    )
    args = parser.parse_args()
    code = run_audit(show_ok=args.show_ok)
    if not args.strict_gates:
        return 0
    return code


if __name__ == "__main__":
    sys.exit(main())
