"""
File: __init__.py
Path: src/agents/__init__.py
Role: Public exports for provider-neutral agent contracts and registry.
Used By:
 - tests/modules/agents/test_agent_registry.py
Depends On:
 - src/agents/contracts.py
 - src/agents/plugin_contract.py
 - src/agents/plugin_manager.py
 - src/agents/registry.py
Notes:
 - Keeps import surface small for consumers in orchestration/routing layers.
"""

from src.agents.contracts import AgentCapabilityTag, AgentSpec, HandoffFallbackPolicy, HandoffRoute
from src.agents.plugin_contract import AgentPlugin, AgentPluginManifest
from src.agents.plugin_manager import AgentPluginManager
from src.agents.registry import AgentRegistry

__all__ = [
    "AgentCapabilityTag",
    "AgentRegistry",
    "AgentPlugin",
    "AgentPluginManager",
    "AgentPluginManifest",
    "AgentSpec",
    "HandoffFallbackPolicy",
    "HandoffRoute",
]
