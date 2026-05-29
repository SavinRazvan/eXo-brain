"""
File: test_adapter_factory.py
Path: tests/modules/runtime/test_adapter_factory.py
Role: Regression coverage for adapter class-ref canonicalization and PyPI adapter loading.
Used By:
 - pytest
Depends On:
 - src/runtime/adapter_factory.py
 - exo-adapter-openai, exo-adapter-echo (PyPI)
Notes:
 - Ensures canonical package refs and legacy aliases load from installed wheels.
"""

from __future__ import annotations

import pytest

from tests.adapter_package_paths import local_portable_adapters_present

from src.runtime.adapter_factory import (
    ECHO_ADAPTER_CANONICAL_CLASS_REF,
    OPENAI_ADAPTER_CANONICAL_CLASS_REF,
    canonicalize_adapter_class_ref,
    load_adapter,
)

requires_installed_adapters = pytest.mark.skipif(
    not local_portable_adapters_present(),
    reason="Install adapter packages: pip install -r requirements.txt",
)


def test_load_adapter_accepts_canonical_openai_ref() -> None:
    from exo_adapter_openai.runtime import OpenAIAgentsRuntimeAdapter as PackagedOpenAIAdapter

    adapter = load_adapter(OPENAI_ADAPTER_CANONICAL_CLASS_REF, provider_id="openai-test")
    assert isinstance(adapter, PackagedOpenAIAdapter)
    assert adapter.get_capabilities().provider_id == "openai-test"


@requires_installed_adapters
def test_load_adapter_returns_packaged_openai_class() -> None:
    from exo_adapter_openai.runtime import OpenAIAgentsRuntimeAdapter as PackagedOpenAIAdapter

    adapter = load_adapter(OPENAI_ADAPTER_CANONICAL_CLASS_REF, provider_id="openai-packaged")
    assert isinstance(adapter, PackagedOpenAIAdapter)
    assert adapter.get_capabilities().provider_id == "openai-packaged"


@requires_installed_adapters
def test_load_adapter_returns_packaged_echo_class() -> None:
    from exo_adapter_echo.runtime import EchoRuntimeAdapter as PackagedEchoAdapter

    adapter = load_adapter(ECHO_ADAPTER_CANONICAL_CLASS_REF, provider_id="echo-packaged")
    assert isinstance(adapter, PackagedEchoAdapter)
    assert adapter.get_capabilities().provider_id == "echo-packaged"


def test_load_adapter_accepts_legacy_short_alias() -> None:
    from exo_adapter_openai.runtime import OpenAIAgentsRuntimeAdapter as PackagedOpenAIAdapter

    adapter = load_adapter("OpenAIAgentsRuntimeAdapter", provider_id="openai-test")
    assert isinstance(adapter, PackagedOpenAIAdapter)
    assert adapter.get_capabilities().provider_id == "openai-test"


def test_canonicalize_adapter_class_ref_maps_short_openai_alias() -> None:
    canonical = canonicalize_adapter_class_ref("OpenAIAgentsRuntimeAdapter")
    assert canonical == OPENAI_ADAPTER_CANONICAL_CLASS_REF


def test_canonicalize_adapter_class_ref_maps_echo_alias() -> None:
    assert canonicalize_adapter_class_ref("EchoRuntimeAdapter") == ECHO_ADAPTER_CANONICAL_CLASS_REF


@requires_installed_adapters
def test_load_adapter_accepts_echo_canonical_ref() -> None:
    adapter = load_adapter(ECHO_ADAPTER_CANONICAL_CLASS_REF, provider_id="echo-load-test")
    assert adapter.get_capabilities().provider_id == "echo-load-test"


def test_load_adapter_rejects_non_dotted_unknown_alias() -> None:
    with pytest.raises((ValueError, ImportError)):
        load_adapter("UnknownAdapterAlias", provider_id="p1")
