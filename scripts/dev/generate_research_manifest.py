"""
File: generate_research_manifest.py
Path: scripts/dev/generate_research_manifest.py
Role: Generate _research_results/manifests/*.md from git ls-files, headers, imports, module map.
Used By:
 - Research Phase 1 (_research_results/manifests/)
Depends On:
 - ast
 - pathlib
 - subprocess
 - src.modules.contracts
Notes:
 - Does not modify source code. Re-run after repo file changes.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_RESEARCH = ROOT / "_research_results" / "manifests"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.contracts import module_name_for_path  # noqa: E402

HEADER_KEYS = ("File:", "Path:", "Role:", "Used By:", "Depends On:", "Notes:")
SKIP_PREFIXES = (
    ".venv/",
    ".exo_data/",
    ".coverage",
    ".git/",
    ".local/",
    "_research_results/manifests/",
)


@dataclass
class FileRow:
    path: str
    module: str
    role: str
    depends_on: str
    used_by_header: str
    imports_inferred: str
    evidence: str
    area: str
    ext: str

    def file_id(self) -> str:
        mod = self.module.replace("_", "-") if self.module != "legacy-unmapped" else "unmapped"
        base = Path(self.path).stem.replace(".", "-")[:40]
        return f"FILE-{mod}-{base}"


def git_ls_files() -> list[str]:
    out = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files"],
        text=True,
    )
    return [line.strip() for line in out.splitlines() if line.strip()]


def parse_header_block(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        matched_key = None
        for key in HEADER_KEYS:
            if stripped.startswith(key):
                if current_key is not None:
                    result[current_key] = "\n".join(current_lines).strip()
                current_key = key.rstrip(":")
                current_lines = [stripped[len(key) :].strip()]
                matched_key = key
                break
        if matched_key is None and current_key is not None:
            if stripped.startswith("- "):
                current_lines.append(stripped)
            elif stripped and not stripped.startswith('"""') and not stripped.startswith("'''"):
                current_lines.append(stripped)
    if current_key is not None:
        result[current_key] = "\n".join(current_lines).strip()
    return result


def first_docstring_line(text: str) -> str:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ""
    doc = ast.get_docstring(tree)
    if not doc:
        return ""
    first = doc.strip().splitlines()[0].strip()
    return first[:200] if first else ""


def extract_imports(path: Path, text: str) -> list[str]:
    if path.suffix != ".py":
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return sorted(set(imports))[:12]


def classify_area(path: str) -> str:
    if path.startswith("src/"):
        return "src"
    if path.startswith("docs/"):
        return "docs"
    if path.startswith("tests/"):
        return "tests"
    if path.startswith("scripts/") or path.startswith(".github/"):
        return "scripts-ci"
    if path.startswith("packages/") or path.startswith("notebooks/"):
        return "packages-notebooks"
    return "root-config"


def build_rows(paths: list[str]) -> list[FileRow]:
    rows: list[FileRow] = []
    for rel in paths:
        if any(rel.startswith(p) for p in SKIP_PREFIXES):
            continue
        area = classify_area(rel)
        full = ROOT / rel
        if not full.is_file():
            continue
        mod = module_name_for_path(rel) or "legacy-unmapped"
        role = ""
        depends = ""
        used_by_h = ""
        evidence = "inferred"
        text = ""
        try:
            text = full.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        if rel.endswith((".py", ".md")):
            header = parse_header_block(text[:4000])
            role = header.get("Role", "").strip()
            depends = header.get("Depends On", "").strip().replace("\n", "; ")
            used_by_h = header.get("Used By", "").strip().replace("\n", "; ")
            if role or depends:
                evidence = "verified" if role else "inferred"
        if not role and rel.endswith(".py"):
            role = first_docstring_line(text)
        if not role:
            role = "TBD"
        imports = extract_imports(full, text) if rel.endswith(".py") else []
        imp_str = ", ".join(imports[:8]) if imports else ""
        if imp_str and not depends:
            depends = imp_str
        rows.append(
            FileRow(
                path=rel,
                module=mod,
                role=role[:180],
                depends_on=depends[:200] if depends else imp_str[:200],
                used_by_header=used_by_h[:200],
                imports_inferred=imp_str,
                evidence=evidence,
                area=area,
                ext=full.suffix,
            )
        )
    return rows


def reverse_used_by(rows: list[FileRow]) -> dict[str, list[str]]:
    rev: dict[str, list[str]] = defaultdict(list)
    path_set = {r.path for r in rows}
    for row in rows:
        if not row.path.endswith(".py"):
            continue
        full = ROOT / row.path
        try:
            text = full.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(text)
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                mod_path = node.module.replace(".", "/")
                for candidate in path_set:
                    if candidate.endswith(".py") and mod_path in candidate.replace("/", "."):
                        rev[candidate].append(row.path)
    return rev


def md_table(rows: list[FileRow], used_by_map: dict[str, list[str]], light: bool = False) -> str:
    lines = [
        "| ID | Path | Module | Role | Depends on | Used by | Workflows | Ideas | Pros | Cons | RefactorNotes | Evidence | Owner |",
        "|----|------|--------|------|------------|---------|-----------|-------|------|------|---------------|----------|-------|",
    ]
    for r in sorted(rows, key=lambda x: (x.module, x.path)):
        ub = used_by_map.get(r.path, [])
        if r.used_by_header:
            ub_text = r.used_by_header[:80]
        elif ub:
            ub_text = "; ".join(ub[:3]) + ("…" if len(ub) > 3 else "")
        else:
            ub_text = "TBD"
        owner = _owner_synthesis(r)
        if light:
            lines.append(
                f"| {r.file_id()} | `{r.path}` | {r.module} | {r.role[:60]} | | {ub_text[:40]} | | | | | | | {r.evidence} | {owner} |"
            )
        else:
            lines.append(
                f"| {r.file_id()} | `{r.path}` | {r.module} | {r.role[:50]} | {r.depends_on[:40]} | {ub_text[:40]} | TBD | TBD | TBD | TBD | TBD | {r.evidence} | {owner} |"
            )
    return "\n".join(lines) + "\n"


def _owner_synthesis(row: FileRow) -> str:
    mod = row.module
    if mod == "tenant_governance" or row.path.startswith("src/policies/"):
        return "03"
    if mod == "turn_execution":
        return "03,05"
    if row.path.startswith("src/api/"):
        return "06"
    if row.path.startswith("docs/"):
        return "08"
    if row.path.startswith("tests/"):
        return "evidence"
    if row.path.startswith((".cursor", ".agents", "scripts/pr")) or row.path.startswith(".github/"):
        return "07"
    if mod in ("platform_bootstrap", "shared_kernel", "adapter_contracts"):
        return "04"
    if mod == "audit_observability":
        return "03,07"
    return "04,05"


def write_shard(name: str, title: str, body: str, count: int) -> None:
    _RESEARCH.mkdir(parents=True, exist_ok=True)
    path = _RESEARCH / name
    header = f"""# {title}

<!--
Generated by scripts/dev/generate_research_manifest.py
Generated at: {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
Row count: {count}
-->

"""
    path.write_text(header + body, encoding="utf-8")


def main() -> int:
    paths = git_ls_files()
    rows = build_rows(paths)
    used_by_map = reverse_used_by(rows)

    by_area: dict[str, list[FileRow]] = defaultdict(list)
    for r in rows:
        by_area[r.area].append(r)

    src_rows = by_area.get("src", [])
    by_mod: dict[str, list[FileRow]] = defaultdict(list)
    for r in src_rows:
        by_mod[r.module].append(r)

    src_parts = ["# Source files by module\n"]
    for mod in sorted(by_mod.keys()):
        mod_rows = by_mod[mod]
        src_parts.append(f"\n## MOD-{mod} ({len(mod_rows)} files)\n\n")
        src_parts.append(md_table(mod_rows, used_by_map))
    write_shard("src-by-module.md", "Source manifest by module", "".join(src_parts), len(src_rows))

    for area, fname, title in [
        ("docs", "docs.md", "Documentation manifest"),
        ("tests", "tests.md", "Tests manifest"),
        ("scripts-ci", "scripts-and-ci.md", "Scripts and CI manifest"),
        ("packages-notebooks", "packages-and-notebooks.md", "Packages and notebooks manifest"),
        ("root-config", "root-and-config.md", "Root and config manifest"),
    ]:
        area_rows = by_area.get(area, [])
        light = area in ("tests", "root-config", "scripts-ci")
        body = md_table(area_rows, used_by_map, light=light)
        write_shard(fname, title, body, len(area_rows))

    meta = _RESEARCH / "_meta.json"
    meta.write_text(
        f'{{"generated_at":"{datetime.now(timezone.utc).isoformat()}","total_rows":{len(rows)},"git_files":{len(paths)}}}\n',
        encoding="utf-8",
    )
    print(f"Generated {len(rows)} rows into {_RESEARCH}")
    for area, lst in sorted(by_area.items()):
        print(f"  {area}: {len(lst)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
