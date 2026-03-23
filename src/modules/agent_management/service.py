"""
File: service.py
Path: src/modules/agent_management/service.py
Role: Public module facade for agent persistence ownership.
Used By:
 - src/modules/platform_bootstrap/service.py
Depends On:
 - src/persistence/contracts.py
Notes:
 - Agent runtime composition still happens in the session-runtime module.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.persistence.contracts import AgentStore


@dataclass(slots=True)
class AgentManagementModule:
    agent_store: AgentStore | None
