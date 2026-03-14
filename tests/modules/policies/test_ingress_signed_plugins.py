"""
File: test_ingress_signed_plugins.py
Path: tests/modules/policies/test_ingress_signed_plugins.py
Role: Unit tests for signed ingress plugin resolution and lifecycle transition guards.
Used By:
 - pytest
Depends On:
 - src/policies/ingress_signed_plugins.py
Notes:
 - Verifies deterministic signature/compatibility/sandbox validation and transition safety checks.
"""

from __future__ import annotations

import pytest

from src.policies.ingress_signed_plugins import (
    classify_signed_plugin_lifecycle_transition,
    list_signed_ingress_plugins,
    resolve_optional_signed_ingress_plugin,
    resolve_signed_ingress_plugin,
)


def test_list_signed_ingress_plugins_exposes_known_refs() -> None:
    refs = list_signed_ingress_plugins()
    assert "plugin://trusted/signed-v1" in refs
    assert "plugin://trusted/signed-v2" in refs


def test_resolve_optional_signed_ingress_plugin_returns_none_for_empty_ref() -> None:
    assert resolve_optional_signed_ingress_plugin("") is None
    assert resolve_optional_signed_ingress_plugin(None) is None


def test_resolve_signed_ingress_plugin_returns_validated_plugin() -> None:
    plugin = resolve_signed_ingress_plugin("plugin://trusted/signed-v1")
    assert plugin.manifest.plugin_ref == "plugin://trusted/signed-v1"
    assert plugin.manifest.signer == "exo-security"
    assert plugin.manifest.sandbox_mode == "declarative_rules_only"
    assert len(plugin.rules) >= 1


def test_resolve_signed_ingress_plugin_rejects_unknown_ref() -> None:
    with pytest.raises(ValueError, match="INGRESS_SIGNED_PLUGIN_UNKNOWN"):
        resolve_signed_ingress_plugin("plugin://unknown/missing")


def test_classify_signed_plugin_lifecycle_transitions() -> None:
    assert classify_signed_plugin_lifecycle_transition(
        previous_plugin_ref="",
        new_plugin_ref="plugin://trusted/signed-v1",
        active_run_count=0,
    ).action == "load"
    assert classify_signed_plugin_lifecycle_transition(
        previous_plugin_ref="plugin://trusted/signed-v1",
        new_plugin_ref="",
        active_run_count=0,
    ).action == "unload"
    assert classify_signed_plugin_lifecycle_transition(
        previous_plugin_ref="plugin://trusted/signed-v1",
        new_plugin_ref="plugin://trusted/signed-v2",
        active_run_count=0,
    ).action == "reload"
    assert classify_signed_plugin_lifecycle_transition(
        previous_plugin_ref="plugin://trusted/signed-v1",
        new_plugin_ref="plugin://trusted/signed-v1",
        active_run_count=3,
    ).action == "none"


def test_classify_signed_plugin_lifecycle_blocks_unload_or_reload_with_active_runs() -> None:
    with pytest.raises(ValueError, match="INGRESS_SIGNED_PLUGIN_LIFECYCLE_BLOCKED_ACTIVE_RUNS"):
        classify_signed_plugin_lifecycle_transition(
            previous_plugin_ref="plugin://trusted/signed-v1",
            new_plugin_ref="",
            active_run_count=1,
        )
    with pytest.raises(ValueError, match="INGRESS_SIGNED_PLUGIN_LIFECYCLE_BLOCKED_ACTIVE_RUNS"):
        classify_signed_plugin_lifecycle_transition(
            previous_plugin_ref="plugin://trusted/signed-v1",
            new_plugin_ref="plugin://trusted/signed-v2",
            active_run_count=2,
        )

