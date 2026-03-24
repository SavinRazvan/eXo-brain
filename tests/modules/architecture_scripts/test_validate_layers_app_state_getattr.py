"""
File: test_validate_layers_app_state_getattr.py
Path: tests/modules/architecture_scripts/test_validate_layers_app_state_getattr.py
Role: Unit tests for validate_layers getattr-on-app.state AST guard.
Used By:
 - pytest
Depends On:
 - scripts/architecture/ast_app_state_guard.py
Notes:
 - Imports ast_app_state_guard only (no validate_layers / contracts preload).
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]


def _load_ast_app_state_guard():
    path = _ROOT / "scripts" / "architecture" / "ast_app_state_guard.py"
    spec = importlib.util.spec_from_file_location("_ast_app_state_guard_under_test", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_getattr_guard_detects_application_state_access() -> None:
    mod = _load_ast_app_state_guard()
    tree = ast.parse('getattr(application.state, "session_store", None)\n')
    assert mod.getattr_bypasses_app_state_guard(tree)


def test_getattr_guard_detects_app_state_access() -> None:
    mod = _load_ast_app_state_guard()
    tree = ast.parse('getattr(app.state, "tool_store", None)\n')
    assert mod.getattr_bypasses_app_state_guard(tree)


def test_getattr_guard_detects_request_app_state_access() -> None:
    mod = _load_ast_app_state_guard()
    tree = ast.parse('getattr(request.app.state, "settings", None)\n')
    assert mod.getattr_bypasses_app_state_guard(tree)


def test_getattr_guard_ignores_bound_state_name() -> None:
    mod = _load_ast_app_state_guard()
    tree = ast.parse(
        "st = app.state\n"
        "x = getattr(st, 'tool_store', None)\n",
    )
    assert not mod.getattr_bypasses_app_state_guard(tree)


def test_getattr_guard_ignores_non_state_attribute() -> None:
    mod = _load_ast_app_state_guard()
    tree = ast.parse('getattr(request.url, "path", "")\n')
    assert not mod.getattr_bypasses_app_state_guard(tree)
