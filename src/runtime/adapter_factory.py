"""
File: adapter_factory.py
Path: src/runtime/adapter_factory.py
Role: Load a RuntimeAdapter by dotted class reference using importlib.
Used By:
 - src/api/routers/providers.py
 - src/api/startup.py
Depends On:
 - importlib
 - src/runtime/runtime_adapter.py
Notes:
 - Validates the loaded class with ``issubclass(..., RuntimeAdapter)`` where ``RuntimeAdapter`` is the
   published ABC re-exported from ``src.runtime.runtime_adapter`` (same type as adapter packages).
 - Canonical OpenAI ref: "exo_adapter_openai.runtime.OpenAIAgentsRuntimeAdapter"
 - Requires published adapter wheels (see requirements.txt).
"""

from __future__ import annotations

import importlib
import logging
from src.runtime.runtime_adapter import RuntimeAdapter

logger = logging.getLogger(__name__)

OPENAI_ADAPTER_CANONICAL_CLASS_REF = "exo_adapter_openai.runtime.OpenAIAgentsRuntimeAdapter"
ECHO_ADAPTER_CANONICAL_CLASS_REF = "exo_adapter_echo.runtime.EchoRuntimeAdapter"

_OPENAI_ADAPTER_CLASS_REF_ALIASES = frozenset(
    {
        "OpenAIAgentsRuntimeAdapter",
        "exo_adapter_openai.OpenAIAgentsRuntimeAdapter",
        OPENAI_ADAPTER_CANONICAL_CLASS_REF,
    }
)

_ECHO_ADAPTER_CLASS_REF_ALIASES = frozenset(
    {
        "EchoRuntimeAdapter",
        ECHO_ADAPTER_CANONICAL_CLASS_REF,
    }
)


def canonicalize_adapter_class_ref(adapter_class_ref: str) -> str:
    """Return canonical class ref for known adapter aliases."""
    ref = adapter_class_ref.strip()
    if not ref:
        raise ValueError("adapter_class_ref cannot be empty")
    if ref in _ECHO_ADAPTER_CLASS_REF_ALIASES:
        return ECHO_ADAPTER_CANONICAL_CLASS_REF
    if ref in _OPENAI_ADAPTER_CLASS_REF_ALIASES:
        return OPENAI_ADAPTER_CANONICAL_CLASS_REF
    return ref


def _load_adapter_class(ref: str) -> type[RuntimeAdapter]:
    if "." not in ref:
        raise ValueError(f"adapter_class_ref must be a dotted path, got: {ref!r}")

    module_path, class_name = ref.rsplit(".", 1)
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name, None)
    if cls is None:
        raise ValueError(f"Class {class_name!r} not found in {module_path!r}")

    if not isinstance(cls, type) or not issubclass(cls, RuntimeAdapter):
        raise ValueError(f"{ref!r} must be a RuntimeAdapter subclass, got {type(cls).__name__}")
    return cls


def load_adapter(adapter_class_ref: str, provider_id: str, **kwargs) -> RuntimeAdapter:
    """Load a RuntimeAdapter by dotted class reference.

    Args:
        adapter_class_ref: Fully qualified class path or known alias. Canonical OpenAI ref:
            "exo_adapter_openai.runtime.OpenAIAgentsRuntimeAdapter"
        provider_id: Provider ID to pass to the adapter constructor.
        **kwargs: Additional constructor arguments (e.g. tool_registry, tool_executor).

    Returns:
        Instantiated RuntimeAdapter.

    Raises:
        ValueError: If the ref is malformed or the class is not a RuntimeAdapter.
        ImportError: If the module or class cannot be loaded (install requirements-adapters.txt).
    """
    canonical_ref = canonicalize_adapter_class_ref(adapter_class_ref)
    try:
        cls = _load_adapter_class(canonical_ref)
    except (ImportError, ValueError) as exc:
        raise ImportError(
            f"Could not load adapter class for {adapter_class_ref!r} "
            f"(canonical={canonical_ref!r}). Install adapter packages: "
            "pip install -r requirements.txt "
            "or bash scripts/dev/install_adapter_dependencies.sh"
        ) from exc
    return cls(provider_id=provider_id, **kwargs)  # type: ignore[call-arg]
