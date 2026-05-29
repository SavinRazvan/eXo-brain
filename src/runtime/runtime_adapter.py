"""
File: runtime_adapter.py
Path: src/runtime/runtime_adapter.py
Role: Re-export published runtime adapter ABC and session handle so control plane and packages share one type identity.
Used By:
 - src/core/orchestrator.py
 - src/runtime/openai_agents_runtime.py
 - src/config/provider_registry.py
Depends On:
 - exo_brain_core_contracts.runtime_adapter
Notes:
 - Canonical ABC: distribution ``exo-brain-core-contracts`` (SavinRazvan/eXo_adapters, PyPI).
 - Stub adapters in ``custom_runtime`` / ``openai_compatible_runtime`` subclass this symbol;
   production OpenAI/echo adapters load from PyPI via ``adapter_factory``.
"""

from __future__ import annotations

from exo_brain_core_contracts.runtime_adapter import RuntimeAdapter, SessionHandle

__all__ = ["RuntimeAdapter", "SessionHandle"]
