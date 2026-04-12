"""
File: events.py
Path: src/schemas/events.py
Role: Re-export published runtime event contracts for control-plane parity with adapter packages.
Used By:
 - src/runtime/openai_agents_runtime.py
 - src/core/orchestrator.py
Depends On:
 - exo_brain_core_contracts.events
Notes:
 - Canonical types: distribution ``exo-brain-core-contracts`` (authored in **eXo_adapters**, installed via pip). Factory methods live on ``RuntimeEvent`` in that package.
"""

from __future__ import annotations

from exo_brain_core_contracts.events import RuntimeEvent, RuntimeEventType

__all__ = ["RuntimeEvent", "RuntimeEventType"]
