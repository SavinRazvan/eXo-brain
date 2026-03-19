"""
File: test_workflow_loader.py
Path: tests/modules/core/test_workflow_loader.py
Role: Unit tests for workflow loader registry behavior and source parsing errors.
Used By:
 - pytest
Depends On:
 - src/core/workflow_loader.py
 - src/schemas/workflow_schema.py
Notes:
 - Validates structured error codes used by higher-level orchestration flows.
"""

from pathlib import Path
from types import ModuleType
import builtins
import sys

from src.core.workflow_loader import WorkflowLoadError, WorkflowLoader
from src.schemas.workflow_schema import WORKFLOW_SCHEMA_VERSION


def _write_valid_workflow(path: Path) -> None:
    path.write_text(
        (
            "{\n"
            f'  "schema_version": "{WORKFLOW_SCHEMA_VERSION}",\n'
            '  "workflow_id": "workflow.sample",\n'
            '  "version": "1.0.0",\n'
            '  "nodes": [\n'
            '    {"node_id": "plan", "agent_role": "planner"}\n'
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )


def test_workflow_loader_loads_and_registers_json_workflow(tmp_path: Path) -> None:
    loader = WorkflowLoader()
    source = tmp_path / "workflow.json"
    _write_valid_workflow(source)

    handle = loader.load_workflow(source)

    assert handle.workflow_id == "workflow.sample"
    assert handle.version == "1.0.0"
    assert loader.get_workflow("workflow.sample", "1.0.0").source == str(source)
    assert len(loader.list_workflows()) == 1


def test_workflow_loader_rejects_invalid_json(tmp_path: Path) -> None:
    loader = WorkflowLoader()
    source = tmp_path / "broken.json"
    source.write_text("{invalid}", encoding="utf-8")

    try:
        loader.load_workflow(source)
        assert False, "Expected WorkflowLoadError for invalid JSON"
    except WorkflowLoadError as exc:
        assert exc.code == "WORKFLOW_JSON_INVALID"


def test_workflow_loader_rejects_unsupported_extension(tmp_path: Path) -> None:
    loader = WorkflowLoader()
    source = tmp_path / "workflow.txt"
    source.write_text("{}", encoding="utf-8")

    try:
        loader.load_workflow(source)
        assert False, "Expected WorkflowLoadError for unsupported extension"
    except WorkflowLoadError as exc:
        assert exc.code == "WORKFLOW_EXTENSION_UNSUPPORTED"


def test_workflow_loader_requires_replace_for_duplicate_registration(tmp_path: Path) -> None:
    loader = WorkflowLoader()
    source = tmp_path / "workflow.json"
    _write_valid_workflow(source)

    loader.load_workflow(source)

    try:
        loader.load_workflow(source)
        assert False, "Expected WorkflowLoadError for duplicate workflow registration"
    except WorkflowLoadError as exc:
        assert exc.code == "WORKFLOW_ALREADY_REGISTERED"

    replaced = loader.load_workflow(source, replace_existing=True)
    assert replaced.workflow_id == "workflow.sample"


def test_workflow_loader_source_and_lookup_guards(tmp_path: Path) -> None:
    loader = WorkflowLoader()
    missing = tmp_path / "missing.json"
    try:
        loader.load_workflow(missing)
    except WorkflowLoadError as exc:
        assert exc.code == "WORKFLOW_SOURCE_NOT_FOUND"
    else:
        raise AssertionError("Expected source not found error")

    try:
        loader.get_workflow("ghost", "0.0.1")
    except WorkflowLoadError as exc:
        assert exc.code == "WORKFLOW_NOT_FOUND"
    else:
        raise AssertionError("Expected workflow not found error")


def test_workflow_loader_reload_wrapper_and_json_payload_type_guard(tmp_path: Path) -> None:
    loader = WorkflowLoader()
    source = tmp_path / "workflow.json"
    _write_valid_workflow(source)
    first = loader.load_workflow(source)
    reloaded = loader.reload_workflow(source)
    assert first.workflow_id == reloaded.workflow_id

    wrong_type = tmp_path / "wrong_type.json"
    wrong_type.write_text("[]", encoding="utf-8")
    try:
        loader.load_workflow(wrong_type)
    except WorkflowLoadError as exc:
        assert exc.code == "WORKFLOW_PAYLOAD_TYPE_INVALID"
    else:
        raise AssertionError("Expected payload type error for non-object JSON")


def test_workflow_loader_yaml_dependency_missing(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "workflow.yaml"
    source.write_text("workflow_id: x", encoding="utf-8")
    loader = WorkflowLoader()

    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "yaml":
            raise ImportError("missing yaml")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)
    try:
        loader.load_workflow(source)
    except WorkflowLoadError as exc:
        assert exc.code == "WORKFLOW_YAML_DEPENDENCY_MISSING"
    else:
        raise AssertionError("Expected YAML dependency error")


def test_workflow_loader_yaml_invalid_type_and_success_paths(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "workflow.yaml"
    source.write_text("workflow_id: x", encoding="utf-8")
    loader = WorkflowLoader()

    fake_yaml = ModuleType("yaml")

    def _raise_yaml(_raw):
        raise ValueError("yaml parse failed")

    fake_yaml.safe_load = _raise_yaml  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "yaml", fake_yaml)
    try:
        loader.load_workflow(source)
    except WorkflowLoadError as exc:
        assert exc.code == "WORKFLOW_YAML_INVALID"
    else:
        raise AssertionError("Expected invalid YAML error")

    fake_yaml.safe_load = lambda _raw: []  # type: ignore[attr-defined]
    try:
        loader.load_workflow(source)
    except WorkflowLoadError as exc:
        assert exc.code == "WORKFLOW_PAYLOAD_TYPE_INVALID"
    else:
        raise AssertionError("Expected payload type error for non-object YAML")

    fake_yaml.safe_load = lambda _raw: {  # type: ignore[attr-defined]
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "workflow_id": "workflow.from_yaml",
        "version": "1.0.0",
        "nodes": [{"node_id": "plan", "agent_role": "planner"}],
    }
    handle = loader.load_workflow(source)
    assert handle.workflow_id == "workflow.from_yaml"
