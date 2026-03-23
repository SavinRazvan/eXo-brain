"""
File: test_provider_management_service.py
Path: tests/modules/provider_management/test_provider_management_service.py
Role: Unit tests for small provider-management service error branches.
Used By:
 - pytest
Depends On:
 - src/modules/provider_management/service.py
Notes:
 - Focuses on error formatting and api_type validation branches.
"""

from __future__ import annotations

import pytest

from src.modules.identity_access.service import IdentityAccessService
from src.modules.provider_management.service import ProviderManagementError, ProviderManagementService


def test_provider_management_error_str_returns_detail() -> None:
    assert str(ProviderManagementError(status_code=422, detail="bad-provider")) == "bad-provider"


def test_parse_api_type_rejects_blank_and_invalid_values() -> None:
    service = ProviderManagementService(
        registry=None,  # type: ignore[arg-type]
        store=None,
        identity_access=IdentityAccessService(api_key_store=None),
    )

    with pytest.raises(ProviderManagementError, match="api_type is required"):
        service._parse_api_type("")
    with pytest.raises(ProviderManagementError, match="Unsupported api_type 'bogus'"):
        service._parse_api_type("bogus")
