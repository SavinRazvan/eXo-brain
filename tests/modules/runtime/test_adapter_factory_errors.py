"""
File: test_adapter_factory_errors.py
Path: tests/modules/runtime/test_adapter_factory_errors.py
Role: Negative-path coverage for adapter_factory helper functions.
Used By:
 - pytest
Depends On:
 - src/runtime/adapter_factory.py
Notes:
 - Targets validation branches not exercised by happy-path OpenAI loading.
"""

from __future__ import annotations

import pytest

from src.runtime import adapter_factory as adapter_factory_module
from src.runtime.adapter_factory import canonicalize_adapter_class_ref, load_adapter


def test_canonicalize_rejects_empty_adapter_ref() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        canonicalize_adapter_class_ref("   ")


def test_load_adapter_class_rejects_non_runtime_adapter_subclass() -> None:
    with pytest.raises(ValueError, match="RuntimeAdapter"):
        adapter_factory_module._load_adapter_class("builtins.str")


def test_load_adapter_surfaces_last_error_when_all_candidates_fail() -> None:
    with pytest.raises(ImportError, match="Could not load adapter"):
        load_adapter("this.module.does_not_exist_ever.AdapterX", provider_id="p")


def test_load_adapter_class_missing_symbol_raises() -> None:
    with pytest.raises(ValueError, match="not found"):
        adapter_factory_module._load_adapter_class("json.not_a_real_decoder_class_name")
