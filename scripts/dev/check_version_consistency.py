#!/usr/bin/env python3
"""
File: check_version_consistency.py
Path: scripts/dev/check_version_consistency.py
Role: Enforce internal package version consistency across local package manifests.
Used By:
 - maintainers before release commits
 - CI and PR release-gate workflows
Depends On:
 - pathlib
 - re
 - sys
 - tomllib
Notes:
 - Uses `packages/exo-brain-core-contracts/pyproject.toml` as canonical source.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys
import tomllib


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = REPO_ROOT / "packages"
CANONICAL_FILE = PACKAGES_DIR / "exo-brain-core-contracts" / "pyproject.toml"


def _read_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def _project_name_and_version(path: Path) -> tuple[str, str]:
    data = _read_toml(path)
    project = data.get("project")
    if not isinstance(project, dict):
        raise ValueError(f"{path.relative_to(REPO_ROOT)} missing [project] table")

    name = project.get("name")
    version = project.get("version")
    if not isinstance(name, str) or not isinstance(version, str):
        raise ValueError(
            f"{path.relative_to(REPO_ROOT)} missing string `project.name` or `project.version`"
        )
    return name, version


def _all_package_pyprojects() -> list[Path]:
    return sorted(
        path
        for path in PACKAGES_DIR.glob("*/pyproject.toml")
        if path.is_file()
    )


def _dependency_version_spec(dependency: str) -> tuple[str, str | None]:
    match = re.match(r"^([A-Za-z0-9_.-]+)\s*(.*)$", dependency.strip())
    if not match:
        return dependency, None
    dep_name = match.group(1)
    spec = match.group(2).strip() or None
    return dep_name, spec


def main() -> int:
    errors: list[str] = []

    canonical_name, canonical_version = _project_name_and_version(CANONICAL_FILE)
    package_paths = _all_package_pyprojects()
    if not package_paths:
        print("No package manifests found under packages/*/pyproject.toml")
        return 1

    internal_versions: dict[str, str] = {}
    package_dependencies: dict[str, list[str]] = {}
    for path in package_paths:
        name, version = _project_name_and_version(path)
        internal_versions[name] = version
        data = _read_toml(path)
        project = data.get("project", {})
        if not isinstance(project, dict):
            package_dependencies[name] = []
            continue
        deps = project.get("dependencies", [])
        if isinstance(deps, list):
            package_dependencies[name] = [str(item) for item in deps]
        else:
            package_dependencies[name] = []

    for name, version in sorted(internal_versions.items()):
        if version != canonical_version:
            errors.append(
                f"Internal package `{name}` has version `{version}`; expected `{canonical_version}`."
            )

    internal_names = set(internal_versions.keys())
    for package_name, deps in sorted(package_dependencies.items()):
        for dep in deps:
            dep_name, spec = _dependency_version_spec(dep)
            if dep_name not in internal_names:
                continue
            if not spec:
                continue
            if canonical_version not in spec:
                errors.append(
                    f"`{package_name}` depends on `{dep_name}` with spec `{spec}` "
                    f"that does not reference canonical version `{canonical_version}`."
                )

    if errors:
        print("Version consistency check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        "Version consistency check passed: "
        f"{canonical_name}={canonical_version}; "
        f"checked {len(internal_versions)} internal package(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
