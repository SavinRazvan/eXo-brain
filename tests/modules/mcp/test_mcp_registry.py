"""
File: test_mcp_registry.py
Path: tests/modules/mcp/test_mcp_registry.py
Role: Unit tests for MCP registry server health and availability controls.
Used By:
 - pytest
Depends On:
 - src/mcp/mcp_registry.py
Notes:
 - Verifies per-server health state influences MCP availability checks.
"""

import pytest

from src.mcp.mcp_registry import McpHealthState, McpRegistry, McpServerRecord, McpTrustTier


def test_list_servers_and_server_health_maps_are_sorted() -> None:
    registry = McpRegistry()
    registry.register_server(
        McpServerRecord(server_id="b", endpoint="local://b", trust_tier=McpTrustTier.TRUSTED)
    )
    registry.register_server(
        McpServerRecord(server_id="a", endpoint="local://a", trust_tier=McpTrustTier.TRUSTED)
    )
    assert registry.list_servers() == ["a", "b"]
    health_map = registry.list_server_health()
    assert list(health_map.keys()) == ["a", "b"]


def test_registry_tracks_server_health_state() -> None:
    registry = McpRegistry()
    registry.register_server(
        McpServerRecord(
            server_id="mcp_health",
            endpoint="local://mcp-health",
            trust_tier=McpTrustTier.TRUSTED,
        )
    )
    assert registry.get_server_health("mcp_health").state == McpHealthState.HEALTHY
    registry.set_server_health("mcp_health", McpHealthState.DEGRADED, reason="latency spike")
    health = registry.get_server_health("mcp_health")
    assert health.state == McpHealthState.DEGRADED
    assert health.reason == "latency spike"


def test_get_server_raises_keyerror_when_missing() -> None:
    registry = McpRegistry()
    with pytest.raises(KeyError, match="not registered"):
        registry.get_server("missing")


def test_get_server_raises_when_disabled() -> None:
    registry = McpRegistry()
    registry.register_server(
        McpServerRecord(
            server_id="off",
            endpoint="local://off",
            trust_tier=McpTrustTier.TRUSTED,
            enabled=False,
        )
    )
    with pytest.raises(ValueError, match="disabled"):
        registry.get_server("off")


def test_set_server_health_requires_registration() -> None:
    registry = McpRegistry()
    with pytest.raises(KeyError, match="not registered"):
        registry.set_server_health("x", McpHealthState.HEALTHY)


def test_get_server_health_requires_registration() -> None:
    registry = McpRegistry()
    with pytest.raises(KeyError, match="not registered"):
        registry.get_server_health("x")


def test_registry_blocks_unavailable_server_access() -> None:
    registry = McpRegistry()
    registry.register_server(
        McpServerRecord(
            server_id="mcp_unavailable",
            endpoint="local://mcp-unavailable",
            trust_tier=McpTrustTier.TRUSTED,
        )
    )
    registry.set_server_health("mcp_unavailable", McpHealthState.UNAVAILABLE, reason="outage")
    try:
        registry.get_server("mcp_unavailable")
    except ValueError as exc:
        assert "unavailable" in str(exc)
        assert "outage" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected unavailable server lookup to fail")
