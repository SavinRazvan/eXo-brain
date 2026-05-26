---
name: Feature discussion
about: Discuss a possible change before implementation
title: "feature: "
labels: enhancement, discussion
assignees: ""
---

## Problem

<!-- What user problem or architecture gap does this address? -->

## Proposed Direction

<!-- Describe the smallest useful change. Avoid implementation detail unless it matters. -->

## Alternatives Considered

<!-- What else could solve this? Why not use that? -->

## Architecture Fit

Please check the invariants that apply:

- [ ] Does not import provider SDKs outside runtime adapter modules.
- [ ] Does not bypass policy middleware before tool execution.
- [ ] Preserves capability + policy mode selection.
- [ ] Preserves tenant isolation.
- [ ] Keeps UI/dashboard out of the required product surface.
- [ ] Adds tests or evidence appropriate to the risk.

## Acceptance Criteria

- [ ]
- [ ]
- [ ]
