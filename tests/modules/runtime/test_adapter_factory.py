"""
File: test_adapter_factory.py
Path: tests/modules/runtime/test_adapter_factory.py
Role: Regression coverage for adapter class-ref canonicalization and legacy compatibility.
Used By:
 - pytest
Depends On:
 - src/runtime/adapter_factory.py
 - src/runtime/openai_agents_runtime.py
Notes:
 - Ensures canonical package refs and legacy aliases continue to load in monorepo runtime.
"""

from __future__ import annotations

import pytest

from src.runtime.adapter_factory import (
    ECHO_ADAPTER_CANONICAL_CLASS_REF,
    OPENAI_ADAPTER_CANONICAL_CLASS_REF,
    canonicalize_adapter_class_ref,
    load_adapter,
)
from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter


def test_load_adapter_accepts_canonical_openai_ref() -> None:
    adapter = load_adapter(OPENAI_ADAPTER_CANONICAL_CLASS_REF, provider_id="openai-test")
    assert isinstance(adapter, OpenAIAgentsRuntimeAdapter)


def test_load_adapter_accepts_legacy_short_alias() -> None:
    adapter = load_adapter("OpenAIAgentsRuntimeAdapter", provider_id="openai-test")
    assert isinstance(adapter, OpenAIAgentsRuntimeAdapter)


def test_canonicalize_adapter_class_ref_maps_legacy_to_canonical() -> None:
    canonical = canonicalize_adapter_class_ref("src.runtime.openai_agents_runtime.OpenAIAgentsRuntimeAdapter")
    assert canonical == OPENAI_ADAPTER_CANONICAL_CLASS_REF


def test_canonicalize_adapter_class_ref_maps_echo_alias() -> None:
    assert canonicalize_adapter_class_ref("EchoRuntimeAdapter") == ECHO_ADAPTER_CANONICAL_CLASS_REF


def test_load_adapter_accepts_echo_canonical_or_fallback() -> None:
    adapter = load_adapter(ECHO_ADAPTER_CANONICAL_CLASS_REF, provider_id="echo-load-test")
    assert adapter.get_capabilities().provider_id == "echo-load-test"


def test_load_adapter_rejects_non_dotted_unknown_alias() -> None:
    with pytest.raises((ValueError, ImportError)):
        load_adapter("UnknownAdapterAlias", provider_id="p1")
