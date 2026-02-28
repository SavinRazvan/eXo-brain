"""
File: __init__.py
Path: src/agents/__init__.py
Role: Public exports for provider-neutral agent contracts and registry.
Used By:
 - tests/unit/test_agent_registry.py
Depends On:
 - src/agents/contracts.py
 - src/agents/registry.py
Notes:
 - Keeps import surface small for consumers in orchestration/routing layers.
"""

from src.agents.contracts import AgentCapabilityTag, AgentSpec, HandoffRoute
from src.agents.registry import AgentRegistry

__all__ = [
    "AgentCapabilityTag",
    "AgentRegistry",
    "AgentSpec",
    "HandoffRoute",
]
