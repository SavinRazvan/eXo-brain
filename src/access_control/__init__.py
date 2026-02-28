"""
File: __init__.py
Path: src/access_control/__init__.py
Role: Public exports for access-control module.
Used By:
 - src/policies/risk_gates.py
 - tests/unit/test_access_control_rbac.py
Depends On:
 - src/access_control/contracts.py
 - src/access_control/policy_engine.py
Notes:
 - Keeps import surface explicit and stable.
"""

from src.access_control.contracts import AccessDecision, AccessRequest
from src.access_control.policy_engine import AccessControlConfig, AccessPolicyEngine

__all__ = ["AccessDecision", "AccessRequest", "AccessControlConfig", "AccessPolicyEngine"]

