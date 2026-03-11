"""
File: tool_wiring.py
Path: packages/exo-adapter-openai/src/exo_adapter_openai/tool_wiring.py
Role: Provider package export for OpenAI tool wrapper wiring.
Used By:
 - provider package consumers
Depends On:
 - src/runtime/tool_wiring.py
Notes:
 - Re-export module keeps stable import path for external consumers.
"""

from src.runtime.tool_wiring import build_agent_tools

__all__ = ["build_agent_tools"]
