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
 - When ``packages/*/src`` is on ``sys.path``, the factory must prefer the portable OpenAI adapter
   over the in-tree fallback (STP-W4-001 / adapter handoff §5.1).
"""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.adapter_package_paths import local_portable_adapters_present, package_src

from src.runtime.adapter_factory import (
    ECHO_ADAPTER_CANONICAL_CLASS_REF,
    OPENAI_ADAPTER_CANONICAL_CLASS_REF,
    canonicalize_adapter_class_ref,
    load_adapter,
)
from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter

_REPO_ROOT = Path(__file__).resolve().parents[3]

requires_local_adapter_packages = pytest.mark.skipif(
    not local_portable_adapters_present(),
    reason="Packaged OpenAI/echo adapters are developed in eXo_adapters; add local packages/ workspace to run this assertion.",
)


@contextlib.contextmanager
def _package_src_paths_first() -> Iterator[None]:
    """Prepend adapter package ``src`` trees so imports resolve like editable installs."""
    inserts = [
        package_src("exo-adapter-openai"),
        package_src("exo-adapter-echo"),
        package_src("exo-brain-adapter-sdk"),
        package_src("exo-brain-core-contracts"),
    ]
    saved = sys.path.copy()
    try:
        for p in inserts:
            sys.path.insert(0, str(p))
        yield
    finally:
        sys.path[:] = saved


def test_load_adapter_accepts_canonical_openai_ref() -> None:
    adapter = load_adapter(OPENAI_ADAPTER_CANONICAL_CLASS_REF, provider_id="openai-test")
    try:
        from exo_adapter_openai.runtime import OpenAIAgentsRuntimeAdapter as PackagedOpenAIAdapter
    except ImportError:
        assert isinstance(adapter, OpenAIAgentsRuntimeAdapter)
    else:
        if isinstance(adapter, PackagedOpenAIAdapter):
            assert adapter.get_capabilities().provider_id == "openai-test"
        else:
            assert isinstance(adapter, OpenAIAgentsRuntimeAdapter)


@requires_local_adapter_packages
def test_load_adapter_prefers_packaged_openai_when_on_path() -> None:
    with _package_src_paths_first():
        from exo_adapter_openai.runtime import OpenAIAgentsRuntimeAdapter as PackagedOpenAIAdapter

        adapter = load_adapter(OPENAI_ADAPTER_CANONICAL_CLASS_REF, provider_id="openai-packaged")
        assert isinstance(adapter, PackagedOpenAIAdapter)
        assert adapter.get_capabilities().provider_id == "openai-packaged"


@requires_local_adapter_packages
def test_load_adapter_prefers_packaged_echo_when_on_path() -> None:
    with _package_src_paths_first():
        from exo_adapter_echo.runtime import EchoRuntimeAdapter as PackagedEchoAdapter

        adapter = load_adapter(ECHO_ADAPTER_CANONICAL_CLASS_REF, provider_id="echo-packaged")
        assert isinstance(adapter, PackagedEchoAdapter)
        assert adapter.get_capabilities().provider_id == "echo-packaged"


def test_load_adapter_accepts_legacy_short_alias() -> None:
    adapter = load_adapter("OpenAIAgentsRuntimeAdapter", provider_id="openai-test")
    try:
        from exo_adapter_openai.runtime import OpenAIAgentsRuntimeAdapter as PackagedOpenAIAdapter
    except ImportError:
        assert isinstance(adapter, OpenAIAgentsRuntimeAdapter)
    else:
        if isinstance(adapter, PackagedOpenAIAdapter):
            assert adapter.get_capabilities().provider_id == "openai-test"
        else:
            assert isinstance(adapter, OpenAIAgentsRuntimeAdapter)


def test_canonicalize_adapter_class_ref_maps_short_openai_alias() -> None:
    canonical = canonicalize_adapter_class_ref("OpenAIAgentsRuntimeAdapter")
    assert canonical == OPENAI_ADAPTER_CANONICAL_CLASS_REF


def test_canonicalize_adapter_class_ref_maps_echo_alias() -> None:
    assert canonicalize_adapter_class_ref("EchoRuntimeAdapter") == ECHO_ADAPTER_CANONICAL_CLASS_REF


def test_load_adapter_accepts_echo_canonical_or_fallback() -> None:
    adapter = load_adapter(ECHO_ADAPTER_CANONICAL_CLASS_REF, provider_id="echo-load-test")
    assert adapter.get_capabilities().provider_id == "echo-load-test"


def test_load_adapter_rejects_non_dotted_unknown_alias() -> None:
    with pytest.raises((ValueError, ImportError)):
        load_adapter("UnknownAdapterAlias", provider_id="p1")
