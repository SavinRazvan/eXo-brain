"""
File: test_user_tools.py
Path: tests/modules/tools/test_user_tools.py
Role: Unit tests for canonical tenant-facing handlers in src.tools.user_tools.
Used By:
 - pytest
Depends On:
 - src/tools/user_tools.py
Notes:
 - Keeps default dashboard handler path behavior stable.
"""

from __future__ import annotations

import pytest

from src.tools.user_tools import calculate_result


def test_calculate_result_add() -> None:
    out = calculate_result("add", 2, 3, 5)
    assert out["result"] == 10


def test_calculate_result_divide_with_secret() -> None:
    out = calculate_result("divide", 100, 4, 5)
    assert out["result"] == 5


def test_calculate_result_invalid_operation_raises() -> None:
    with pytest.raises(ValueError):
        calculate_result("pow", 2, 3, 1)
