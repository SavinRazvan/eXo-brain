# Compliance tests

## Evidence bundle ownership

Two suites touch `src/compliance/evidence_bundle.py` with different scopes:

| Location | Role |
| -------- | ---- |
| [`test_evidence_bundle.py`](test_evidence_bundle.py) | **Unit tests** for signing, keyring resolution, fingerprints, and branch-complete coverage of `evidence_bundle` helpers. Imports `src.audit.trail` only where the compliance code under test depends on audit chain primitives (deterministic fixtures). |
| [`../audit/test_evidence_bundle_generation.py`](../audit/test_evidence_bundle_generation.py) | **Integration-style** test: builds a bundle via `build_evidence_bundle` and asserts **audit integrity** reporting (durable audit path). Owned by the **`audit`** test bucket for API/store continuity, not duplicated under `compliance/`. |

**FIND-005 (2026-03-24):** No file moves required; ownership is explicit here and in [`.local/index-and-planning/current/test-index.md`](../../../.local/index-and-planning/current/test-index.md).
