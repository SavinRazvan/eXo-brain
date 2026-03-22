"""
File: test_artifact_store.py
Path: tests/modules/tools/test_artifact_store.py
Role: Unit tests for tool artifact hashing and signing helpers.
Used By:
 - pytest
Depends On:
 - src/tools/artifact_store.py
Notes:
 - Covers signing secret validation used by upload integrity checks.
"""

from __future__ import annotations

import pytest

from src.tools.artifact_store import sign_bundle_hash


def test_sign_bundle_hash_rejects_blank_secret() -> None:
    with pytest.raises(ValueError, match="signing secret"):
        sign_bundle_hash("abc", "   ")
