<!--
File: abbreviations-notepad.md
Path: docs/operations/abbreviations-notepad.md
Role: Beginner-friendly glossary and plain-language notes for architecture/workflow abbreviations.
Used By:
 - README.md
 - AGENTS.md
Depends On:
 - docs/strategy/goal.md
 - docs/strategy/next-directions.md
 - src/api/*
Notes:
 - Keep definitions short and practical for newcomers.
-->

# Abbreviations Notepad

This is a quick notepad for reading `README.md`, `AGENTS.md`, and architecture docs without guessing terminology.

## One-turn story (plain language)

1. A user sends a request to the API.
2. The platform checks tenant identity and governance rules.
3. The orchestrator decides what to run.
4. A runtime adapter talks to the selected model provider.
5. Tool calls are policy-checked and run deterministically when risky.
6. Events and audit records are stored with a correlation ID so the run can be traced later.

## Core abbreviations

| Abbreviation | Meaning | Simple explanation |
|---|---|---|
| AI | Artificial Intelligence | Systems that generate or process language/data using models. |
| LLM | Large Language Model | The model that generates responses. |
| API | Application Programming Interface | The HTTP endpoints customers call. |
| SDK | Software Development Kit | Helper package for building integrations/adapters. |
| ABC | Abstract Base Class | Interface contract that implementations must follow. |
| DSL | Domain-Specific Language | A constrained config language for rules/policies. |
| CRUD | Create, Read, Update, Delete | Basic data operations in APIs. |

## Runtime and architecture abbreviations

| Abbreviation | Meaning | Simple explanation |
|---|---|---|
| BYOC | Bring Your Own Cloud | Customer runs tool execution in their own cloud/workers. |
| MCP | Model Context Protocol | Standard way to connect model tools/resources safely. |
| DAG | Directed Acyclic Graph | Task graph used for background job orchestration. |
| TTL | Time To Live | How long a record/token/state stays valid. |
| DLQ | Dead Letter Queue | Failed jobs/events routed for retry or inspection. |
| SLO | Service Level Objective | Reliability/latency target (for example p95 turn latency). |
| SLA | Service Level Agreement | Contractual reliability commitment to customers. |
| p95 | 95th Percentile | 95% of requests are faster than this latency value. |
| Option C | API-first operating mode | Current delivery posture: control plane + adapter plane + data plane. |

## Security and governance abbreviations

| Abbreviation | Meaning | Simple explanation |
|---|---|---|
| JWT | JSON Web Token | Signed token used for identity/authentication. |
| RBAC | Role-Based Access Control | Access decisions based on user roles. |
| AuthN | Authentication | Confirming who the caller is. |
| AuthZ | Authorization | Confirming what the caller is allowed to do. |
| P0 / P1 / P2 | Severity levels | P0 critical, P1 major, P2 minor priority. |
| CI | Continuous Integration | Automated checks/tests that run on changes. |
| RC | Release Candidate | Pre-release validation package/checkpoint. |
| PR | Pull Request | Proposed change set reviewed before merge. |

## Transport and protocol abbreviations

| Abbreviation | Meaning | Simple explanation |
|---|---|---|
| REST | Representational State Transfer | Standard request/response HTTP API style. |
| SSE | Server-Sent Events | One-way streaming updates from server to client. |
| WS | WebSocket | Two-way persistent connection for real-time turns. |
| HTTP | HyperText Transfer Protocol | Transport protocol used by the API. |
| JSON | JavaScript Object Notation | Data format used in API payloads/events. |

## Product/tiering abbreviations

| Abbreviation | Meaning | Simple explanation |
|---|---|---|
| Foundation | Base tier | Core safe baseline features available to all customers. |
| Pro | Mid tier | More governance depth, controls, and automation. |
| Enterprise | Top tier | Compliance-grade evidence, strict controls, advanced operations. |
| Entitlement | Feature permission by tier | Rule that decides which customer can use which capability. |

## Notes for newcomers

- If a term is not clear, add it here immediately so future docs stay easy to read.
- Prefer plain language in docs, then include abbreviation in parentheses.
- Keep abbreviations consistent across docs, API schemas, and audit artifacts.
