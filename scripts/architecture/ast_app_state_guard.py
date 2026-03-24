"""
File: ast_app_state_guard.py
Path: scripts/architecture/ast_app_state_guard.py
Role: Pure AST helpers for detecting app.state access patterns in validate_layers.
Used By:
 - scripts/architecture/validate_layers.py
 - tests/modules/unknown/test_validate_layers_app_state_getattr.py
Depends On:
 - ast
Notes:
 - No imports from src/* — safe to import from tests without skewing coverage of src.modules.contracts.
"""

from __future__ import annotations

import ast


def attribute_chain(node: ast.AST) -> list[str]:
    chain: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        chain.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        chain.append(current.id)
    chain.reverse()
    return chain


def has_direct_app_state_access(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        chain = attribute_chain(node)
        if chain[:2] == ["app", "state"]:
            return True
        if chain[:3] in (["request", "app", "state"], ["websocket", "app", "state"]):
            return True
    return False


def _getattr_first_arg_is_app_state(expr: ast.AST) -> bool:
    if not isinstance(expr, ast.Attribute):
        return False
    chain = attribute_chain(expr)
    if len(chain) < 2:
        return False
    if chain[-1] != "state":
        return False
    return chain[-2] in ("app", "application")


def getattr_bypasses_app_state_guard(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Name) or func.id != "getattr":
            continue
        if not node.args:
            continue
        if _getattr_first_arg_is_app_state(node.args[0]):
            return True
    return False
