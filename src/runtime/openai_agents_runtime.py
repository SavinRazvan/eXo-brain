"""
File: openai_agents_runtime.py
Path: src/runtime/openai_agents_runtime.py
Role: Backward-compatible re-export of the published OpenAI runtime adapter.
Used By:
 - legacy tests and aliases that import src.runtime.openai_agents_runtime
Depends On:
 - exo_adapter_openai.runtime
Notes:
 - Canonical implementation: distribution exo-adapter-openai (SavinRazvan/eXo_adapters).
 - Install adapters via requirements-adapters.txt or install_adapter_dependencies.sh.
"""

from __future__ import annotations

from exo_adapter_openai.runtime import OpenAIAgentsRuntimeAdapter

__all__ = ["OpenAIAgentsRuntimeAdapter"]
