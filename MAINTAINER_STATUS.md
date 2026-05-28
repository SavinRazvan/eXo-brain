# Maintainer Status

## Current Posture

eXo-brain is an independent, single-maintainer reference implementation of
governed agentic AI execution.

It is **not** a commercial SaaS product, not an enterprise-supported platform,
and not a production deployment template. It is maintained part-time by
**Savin Ionut Razvan** (credited as Savin I. Razvan) as an open-source research
and engineering artifact.

## What This Repository Is For

- Demonstrating governed execution patterns for tool-using AI systems.
- Providing a concrete reference for provider-neutral adapter boundaries.
- Exploring policy gates, deterministic tool execution, auditability, tenant
  governance, and runtime control.
- Supporting technical writing, design-partner conversations, and architecture
  reviews.

## What This Repository Is Not

- Not a vendor-backed enterprise product.
- Not covered by an SLA.
- Not certified for SOC 2, ISO 42001, HIPAA, PCI, GDPR, or EU AI Act compliance.
- Not a complete multi-provider adapter marketplace.
- Not a production Kubernetes, cloud, or private-deployment distribution.
- Not guaranteed to accept every external contribution.

## Maintenance Expectations

- Issues are triaged best-effort.
- Pull requests are reviewed best-effort and may take days or weeks.
- Architectural changes should start as design-discussion issues.
- Security issues should follow [SECURITY.md](SECURITY.md).
- Releases happen when useful slices are ready, not on a fixed cadence.

## How This Project Is Built

This repository is developed with **AI-assisted implementation** where it helps
speed up iteration (drafting, refactors, test scaffolds). The maintainer remains
responsible for:

- architecture decisions and system boundaries,
- reviewing and validating changes,
- keeping tests and architecture checks green,
- ensuring public-facing claims remain aligned with `STATUS.md`.

AI assistance is an implementation accelerator, not a substitute for ownership
or evidence. If you evaluate this repo, evaluate the **boundaries and evidence**
(tests, checks, docs) rather than assumptions about how quickly code was typed.

## Contribution Filter

The project is most likely to accept changes that:

- Strengthen non-bypassable policy and deterministic execution paths.
- Improve evidence, tests, or architecture checks.
- Reduce operational ambiguity for local evaluation.
- Clarify provider-neutral adapter boundaries.
- Improve governance for MCP, tools, tenants, audit, or runtime control.

The project is unlikely to accept changes that:

- Add provider SDK imports outside runtime adapter modules.
- Introduce a mandatory UI or dashboard.
- Expand provider breadth without tests and conformance evidence.
- Add enterprise claims that are not backed by code, tests, and docs.
- Create a parallel execution path that bypasses policy or audit.

## Design-Partner Work

The maintainer is open to paid design-partner or embedded engineering work
around governed AI execution, adapter-neutral control planes, policy-wrapped
tool execution, and related architecture reviews.

This repository can be used as a reference implementation or starting point,
but any production deployment should go through a separate hardening process.
