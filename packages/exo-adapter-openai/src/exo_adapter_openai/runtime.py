"""
File: runtime.py
Path: packages/exo-adapter-openai/src/exo_adapter_openai/runtime.py
Role: Provider package wrapper exposing OpenAI runtime adapter entrypoint.
Used By:
 - dynamic adapter loaders
Depends On:
 - src/runtime/openai_agents_runtime.py
Notes:
 - Wrapper class keeps provider package API stable while monorepo internals evolve.
"""

from __future__ import annotations

from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter as _MonorepoOpenAIAdapter


class OpenAIAgentsRuntimeAdapter(_MonorepoOpenAIAdapter):
    """Package-level adapter entrypoint."""


def load_adapter() -> OpenAIAgentsRuntimeAdapter:
    """Factory entrypoint used by dynamic adapter loading."""
    return OpenAIAgentsRuntimeAdapter()
