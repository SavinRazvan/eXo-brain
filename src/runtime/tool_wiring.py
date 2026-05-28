"""
File: tool_wiring.py
Path: src/runtime/tool_wiring.py
Role: Backward-compatible re-export of OpenAI Agents tool wiring from the adapter package.
Used By:
 - tests/modules/runtime/test_tenant_runtime.py
Depends On:
 - exo_adapter_openai.tool_wiring
Notes:
 - Canonical implementation lives in exo-adapter-openai.
"""

from __future__ import annotations

from exo_adapter_openai.tool_wiring import build_agent_tools

__all__ = ["build_agent_tools"]
