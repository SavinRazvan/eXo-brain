"""
File: user_tools.py
Path: src/tools/user_tools.py
Role: Canonical module for tenant-facing tool handlers referenced by default UI conventions.
Used By:
 - ui/src/screens/tools.ts
 - src/api/routers/tools.py
Depends On:
 - os
Notes:
 - Standard handler_ref format for dashboard-created tools is `src.tools.user_tools:<tool_name>`.
 - Keep handlers deterministic and side-effect aware for policy middleware compatibility.
"""

from __future__ import annotations

import os
from typing import Any


def calculate_result(
    operation: str,
    operand1: float,
    operand2: float,
    operand3: float | None = None,
) -> dict[str, Any]:
    """Reference arithmetic tool with optional server-side secret operand.

    This function is provided as a starter implementation for dashboard users.
    """
    secret_operand = float(operand3) if operand3 is not None else float(os.environ.get("EXO_SECRET_OPERAND", "0"))
    op = operation.strip().lower()

    if op == "add":
        result = operand1 + operand2 + secret_operand
    elif op == "subtract":
        result = operand1 - operand2 - secret_operand
    elif op == "multiply":
        result = operand1 * operand2 * (secret_operand if secret_operand != 0 else 1.0)
    elif op == "divide":
        divisor = operand2 if secret_operand == 0 else operand2 * secret_operand
        if divisor == 0:
            raise ValueError("Division by zero is not allowed.")
        result = operand1 / divisor
    else:
        raise ValueError(f"Unsupported operation: {operation}")

    return {
        "operation": op,
        "operand1": operand1,
        "operand2": operand2,
        "operand3": secret_operand,
        "result": result,
    }
