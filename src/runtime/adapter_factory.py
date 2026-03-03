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
 - Validates the loaded class inherits RuntimeAdapter before instantiation.
 - Typical ref: "src.runtime.openai_agents_runtime.OpenAIAgentsRuntimeAdapter"
"""

from __future__ import annotations

import importlib
import logging

from src.runtime.runtime_adapter import RuntimeAdapter

logger = logging.getLogger(__name__)


def load_adapter(adapter_class_ref: str, provider_id: str, **kwargs) -> RuntimeAdapter:
    """Load a RuntimeAdapter by dotted class reference.

    Args:
        adapter_class_ref: Fully qualified class path, e.g.
            "src.runtime.openai_agents_runtime.OpenAIAgentsRuntimeAdapter"
        provider_id: Provider ID to pass to the adapter constructor.
        **kwargs: Additional constructor arguments (e.g. tool_registry, tool_executor).

    Returns:
        Instantiated RuntimeAdapter.

    Raises:
        ValueError: If the ref is malformed or the class is not a RuntimeAdapter.
        ImportError: If the module or class cannot be loaded.
    """
    ref = adapter_class_ref.strip()
    if not ref:
        raise ValueError("adapter_class_ref cannot be empty")

    if "." not in ref:
        raise ValueError(f"adapter_class_ref must be a dotted path, got: {ref!r}")

    module_path, class_name = ref.rsplit(".", 1)
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name, None)
    if cls is None:
        raise ValueError(f"Class {class_name!r} not found in {module_path!r}")

    if not isinstance(cls, type) or not issubclass(cls, RuntimeAdapter):
        raise ValueError(
            f"{adapter_class_ref!r} must be a RuntimeAdapter subclass, got {type(cls).__name__}"
        )

    return cls(provider_id=provider_id, **kwargs)
