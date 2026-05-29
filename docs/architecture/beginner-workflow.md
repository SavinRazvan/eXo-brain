<!--
File: beginner-workflow.md
Path: docs/architecture/beginner-workflow.md
Role: Beginner-friendly explanation of the eXo-brain request workflow using plain language and analogies.
Used By:
 - docs/README.md
 - docs/architecture/README.md
Depends On:
 - README.md
 - docs/architecture/mvp.md
 - docs/architecture/governed-execution-pipeline.md
 - docs/plans/tenant-tool-execution-architecture.md
Notes:
 - Prefer plain language and one consistent analogy over internal jargon.
-->

# Beginner workflow guide

## What this product is

`eXo-brain` is not "just an AI model".

It is the **controlled system around the AI**.

Think of it like an office building:

- the **front desk** receives requests,
- **security** checks who you are,
- the **rules desk** checks what is allowed,
- the **dispatcher** sends work to the right specialist,
- the **secure tool room** handles risky actions,
- the **records room** keeps proof of what happened.

The model provider is only one worker inside that building.  
The real product is the building, the rules, and the control system.

## The simplest one-line workflow

**A request comes in -> identity is checked -> rules are checked -> the right AI runtime is used -> tools are executed safely if needed -> the answer comes back -> proof is recorded.**

## Why this exists

Without a system like this, a team usually talks directly to one AI provider.

That is fast at the beginning, but later it creates problems:

- you get tied to one provider,
- risky actions can happen with weak controls,
- customers can get mixed together if tenant boundaries are weak,
- you have poor audit history,
- it becomes hard to control policy, cost, and operations.

`eXo-brain` exists to solve those control problems.

## Step-by-step story

Imagine a customer sends this request:

> "Read this contract, summarize it, and if the policy allows it, send an email."

Here is what happens in simple terms.

### 1. The request arrives at the front desk

The front desk receives the request through the API.

In the codebase, this is mainly:

- `src/api/app.py`
- `src/api/routers/turns.py`

### 2. Security checks the badge

Before anything useful happens, the system checks:

- who is making the request,
- which tenant/customer they belong to,
- whether they are allowed to use this part of the system.

In the codebase, this is mainly:

- `src/api/middleware/auth.py`
- `src/api/dependencies.py`
- `src/identity/*`

### 3. The rules desk checks the request

Now the system asks:

- Is this request allowed?
- Should it be blocked?
- Should it be escalated for review?
- Does this tenant have access to this feature level?

This is the governance part of the system. On the **production API path**, **entitlements** and **ingress gates** run in `turns.py` **before** the model or orchestrator sees the user text (pre-model guard rails).

**Canonical ordering:** [governed-execution-pipeline.md](governed-execution-pipeline.md).

In the codebase, this is mainly:

- `src/policies/ingress_gates.py`, `src/policies/ingress_profiles.py` (evaluated from `src/api/routers/turns.py`)
- `src/api/middleware/entitlements.py`
- `src/policies/*` (tool policy and risk gates — also used inside the orchestrator path)

### 4. The dispatcher chooses how to run the work

If the request is allowed, the system chooses how to execute it.

The dispatcher does not have to be the AI itself.  
Its job is to coordinate the work and send it to the right runtime/provider.

In the codebase, this is mainly:

- `src/core/orchestrator.py`
- `src/runtime/tenant_runtime.py`
- `src/runtime/runtime_adapter.py`

### 5. The AI specialist starts answering

Now the chosen provider/runtime begins the actual AI work.

This is where the system talks to the model provider.

In the codebase, this is mainly:

- `src/runtime/*`
- `packages/*`

### 6. The AI may ask for a tool

Sometimes the model cannot finish the task with text alone.

For example, it may need to:

- call a tool,
- fetch data,
- trigger a business action,
- send something out.

Important idea:

The model should **ask for the tool**, but it should **not directly perform the risky side effect by itself**.

### 7. The secure tool room executes the risky action

This is one of the most important design ideas in the whole repo.

Instead of letting the model directly perform a risky action, the platform sends that action through a controlled execution path:

- policies are checked,
- deterministic execution can be enforced,
- limits and guards can apply,
- results are normalized,
- audit records can be written.

In the codebase, this is mainly:

- `src/tools/*`
- `src/policies/middleware.py`
- `src/core/orchestrator.py`

### 8. The result goes back to the AI flow

After the secure tool path finishes, the result goes back into the AI run.

The AI can continue, now using the safe result produced by the platform.

### 9. The customer receives the answer

The answer can be streamed back step by step, not only at the very end.

That means the customer can see progress while the system is still working.

In the codebase, this is mainly:

- `src/api/routers/turns.py`

### 10. The records room keeps proof

While all this is happening, the system should keep evidence:

- what was requested,
- what decisions were made,
- what tools ran,
- what happened in the end,
- what needs to be audited later.

In the codebase, this is mainly:

- `src/persistence/*`
- `src/audit/*`
- `src/compliance/*`
- `src/observability/*`
- `src/api/routers/audit.py`

## What each big part means

| Part | Plain-language meaning | Main repo areas |
|---|---|---|
| Front desk | Entry point that receives requests | `src/api/*` |
| Security | Checks identity and tenant scope | `src/api/middleware/auth.py`, `src/api/dependencies.py`, `src/identity/*` |
| Rules desk | Decides what is allowed, denied, or escalated (ingress + entitlements on API path) | `src/api/routers/turns.py`, `src/policies/ingress_*`, `src/api/middleware/entitlements.py`, `src/policies/*` |
| Dispatcher | Coordinates the whole request | `src/core/*` |
| Specialist phone lines | Connections to model providers | `src/runtime/*`, `packages/*` |
| Secure tool room | Safe execution of tools and side effects | `src/tools/*` |
| Tenant walls | Separation between customers | `src/tenancy/*`, `src/runtime/tenant_runtime.py` |
| Filing cabinets | Saved operational state | `src/persistence/*` |
| Cameras and timers | Logs, metrics, tracing, timelines | `src/observability/*` |
| Proof and signed evidence | Audit and compliance outputs | `src/audit/*`, `src/compliance/*`, `src/api/routers/audit.py` |

## Why the split into parts is useful

This split is good because it separates responsibilities:

- the API should not own provider logic,
- the provider should not own governance,
- the model should not directly own risky side effects,
- the audit path should not depend on memory or luck,
- customer separation should be explicit, not implied.

In simple words:

**each room in the building should have one clear job.**

That is why the current direction of the architecture is mostly correct.

## Where bottlenecks usually appear

Here are the main bottlenecks in plain language.

### 1. The front desk can become too busy

If too many decisions are concentrated in the request entry path, the whole system becomes harder to reason about.

In this repo, `src/api/routers/turns.py` is a major traffic controller, so it needs to stay simple and well controlled.

### 2. The dispatcher can become too crowded

If the place that builds and coordinates runtimes also owns too many special cases, complexity grows quickly.

In this repo, `src/runtime/tenant_runtime.py` is one of the main composition hotspots.

### 3. The records room can be weaker than the rules story

You can have excellent governance ideas, but if evidence and state are not durable enough, enterprise trust is weakened.

This is why persistence, audit durability, and operational evidence matter so much.

### 4. Too many futures at the same time

The product currently points toward many directions at once:

- multiple provider adapters,
- OpenAI-compatible gateway,
- hosted tools,
- BYOC tools,
- entitlements,
- signed plugins,
- different deployment models,
- compliance packaging.

This is a common bottleneck: **too many products inside one product**.

### 5. Delivery can be less mature than design

A repo can have strong architecture and strong tests, but still be weak in:

- deployment,
- rollback,
- production operations,
- environment standardization,
- durable evidence flows.

That is an operations bottleneck, not a design bottleneck.

## The simplest viable version

If the goal is to make this product simple, viable, and easy to control, the easiest version to operate is:

1. one public API surface,
2. one clear auth model,
3. one durable production database,
4. one first-class provider path,
5. one first-class safe tool execution path,
6. one durable audit/evidence path,
7. one deployment model first.

Then, only after that path is stable and boring, add:

- more providers,
- more execution modes,
- more deployment models,
- more premium governance depth.

## Short explanation you can say out loud

If you need to explain the product to a beginner, this sentence works well:

> `eXo-brain` is a control tower for AI work. It checks identity, applies rules, chooses the right execution path, runs risky tools safely, and keeps proof of what happened.

## If you want to read the code later

A simple reading order is:

1. `README.md`
2. `docs/architecture/governed-execution-pipeline.md` (canonical turn ordering)
3. `docs/architecture/mvp.md`
4. `docs/plans/tenant-tool-execution-architecture.md`
5. `src/api/app.py`
6. `src/api/routers/turns.py`
7. `src/core/orchestrator.py`
8. `src/runtime/tenant_runtime.py`
9. `src/tools/*`
10. `src/policies/*`
11. `src/persistence/*` and `src/api/routers/audit.py`

## If you want hands-on proof (optional)

Notebooks complement `tests/` with narrative, printable evidence:

| Goal | Start here |
|---|---|
| 15 min executive skim (no API key) | [notebooks/EVALUATOR_GUIDE.md](../../notebooks/EVALUATOR_GUIDE.md) |
| Full index and learning order | [notebooks/README.md](../../notebooks/README.md) |
| Governed execution + `safe_add_proven` proof | `notebooks/tutorial_08_governed_execution_sandbox.ipynb` (see pipeline doc **Hands-on proof**) |

This guide is intentionally plain-language first.  
It explains the workflow and the idea behind the system, not every technical detail.
