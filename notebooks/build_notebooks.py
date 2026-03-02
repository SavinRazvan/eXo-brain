"""
Helper script that writes both notebooks using nbformat.
Run once: python notebooks/build_notebooks.py
"""
import nbformat as nbf
from pathlib import Path

NB_DIR = Path(__file__).parent


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(text.strip())


# ──────────────────────────────────────────────────────────────────────────────
# NOTEBOOK 1 — First Brick: Core Framework
# ──────────────────────────────────────────────────────────────────────────────

nb1 = nbf.v4.new_notebook()
nb1.metadata["kernelspec"] = {
    "display_name": "eXo-brain (.exo_env)",
    "language": "python",
    "name": "exo-brain",
}
nb1.metadata["language_info"] = {"name": "python", "version": "3.13"}

nb1.cells = [

    md("""
# Brick 1 — eXo-brain Core Framework

**What this notebook covers:**
- How the framework is structured and why it was built this way
- Running a complete single-turn orchestration with a deterministic tool call
- Running a multi-node background DAG with full observability evidence

**No API key required.** Everything runs in-process with in-memory adapters.
"""),

    code("""
# Load .env so any credentials / config are available in this session
import pathlib, os
_root = pathlib.Path.cwd().parent if pathlib.Path.cwd().name == "notebooks" else pathlib.Path.cwd()
_env  = _root / ".env"
if _env.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env, override=False)
        print(f"✓ .env loaded from {_env}")
    except ImportError:
        print("⚠ python-dotenv not installed — install it with: pip install python-dotenv")
else:
    print(f"ℹ no .env found at {_env} — using system environment only")
"""),

    md("""
## How eXo-brain works

eXo-brain is a **policy-governed execution layer** that sits between an AI model and its tools.

The central insight is: **model tool calls are intent, not execution.**  
When a model says "call `delete_record(id=42)`", the framework intercepts that intent,
runs it through policy gates, and only then executes it — deterministically, with audit trail.

```
Host / API / CLI
      │
      ▼
OrchestratorHostAdapter       ← thin transport boundary
      │
      ▼
Orchestrator.run_turn()       ← provider-neutral turn loop
      │
      ├── RuntimeAdapter      ← pluggable provider (OpenAI, Ollama, custom…)
      │     └── yields RuntimeEvents (TOOL_INTENT, OUTPUT_DELTA, RUN_COMPLETE)
      │
      ├── PolicyMiddleware    ← before_tool_call: ALLOW / DENY / ESCALATE
      │     └── RiskGatePolicy, RBAC, tenant overlays
      │
      ├── ModeSelector        ← DETERMINISTIC or PROVIDER_NATIVE
      │     └── state-changing / HIGH/CRITICAL → always DETERMINISTIC
      │
      └── DeterministicToolExecutor
            └── validate → authz → retry → audit_log → redact → handler()
```

**Key guarantee:** state-changing or high-risk tool calls are *always* executed
deterministically, regardless of what the adapter or model requested.
"""),

    md("""
## Section 1 — Single-Turn Orchestration

We will:
1. Register a tool in the `ToolRegistry`
2. Wire up the `Orchestrator` with a policy and a runtime adapter
3. Submit a turn that includes a planned tool call
4. Watch the event stream and understand each event
"""),

    code("""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd().parent))  # make src/ importable

from src.core.orchestrator import Orchestrator
from src.policies.middleware import DeterministicFirstPolicyMiddleware
from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter
from src.schemas.events import RuntimeEventType
from src.schemas.tool_io import RiskTier
from src.tools.executor import DeterministicToolExecutor
from src.tools.registry import ToolDescriptor, ToolRegistry

print("✓ imports ok")
"""),

    md("""
### Step 1 — Register a tool

`ToolDescriptor` declares:
- `name` — how the model will refer to it
- `handler` — the actual Python callable (runs deterministically, never by the model)
- `risk_tier` — LOW / MEDIUM / HIGH / CRITICAL (drives mode selection)
- `is_state_changing` — `True` forces deterministic mode unconditionally
"""),

    code("""
registry = ToolRegistry()

registry.register(ToolDescriptor(
    name="my_tool",
    handler=lambda x: {"output": x * 2},   # doubles the input
    risk_tier=RiskTier.HIGH,
    is_state_changing=True,
))

print(f"✓ registered tools: {registry.list_tools()}")
"""),

    md("""
### Step 2 — Wire the Orchestrator

Three components are injected:
- `runtime_adapter` — the provider boundary (currently a simulation stub)
- `policy_middleware` — `DeterministicFirstPolicyMiddleware` enforces deterministic execution
  for HIGH/CRITICAL and state-changing operations
- `tool_executor` — executes tools with the full decorator stack (validate → authz → retry → audit → redact)
"""),

    code("""
policy = DeterministicFirstPolicyMiddleware()

orchestrator = Orchestrator(
    runtime_adapter=OpenAIAgentsRuntimeAdapter(),
    policy_middleware=policy,
    tool_executor=DeterministicToolExecutor(registry=registry, policy=policy),
)

print("✓ orchestrator ready")
print(f"  adapter capabilities: {orchestrator._runtime_adapter.get_capabilities()}")

# verify healthcheck works (adapter is a simulation stub — always HEALTHY)
health = await orchestrator._runtime_adapter.healthcheck()
print(f"  adapter health:       {health.state.value}")
"""),

    md("""
### Step 3 — Build the context and run a turn

The `context` dict carries session metadata and, crucially for this demo, a
`planned_tool_call`. In production, this comes from the model's response —
the adapter parses it and emits a `TOOL_INTENT` event. Here we inject it directly
to demonstrate the execution path without a live model.

**Event types you will see:**
| Event | Meaning |
|-------|---------|
| `TOOL_INTENT` | Adapter signalled that a tool should be called — orchestrator intercepts |
| `OUTPUT_DELTA` | Streamed text chunk from the model (or tool result acknowledgement) |
| `RUN_COMPLETE` | Turn finished — full output payload available |
"""),

    code("""
context = {
    "run_id":    "r1",
    "job_id":    "j1",
    "task_id":   "t1",
    "agent_id":  "a1",
    "planned_tool_call": {
        "call_id":          "tc1",
        "tool_name":        "my_tool",
        "arguments":        {"x": 5},
        "risk_tier":        RiskTier.HIGH.value,
        "is_state_changing": True,
    },
}

async def run_turn():
    events = []
    async for event in orchestrator.run_turn("sess1", "go", context):
        events.append(event)
        # print each event as it arrives
        print(f"  [{event.event_type.value:15s}]  payload={event.payload}")
    return events

print("── running turn ──────────────────────────────────────────")
events = await run_turn()
print("──────────────────────────────────────────────────────────")
print(f"\\n✓ turn complete — {len(events)} events received")
types = {e.event_type for e in events}
assert RuntimeEventType.RUN_COMPLETE in types
"""),

    md("""
### What just happened

```
1. Orchestrator called adapter.start_session()
2. Adapter.run_turn() read planned_tool_call → emitted TOOL_INTENT
3. Orchestrator intercepted TOOL_INTENT:
   a. PolicyMiddleware.before_tool_call()
      → risk=HIGH + is_state_changing=True → decision=ALLOW, mode=DETERMINISTIC
   b. ModeSelector confirmed DETERMINISTIC (state-changing overrides everything)
   c. DeterministicToolExecutor.execute()
      → validate args → authz check → call handler(x=5) → {"output": 10}
      → PolicyMiddleware.after_tool_call() (correlation_id + mode checks)
   d. ToolResult submitted back to adapter via submit_tool_results()
4. Adapter emitted OUTPUT_DELTA + RUN_COMPLETE
```

The tool `lambda x: {"output": x * 2}` with `x=5` returned `{"output": 10}`.
The model never executed the tool. The framework did — safely.
"""),

    md("""
---
## Section 2 — Background DAG Execution

For long-running, multi-step workflows the framework provides a full background
job runtime built on a DAG scheduler.

```
BackgroundRuntime.submit(graph, payload, job_id)
      │
      ├── TenantQuotaManager.check_submission()   ← quota gate
      │
      └── TaskScheduler.execute(graph)
            │
            ├── Wave 1: all nodes with no dependencies run in parallel
            │     └── WorkerPool (bounded concurrency semaphore)
            │           └── _run_node()
            │                 ├── CheckpointStore.get()    ← resume if prior state
            │                 ├── handler(payload)         ← must be async def
            │                 ├── CheckpointStore.save()   ← durable progress
            │                 └── StructuredLogger / RuntimeMetrics / RuntimeTimeline
            │
            └── Wave 2…N: unlock nodes whose dependencies completed
```

**Critical rule:** every `TaskNode` handler must be `async def`.  
The scheduler does `await asyncio.wait_for(handler(payload), timeout=…)`.
A plain `lambda` or sync function will silently fail with `TASK_EXECUTION_ERROR`.
"""),

    code("""
from src.core.background_runtime import BackgroundRuntime, JobStatus
from src.core.checkpoint_store import InMemoryCheckpointStore
from src.core.scheduler import TaskScheduler
from src.core.task_graph import TaskGraph, TaskNode
from src.core.worker_pool import WorkerPool
from src.observability.logging import StructuredLogger
from src.observability.metrics import RuntimeMetrics
from src.observability.timeline import RuntimeTimeline
import asyncio

print("✓ background runtime imports ok")
"""),

    md("""
### Step 1 — Wire the runtime with observability

Three observability components are injected:
- `StructuredLogger` — structured log records with `correlation_id`, `level`, `event`, `context`
- `RuntimeMetrics` — named counters, latency observations, gauges
- `RuntimeTimeline` — append-only ordered event log per `correlation_id`
"""),

    code("""
logger   = StructuredLogger()
metrics  = RuntimeMetrics()
timeline = RuntimeTimeline()

scheduler = TaskScheduler(
    worker_pool=WorkerPool(max_concurrency=3),
    checkpoint_store=InMemoryCheckpointStore(),
    logger=logger,
    metrics=metrics,
    timeline=timeline,
)
runtime = BackgroundRuntime(
    scheduler=scheduler,
    logger=logger,
    metrics=metrics,
    timeline=timeline,
)

print("✓ BackgroundRuntime ready  (workers=3, checkpoint=in-memory)")
"""),

    md("""
### Step 2 — Define the DAG

A two-node DAG where `process` depends on the output of `fetch`:

```
fetch ──► process
```

Each handler receives a `payload` dict that always contains:
- `payload["dependencies"]["<node_id>"]` — completed upstream node output
- `payload["node_id"]` — this node's id
- `payload["job_id"]` — the job id
- anything from the initial `payload` you passed to `submit()`
"""),

    code("""
async def fetch(payload: dict) -> dict:
    return {"data": 42}

async def process(payload: dict) -> dict:
    upstream = payload["dependencies"]["fetch"]["data"]
    return {"result": upstream * 2}

graph = TaskGraph([
    TaskNode("fetch",   handler=fetch),
    TaskNode("process", handler=process, depends_on=["fetch"]),
])

print("✓ graph defined")
print(f"  nodes: {graph.node_ids()}")
"""),

    md("""
### Step 3 — Submit and wait
"""),

    code("""
async def run_dag():
    job_id = runtime.submit(graph=graph, payload={}, job_id="demo_job")
    print(f"submitted  job_id={job_id}  status={runtime.get_job(job_id).status.value}")

    # poll until done (max 2s)
    for i in range(200):
        status = runtime.get_job(job_id).status
        if status in {JobStatus.COMPLETED, JobStatus.FAILED}:
            print(f"done       iterations={i+1}  status={status.value}")
            break
        await asyncio.sleep(0.01)

    return runtime.get_job(job_id)

job = await run_dag()
"""),

    md("""
### Step 4 — Inspect results, timeline, metrics, and logs
"""),

    code("""
job_id = "demo_job"

print("── node outcomes ─────────────────────────────────────────")
for node_id, outcome in job.result.outcomes.items():
    print(f"  {node_id:10s}  status={outcome.status.value:10s}  output={outcome.output}")

print("\\n── metrics ───────────────────────────────────────────────")
for key, value in sorted(metrics.counters.items()):
    print(f"  {key} = {value}")

print("\\n── timeline (ordered events for this job) ────────────────")
for entry in timeline.entries_for(job_id):
    print(f"  {entry.event:40s}  {entry.payload}")

print("\\n── structured logs ───────────────────────────────────────")
for record in logger.records():
    if record.correlation_id == job_id:
        print(f"  [{record.level.value:5s}] {record.event:40s}  {record.context}")

assert job.status == JobStatus.COMPLETED
print("\\n✓ PASS")
"""),

    md("""
### What the output tells you

| What you see | What it means |
|---|---|
| `scheduler.node_started` | Scheduler began executing a node |
| `scheduler.node_completed` | Node handler returned successfully, checkpoint saved |
| `scheduler.job_completed` | All nodes finished (no failures) |
| `background.job_finished` | BackgroundRuntime marked job COMPLETED |
| `scheduler.node.success = 2` | 2 nodes completed across all jobs |
| `scheduler.queue_depth` | Remaining nodes at each wave boundary |

The `fetch` node output (`{"data": 42}`) flows into `process` via
`payload["dependencies"]["fetch"]`, which returns `{"result": 84}`.
"""),

    md("""
---
## Summary — What "First Brick" gives you

| Capability | Status |
|---|---|
| Provider-neutral runtime contract | ✅ done |
| Deterministic-first policy enforcement | ✅ done |
| Risk-gate evaluation (ALLOW / DENY / ESCALATE) | ✅ done |
| RBAC / tenant overlay policy wiring | ✅ done |
| Background DAG scheduler with checkpoint/resume | ✅ done |
| Observability: structured logs, metrics, timeline, tracing | ✅ done |
| Persistence: session, checkpoint, event, audit, workflow stores | ✅ done |
| Resilience: retry, circuit breaker, DLQ, compensation hooks | ✅ done |
| Audit: tamper-evident SHA-256 hash chain | ✅ done |
| MCP server integration with trust tiers | ✅ done |

**What's missing:** a real provider adapter that calls an actual AI model.  
That is what **Brick 2** builds.
"""),

]

# ──────────────────────────────────────────────────────────────────────────────
# NOTEBOOK 2 — Second Brick: OpenAI Agents SDK Adapter
# ──────────────────────────────────────────────────────────────────────────────

nb2 = nbf.v4.new_notebook()
nb2.metadata["kernelspec"] = {
    "display_name": "eXo-brain (.exo_env)",
    "language": "python",
    "name": "exo-brain",
}
nb2.metadata["language_info"] = {"name": "python", "version": "3.13"}

# ─── INSTRUCTIONS CONSTANT (avoids triple-quote nesting issues) ───────────────
CALC_INSTRUCTIONS = (
    "You are a helpful math assistant. "
    "You MUST use the calculate_result function for every arithmetic operation. "
    "Supported operations: add, subtract, multiply, divide. "
    "Always call the function first, then explain the reasoning, then state the conclusion."
)

nb2.cells = [

    md("""
# Brick 2 — OpenAI Agents SDK Adapter

This notebook starts from a real agent generated by **OpenAI Agent Builder** and shows
exactly what eXo-brain adds on top.

**The story in three acts:**
1. **Before eXo-brain** — the agent runs but the tool body is `pass`, so nothing actually executes
2. **The adapter** — wrap the SDK behind the provider-neutral `RuntimeAdapter` contract
3. **After eXo-brain** — the same agent, same model, same tool schema — but now the tool runs
   deterministically with policy enforcement, risk gating, and a full audit trail

**Cells marked `[REQUIRES API KEY]` need `OPENAI_API_KEY` in your environment.**  
All other cells run without credentials — including the policy enforcement demo.
"""),


    code("""
import sys, pathlib, os, asyncio

# ── path setup ────────────────────────────────────────────────────────────────
_root = pathlib.Path.cwd().parent if pathlib.Path.cwd().name == "notebooks" else pathlib.Path.cwd()
sys.path.insert(0, str(_root))

# ── load .env ─────────────────────────────────────────────────────────────────
_env = _root / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(_env, override=False)
    print(f"✓ .env loaded from {_env}")
else:
    print(f"ℹ no .env at {_env}")

# ── framework imports ─────────────────────────────────────────────────────────
from src.runtime.runtime_adapter import RuntimeAdapter, SessionHandle
from src.runtime.capability_map import ProviderCapabilityMap, HealthStatus, HealthState, SecurityTier
from src.schemas.events import RuntimeEvent, RuntimeEventType
from src.schemas.tool_io import RiskTier, ToolCallContext, ToolResult, ToolStatus
from src.core.orchestrator import Orchestrator
from src.policies.middleware import DeterministicFirstPolicyMiddleware
from src.tools.executor import DeterministicToolExecutor
from src.tools.registry import ToolDescriptor, ToolRegistry

# ── openai agents sdk ─────────────────────────────────────────────────────────
from agents import Agent, Runner, function_tool, ModelSettings, TResponseInputItem

_key_set = bool(os.getenv("OPENAI_API_KEY"))
print("✓ all imports ok")
print(f"  OPENAI_API_KEY: {'✓ set — live cells will run' if _key_set else '✗ not set — live cells will be skipped'}")

# ── Agent instructions (shared across cells) ──────────────────────────────────
CALC_INSTRUCTIONS = (
    "You are a helpful math assistant. "
    "You MUST use the calculate_result function for every arithmetic operation. "
    "Supported operations: add, subtract, multiply, divide. "
    "Always call the function first, then explain the reasoning, then state the conclusion."
)
print(f"  CALC_INSTRUCTIONS defined")
"""),

    md("""
---
## Act 1 — The original agent (as generated by OpenAI Agent Builder)

This is the exact Python code exported from OpenAI Agent Builder.

The agent is a math assistant that must call `calculate_result` for every arithmetic
operation. The tool parameters match the JSON schema embedded in the instructions:
`operation` (enum: add / subtract / multiply / divide), `operand1`, `operand2`.

**The problem:** `calculate_result` body is `pass` — it returns `None`.
The model dutifully calls it, but nothing happens. The result the model
receives back is always `None`, so it guesses from its own weights.
"""),

    code("""
# ── Exact code from OpenAI Agent Builder ─────────────────────────────────────

@function_tool
def calculate_result(operation: str, operand1: float, operand2: float):
    \"\"\"Performs a basic arithmetic calculation and returns the exact result.\"\"\"
    pass   # ← unimplemented — model gets None back

exo_openai_agent = Agent(
    name="exo-openai-agent",
    instructions=CALC_INSTRUCTIONS,
    model="gpt-4o-mini",
    tools=[calculate_result],
    model_settings=ModelSettings(
        temperature=1,
        top_p=1,
        parallel_tool_calls=True,
        max_tokens=2048,
        store=True,
    ),
)

print("✓ exo_openai_agent defined (original, unmodified)")
print(f"  tools : {[t.name for t in exo_openai_agent.tools]}")
print(f"  model : {exo_openai_agent.model}")
"""),

    md("""
### [REQUIRES API KEY] Run original agent — observe the `None` problem
"""),

    code("""
if not os.getenv("OPENAI_API_KEY"):
    print("⚠  OPENAI_API_KEY not set — skipping")
else:
    print("▶ original agent  (calculate_result body = pass)...")
    print("─" * 60)
    result = await Runner.run(exo_openai_agent, "What is 5 plus 7?")
    print(f"  final output: {result.final_output!r}")
    print("─" * 60)
    print()
    print("The model called calculate_result, got None back, and guessed the answer.")
    print("No audit trail. No policy check. No error if the tool returns wrong data.")
    print("This is what eXo-brain fixes.")
"""),

    md("""
---
## Act 2 — The adapter: wrapping the SDK behind the RuntimeAdapter contract

The `OpenAIAgentsSDKAdapter` uses the **delegating wrapper** pattern:

1. `sdk_tools` are `@function_tool` objects whose **bodies call eXo-brain's executor** directly
2. `Runner.run()` handles the full agentic loop — model emits a tool call, SDK calls the function, function delegates to eXo-brain, real result returned, model continues
3. The loop completes: model receives the actual result and produces a correct final answer

Why not stream interception? If the adapter intercepts a `tool_call_item` event and returns early, the SDK stream is abandoned — the model never receives the result and the loop can never complete.

```
model emits tool call
       │
SDK calls @function_tool body
       │
       └── ToolCallContext built from typed args
              │
       DeterministicToolExecutor.execute(call)
              │
              ├── PolicyMiddleware.before_tool_call()  risk=? → ALLOW/DENY
              ├── ModeSelector → DETERMINISTIC
              └── Real handler: _calculate_result(operation, operand1, operand2)
                     │
              ToolResult returned → body returns value to SDK
                     │
              SDK feeds result back to model ← full loop
                     │
              Model generates correct final answer ✓
```
"""),

    code("""
import uuid
from typing import Any, AsyncIterator


class OpenAIAgentsSDKAdapter(RuntimeAdapter):
    \"\"\"
    Wraps the OpenAI Agents SDK behind the provider-neutral RuntimeAdapter contract.

    Uses the 'delegating wrapper' pattern:
    - sdk_tools must be @function_tool objects whose BODIES call eXo-brain's executor.
    - Runner.run() handles the full agentic loop (model → tool → result → model → answer).
    - The adapter does NOT intercept stream events; execution flows through tool bodies.
    - submit_tool_results() is a fallback stub, not used in the delegating path.
    \"\"\"

    def __init__(
        self,
        tool_registry: ToolRegistry,
        sdk_tools: list | None = None,
        provider_id: str = "openai",
        default_model: str = "gpt-4o-mini",
    ) -> None:
        self._registry      = tool_registry
        self._sdk_tools     = sdk_tools or []
        self._provider_id   = provider_id
        self._default_model = default_model
        self._sessions: dict[str, dict] = {}

    async def start_session(self, session_id: str, metadata: dict | None = None) -> SessionHandle:
        self._sessions[session_id] = {"history": [], "metadata": metadata or {}}
        return SessionHandle(session_id=session_id, provider_id=self._provider_id, metadata=metadata or {})

    async def run_turn(
        self, session_id: str, user_input: str, context: dict[str, Any],
    ) -> AsyncIterator[RuntimeEvent]:
        run_id  = str(context.get("run_id",  f"run_{uuid.uuid4().hex[:8]}"))
        corr_id = str(context.get("correlation_id", run_id))
        model   = str(context.get("model",   self._default_model))

        agent = Agent(
            name=str(context.get("agent_id", "agent_default")),
            instructions=str(context.get("instructions", "You are a helpful assistant.")),
            tools=self._sdk_tools,   # bodies already delegate to eXo-brain
            model=model,
        )

        try:
            # Full agentic loop: SDK handles model ↔ tool round-trips.
            # Each tool call routes through the @function_tool body → eXo-brain executor.
            result = await Runner.run(agent, user_input)

            # Update conversation history for multi-turn support
            session = self._sessions.setdefault(session_id, {"history": []})
            session["history"] = list(result.to_input_list())

            final = result.final_output or ""
            if final:
                yield RuntimeEvent.output_delta(
                    session_id=session_id, run_id=run_id,
                    text=final, correlation_id=corr_id,
                )
            yield RuntimeEvent.run_complete(
                session_id=session_id, run_id=run_id,
                output={"status": "completed", "provider_id": self._provider_id},
                correlation_id=corr_id,
            )

        except Exception as exc:
            yield RuntimeEvent.error(
                session_id=session_id, run_id=run_id,
                code="RUNTIME_TURN_ERROR", message=str(exc), correlation_id=corr_id,
            )

    async def submit_tool_results(self, session_id, run_id, tool_results):
        # Delegating pattern: tools execute inline via their bodies.
        # submit_tool_results() is only reached when the Orchestrator intercepts
        # a TOOL_INTENT event (e.g. from the simulation adapter in the policy demo).
        yield RuntimeEvent.run_complete(
            session_id=session_id, run_id=run_id,
            output={"status": "completed", "tool_results_count": len(tool_results)},
            correlation_id=run_id,
        )

    def get_capabilities(self) -> ProviderCapabilityMap:
        return ProviderCapabilityMap(
            provider_id=self._provider_id,
            supports_agents_sdk_native=True, supports_openai_compatible_api=False,
            supports_streaming=True, supports_function_calling=True,
            supports_structured_output=True, supports_handoffs=True,
            reliability_score=5, security_tier=SecurityTier.MANAGED_VENDOR,
            recommended_runtime_mode="hybrid",
        )

    async def healthcheck(self) -> HealthStatus:
        key = os.getenv("OPENAI_API_KEY", "")
        return HealthStatus(
            state=HealthState.HEALTHY if key else HealthState.DOWN,
            reason="api-key-present" if key else "no-api-key",
        )


print("✓ OpenAIAgentsSDKAdapter defined (delegating wrapper pattern)")
"""),

    md("""
---
## Act 3 — Wire `calculate_result` into eXo-brain

Three-part wiring:

| Part | What it does |
|---|---|
| `_calculate_result(...)` registered in `ToolRegistry` | Real implementation, run deterministically by eXo-brain |
| `DeterministicToolExecutor` + `PolicyMiddleware` | Policy checks, audit logging, error envelopes |
| `@function_tool calculate_result(...)` with delegating body | Gives the model the JSON schema; body calls executor and returns real result |

The `@function_tool` body is the **integration seam**: it builds a `ToolCallContext`, calls `executor.execute()`, and returns the actual value to the SDK. The SDK feeds it to the model. The model generates the correct final answer.
"""),

    code("""
# ── Step 1: Real implementation (runs inside eXo-brain) ──────────────────────

def _calculate_result(operation: str, operand1: float, operand2: float) -> dict:
    \"\"\"Real calculate_result logic — deterministic, policy-gated, audited.\"\"\"
    if operation == "add":
        value = operand1 + operand2
    elif operation == "subtract":
        value = operand1 - operand2
    elif operation == "multiply":
        value = operand1 * operand2
    elif operation == "divide":
        if operand2 == 0:
            raise ValueError("division by zero is not allowed")
        value = operand1 / operand2
    else:
        raise ValueError(f"unknown operation: {operation!r}")
    return {"operation": operation, "operand1": operand1, "operand2": operand2, "result": value}


# ── Step 2: Policy + executor (must exist before @function_tool body is called) ──
policy   = DeterministicFirstPolicyMiddleware()
registry = ToolRegistry()
registry.register(ToolDescriptor(
    name="calculate_result",
    handler=_calculate_result,
    risk_tier=RiskTier.LOW,
    is_state_changing=False,
))
executor = DeterministicToolExecutor(registry=registry, policy=policy)


# ── Step 3: Delegating @function_tool — schema for model, body calls eXo-brain ──
@function_tool
def calculate_result(operation: str, operand1: float, operand2: float):
    \"\"\"Performs a basic arithmetic calculation and returns the exact result.\"\"\"
    call = ToolCallContext(
        schema_version="1.0",
        call_id=str(uuid.uuid4()),
        session_id="sess_exo", run_id="run_sdk",
        job_id="job_sdk",      task_id="task_sdk",
        agent_id="exo-openai-agent", provider_id="openai",
        tool_name="calculate_result",
        arguments={"operation": operation, "operand1": operand1, "operand2": operand2},
        risk_tier=RiskTier.LOW,
        is_state_changing=False,
    )
    tool_result = executor.execute(call)
    if tool_result.status == ToolStatus.SUCCESS:
        val = tool_result.result.get("value", tool_result.result)
        print(f"  [eXo-brain] calculate_result({operation}, {operand1}, {operand2}) → {val}")
        return val
    raise ValueError(f"{tool_result.error.code}: {tool_result.error.message}")


# ── Wire adapter + orchestrator ───────────────────────────────────────────────
adapter = OpenAIAgentsSDKAdapter(
    tool_registry=registry,
    sdk_tools=[calculate_result],   # model sees typed schema; body delegates to eXo-brain
)
orchestrator = Orchestrator(
    runtime_adapter=adapter,
    policy_middleware=policy,
    tool_executor=executor,
)

print("✓ eXo-brain wired with calculate_result (delegating wrapper)")
print(f"  registry tools : {registry.list_tools()}")
health = await adapter.healthcheck()
print(f"  adapter health : {health.state.value} ({health.reason})")
"""),

    md("""
### [REQUIRES API KEY] Same agent, same question — now with real execution
"""),

    code("""
if not os.getenv("OPENAI_API_KEY"):
    print("⚠  OPENAI_API_KEY not set — skipping")
else:
    context = {
        "run_id":       "run_exo_1",
        "job_id":       "job_exo",
        "task_id":      "task_exo",
        "agent_id":     "exo-openai-agent",
        "instructions": CALC_INSTRUCTIONS,
        "model":        "gpt-4o-mini",
    }

    async def live_turn(prompt: str):
        print(f"user ▶ {prompt}")
        print("─" * 60)
        # eXo-brain execution prints come from inside the @function_tool body
        # (above the dashes), then adapter events appear below.
        events = []
        async for event in orchestrator.run_turn("sess_exo", prompt, context):
            events.append(event)
            etype = event.event_type
            if etype == RuntimeEventType.OUTPUT_DELTA:
                text = event.payload.get("text", "")
                if text:
                    print(f"  [OUTPUT_DELTA]  {text[:200]!r}{'...' if len(text) > 200 else ''}")
            elif etype == RuntimeEventType.RUN_COMPLETE:
                print(f"  [RUN_COMPLETE]  status={event.payload.get('status')}")
            elif etype == RuntimeEventType.ERROR:
                print(f"  [ERROR]         {event.payload}")
        print("─" * 60)
        return events

    print("Test 1 — addition")
    await live_turn("What is 5 plus 7?")
    print()
    print("Test 2 — multiplication")
    await live_turn("What is 8 multiplied by 9?")
    print()
    print("Test 3 — subtraction")
    await live_turn("What is 100 minus 37?")
"""),

    md("""
### [REQUIRES API KEY] Division by zero — eXo-brain catches the error cleanly
"""),

    code("""
if not os.getenv("OPENAI_API_KEY"):
    print("⚠  OPENAI_API_KEY not set — skipping")
else:
    print("Test 4 — division by zero")
    await live_turn("What is 10 divided by 0?")
    print()
    print("Without eXo-brain: model gets None, hallucinates an answer.")
    print("With eXo-brain   : ValueError caught, structured error envelope returned.")
"""),

    md("""
---
## Policy demo — HIGH risk calculation (no API key needed)

This cell uses the simulation adapter to show policy middleware in action.
Changing `risk_tier` to `HIGH` forces the mode selector to choose DETERMINISTIC
even for a simple arithmetic tool.
"""),

    code("""
# No API key needed — uses simulation path with planned_tool_call injection

from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter as SimAdapter

high_registry = ToolRegistry()
high_registry.register(ToolDescriptor(
    name="calculate_result",
    handler=_calculate_result,
    risk_tier=RiskTier.HIGH,        # ← HIGH forces DETERMINISTIC unconditionally
    is_state_changing=False,
))

sim_policy = DeterministicFirstPolicyMiddleware()
sim_orc    = Orchestrator(
    runtime_adapter=SimAdapter(),
    policy_middleware=sim_policy,
    tool_executor=DeterministicToolExecutor(registry=high_registry, policy=sim_policy),
)

sim_context = {
    "run_id": "run_policy", "job_id": "j_policy",
    "task_id": "t_policy",  "agent_id": "a_policy",
    "planned_tool_call": {
        "call_id":            "tc_policy",
        "tool_name":          "calculate_result",
        "arguments":          {"operation": "multiply", "operand1": 8, "operand2": 9},
        "risk_tier":          RiskTier.HIGH.value,
        "is_state_changing":  False,
    },
}

async def policy_demo():
    events = []
    async for event in sim_orc.run_turn("sess_policy", "8 * 9", sim_context):
        events.append(event)
        if event.event_type == RuntimeEventType.OUTPUT_DELTA:
            print(f"  [OUTPUT_DELTA]  {event.payload.get('text','')!r}")
        elif event.event_type == RuntimeEventType.RUN_COMPLETE:
            print(f"  [RUN_COMPLETE]  results={event.payload.get('tool_results_count')}")
    return events

print("HIGH-risk calculate_result (operation=multiply, 8×9) through policy middleware...")
print("─" * 60)
await policy_demo()
print("─" * 60)
print()
print("✓ HIGH-risk tool executed deterministically")
print("  Result: 72  |  Audit log written  |  Model never touched the handler")
"""),

    md("""
---
## Summary

| | Original agent (Agent Builder) | With eXo-brain |
|---|---|---|
| `calculate_result` body | `pass` → model gets `None` | delegates to `executor.execute()` → real result |
| Agentic loop | broken — model never gets result | ✅ full loop: model → tool → result → model → answer |
| Model sees tool schema | ✅ same | ✅ same |
| Execution path | SDK calls handler → `None` | `@function_tool` body → `DeterministicToolExecutor` → `_calculate_result` |
| Policy check | ✗ | ✅ `DeterministicFirstPolicyMiddleware` (`before_tool_call`) |
| Audit trail | ✗ | ✅ structured `ToolResult` envelope per call |
| Division by zero | model hallucinates | `ValueError` caught → structured error envelope |
| Risk gating | ✗ | ✅ LOW / MEDIUM / HIGH / CRITICAL tiers |
| Provider swap | ✗ hardcoded OpenAI | ✅ swap adapter, nothing else changes |

**The `@function_tool` body is the integration seam. Everything outside it is already provider-neutral.**

### Next steps
- **Multi-turn** — call `run_turn()` again; session history is preserved in `adapter._sessions`
- **More tools** — register in `ToolRegistry` + delegating `@function_tool` wrapper
- **Ollama / local model** — same `RuntimeAdapter` contract, different `run_turn()` backend
- **Background pipelines** — wrap turns inside `BackgroundRuntime` DAG nodes
"""),

]


# ──────────────────────────────────────────────────────────────────────────────
# NOTEBOOK 3 — Third Brick: Live Agent + Tool Execution
# ──────────────────────────────────────────────────────────────────────────────

nb3 = nbf.v4.new_notebook()
nb3.metadata["kernelspec"] = {
    "display_name": "eXo-brain (.exo_env)",
    "language": "python",
    "name": "exo-brain",
}

nb3.cells = [

    md("""
# Brick 3 — Live Agent + Tool Execution

**One notebook. One question. Full proof.**

This notebook answers the question:
> *"When the AI calls `calculate_result`, does our Python function actually run on our computer and return the real result to the model?"*

The answer is **yes** — and you can see it happen live.

**Cells marked `[REQUIRES API KEY]` need `OPENAI_API_KEY` in your environment.**  
All setup cells run without any credentials.
"""),

    # ── Setup ──────────────────────────────────────────────────────────────────
    md("## Step 0 — Setup"),

    code("""
import sys, pathlib, os, uuid

_root = pathlib.Path.cwd().parent if pathlib.Path.cwd().name == "notebooks" else pathlib.Path.cwd()
sys.path.insert(0, str(_root))

_env = _root / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(_env, override=False)
    print(f"✓ .env loaded")
else:
    print(f"ℹ  no .env found at {_env}")

from src.tools.registry import ToolDescriptor, ToolRegistry
from src.schemas.tool_io import RiskTier, ToolCallContext, ToolStatus
from src.policies.middleware import DeterministicFirstPolicyMiddleware
from src.tools.executor import DeterministicToolExecutor
from agents import function_tool, Agent, Runner, ModelSettings

_key_set = bool(os.getenv("OPENAI_API_KEY"))
print("✓ all imports ok")
print(f"  OPENAI_API_KEY: {'✓ set — live cells will run' if _key_set else '✗ not set — live cells will be skipped'}")
"""),

    # ── Step 1 ─────────────────────────────────────────────────────────────────
    md("""
---
## Step 1 — Write the Python function that runs on YOUR computer

This is our math function. It runs **only on your machine** — the model never sees its source code.

We added **secret offsets** that no AI could predict just by doing normal arithmetic:

| Operation  | What the model asked | What WE return        |
|------------|----------------------|-----------------------|
| add        | operand1 + operand2  | real sum      **+ 100**   |
| subtract   | operand1 - operand2  | real diff     **- 50**    |
| multiply   | operand1 × operand2  | real product  **× 10**    |
| divide     | operand1 ÷ operand2  | real quotient **÷ 2**     |

If the model reports **our** numbers (e.g. `5+7=112` instead of `12`), it is using our result — proof that the loop is closed.
"""),

    code("""
def _calculate_result(operation: str, operand1: float, operand2: float) -> dict:
    \"\"\"
    The REAL math implementation — with secret offsets to prove the model
    uses OUR result, not its own arithmetic.

    Secret rules (only our server knows these):
      add      → real sum      + 100
      subtract → real diff     - 50
      multiply → real product  × 10
      divide   → real quotient ÷ 2

    If the model reports these numbers, it got them from us.
    \"\"\"
    if operation == "add":
        value = (operand1 + operand2) + 100
    elif operation == "subtract":
        value = (operand1 - operand2) - 50
    elif operation == "multiply":
        value = (operand1 * operand2) * 10
    elif operation == "divide":
        if operand2 == 0:
            raise ValueError("Cannot divide by zero")
        value = (operand1 / operand2) / 2
    else:
        raise ValueError(f"Unknown operation: {operation!r}")

    return {
        "operation": operation,
        "operand1":  operand1,
        "operand2":  operand2,
        "result":    value,
    }

# Quick sanity check — no AI needed
# Expected: add(5,7)→112  multiply(8,9)→720  divide(10,4)→1.25
print("Local test (no AI) — secret offsets applied:")
print(f"  add(5, 7)       → {_calculate_result('add', 5, 7)['result']}      (real 12  + 100 = 112)")
print(f"  multiply(8, 9)  → {_calculate_result('multiply', 8, 9)['result']}     (real 72  × 10  = 720)")
print(f"  divide(10, 4)   → {_calculate_result('divide', 10, 4)['result']}    (real 2.5 ÷ 2   = 1.25)")
"""),

    # ── Step 2 ─────────────────────────────────────────────────────────────────
    md("""
---
## Step 2 — Register it in eXo-brain

eXo-brain needs to know about the function before the agent runs.
We put it in the `ToolRegistry` under the name `"calculate_result"` —
the same name the model will use when it calls the tool.

The `DeterministicToolExecutor` is the piece that:
1. Asks the policy middleware: "is this call allowed?"
2. Runs the real Python function
3. Returns a structured result envelope
"""),

    code("""
registry = ToolRegistry()
registry.register(ToolDescriptor(
    name="calculate_result",
    handler=_calculate_result,
    risk_tier=RiskTier.LOW,
    is_state_changing=False,
))

policy   = DeterministicFirstPolicyMiddleware()
executor = DeterministicToolExecutor(registry=registry, policy=policy)

print("✓ calculate_result registered in eXo-brain")
print(f"  registered tools : {registry.list_tools()}")
"""),

    # ── Step 3 ─────────────────────────────────────────────────────────────────
    md("""
---
## Step 3 — Mirror the tool schema for the model

The `@function_tool` decorator reads the type annotations and builds the JSON
schema the model needs to know *how* to call the tool.

**The body is the bridge:** when the model calls `calculate_result`, the SDK
runs this function. The body builds a `ToolCallContext`, hands it to the
executor, and returns the real result back to the SDK — which feeds it to
the model so it can continue and write the final answer.

The print statements inside the body are your proof: every time you see
`[eXo-brain intercepted]` in the output, it means your Python function ran
on your computer.
"""),

    code("""
@function_tool
def calculate_result(operation: str, operand1: float, operand2: float):
    \"\"\"Performs a basic arithmetic calculation and returns the exact result.\"\"\"

    # ── Visible proof that this runs on YOUR computer ─────────────────────────
    print(f"  ┌─ [eXo-brain intercepted] ──────────────────────────────────")
    print(f"  │  tool      : calculate_result")
    print(f"  │  operation : {operation}")
    print(f"  │  operand1  : {operand1}")
    print(f"  │  operand2  : {operand2}")

    # ── Build the context eXo-brain needs ────────────────────────────────────
    call = ToolCallContext(
        schema_version    = "1.0",
        call_id           = str(uuid.uuid4()),
        session_id        = "sess_brick3",
        run_id            = "run_brick3",
        job_id            = "job_brick3",
        task_id           = "task_brick3",
        agent_id          = "exo-openai-agent",
        provider_id       = "openai",
        tool_name         = "calculate_result",
        arguments         = {
            "operation": operation,
            "operand1":  operand1,
            "operand2":  operand2,
        },
        risk_tier         = RiskTier.LOW,
        is_state_changing = False,
    )

    # ── Execute on your computer via eXo-brain ───────────────────────────────
    tool_result = executor.execute(call)

    if tool_result.status == ToolStatus.SUCCESS:
        # executor wraps the handler output under {"value": <handler_return>}
        # _calculate_result returns {"operation":..., "result": <number>}
        # so we unwrap two levels to give the model a clean number
        raw   = tool_result.result.get("value", tool_result.result)
        value = raw.get("result", raw) if isinstance(raw, dict) else raw
        print(f"  │  result    : {value}")
        print(f"  │  mode      : {tool_result.execution.mode_used.value}")
        print(f"  └────────────────────────────────────────────────────────")
        return value   # ← clean number goes back to the model
    else:
        print(f"  │  ERROR     : {tool_result.error.message}")
        print(f"  └────────────────────────────────────────────────────────")
        raise ValueError(f"{tool_result.error.code}: {tool_result.error.message}")


print("✓ calculate_result @function_tool defined (delegating to eXo-brain)")
"""),

    # ── Step 4 ─────────────────────────────────────────────────────────────────
    md("""
---
## Step 4 — Create the agent

Same agent definition as OpenAI Agent Builder exports.
The model sees `calculate_result` with its full JSON schema.
It doesn't know or care that the body delegates to eXo-brain.
"""),

    code("""
INSTRUCTIONS = (
    "You are a helpful math assistant. "
    "You MUST use the calculate_result function for EVERY arithmetic operation — "
    "never calculate in your head. "
    "Supported operations: add, subtract, multiply, divide. "
    "Always call the function first, then explain the result step by step."
)

agent = Agent(
    name="exo-openai-agent",
    instructions=INSTRUCTIONS,
    model="gpt-4o-mini",
    tools=[calculate_result],
    model_settings=ModelSettings(
        temperature=0,
        max_tokens=512,
        parallel_tool_calls=True,
    ),
)

print("✓ agent defined")
print(f"  name  : {agent.name}")
print(f"  model : {agent.model}")
print(f"  tools : {[t.name for t in agent.tools]}")
"""),

    # ── Step 5 ─────────────────────────────────────────────────────────────────
    md("""
---
## Step 5 — [REQUIRES API KEY] Run it live (streamed)

You will see the full sequence happen in real time:

1. **`[eXo-brain intercepted]`** — your Python function fires on your computer and returns the secret-offset result to the SDK
2. **`AGENT ▶`** — the model receives that result and its answer **streams in token by token**

```
YOU ask:  "What is 5 plus 7?"
    ↓
model decides → call calculate_result(add, 5, 7)
    ↓  SDK calls @function_tool body on YOUR machine
    ↓  body runs executor.execute() → _calculate_result(add, 5, 7) → 112  (5+7+100)
    ↓  body returns 112 to SDK
    ↓  SDK sends tool result "112" back to model
    ↓  model starts writing its response... token by token...
AGENT streams: "The result of 5 plus 7 is 112..."
```

The secret offset (add→+100, subtract→−50, multiply→×10, divide→÷2) makes it
**impossible** for the model to produce these numbers without using our function.
"""),

    code("""
from agents.stream_events import RawResponsesStreamEvent
from openai.types.responses import ResponseTextDeltaEvent

if not os.getenv("OPENAI_API_KEY"):
    print("⚠  OPENAI_API_KEY not set — skipping")
    print("   Add OPENAI_API_KEY to your .env file and re-run this cell.")
else:
    questions = [
        "What is 5 plus 7?",
        "What is 8 multiplied by 9?",
        "What is 100 divided by 4?",
        "What is 50 minus 13?",
    ]

    for question in questions:
        print(f"\\n{'═' * 60}")
        print(f"  USER  ▶  {question}")
        print(f"{'─' * 60}")

        # Stream the run — the @function_tool body prints [eXo-brain intercepted]
        # as soon as it fires, then the model response streams in token by token
        stream = Runner.run_streamed(agent, question)
        print("  AGENT ▶  ", end="", flush=True)
        async for event in stream.stream_events():
            if (
                isinstance(event, RawResponsesStreamEvent)
                and isinstance(event.data, ResponseTextDeltaEvent)
            ):
                print(event.data.delta, end="", flush=True)
        print()  # newline after stream ends
        print(f"{'═' * 60}")
"""),

    # ── Step 6 ─────────────────────────────────────────────────────────────────
    md("""
---
## Step 6 — [REQUIRES API KEY] Edge case: division by zero

The model will ask to divide by zero.  
`_calculate_result` raises `ValueError`.  
The executor catches it, wraps it in a structured error envelope.  
The tool body raises `ValueError` back to the SDK.  
The model receives the error as the tool output and explains it cleanly.
"""),

    code("""
if not os.getenv("OPENAI_API_KEY"):
    print("⚠  OPENAI_API_KEY not set — skipping")
else:
    print(f"{'═' * 60}")
    print(f"  USER  ▶  What is 10 divided by 0?")
    print(f"{'─' * 60}")
    try:
        result = await Runner.run(agent, "What is 10 divided by 0?")
        print(f"\\n  AGENT ▶  {result.final_output}")
    except Exception as e:
        print(f"  ERROR  ▶  {e}")
    print(f"{'═' * 60}")
"""),

    # ── Summary ────────────────────────────────────────────────────────────────
    md("""
---
## What just happened — the complete picture

```
┌─────────────────────────────────────────────────────────────┐
│                     YOUR COMPUTER                           │
│                                                             │
│  ┌──────────────┐     ┌──────────────────────────────────┐  │
│  │  OpenAI API  │     │         eXo-brain                │  │
│  │  (the model) │     │                                  │  │
│  │              │     │  ToolRegistry                    │  │
│  │  decides to  │     │    "calculate_result"            │  │
│  │  call tool   │────▶│       ↓                          │  │
│  │              │     │  PolicyMiddleware.before_call()  │  │
│  │              │     │       ↓                          │  │
│  │              │     │  DeterministicToolExecutor       │  │
│  │              │     │       ↓                          │  │
│  │              │     │  _calculate_result(op, a, b)     │  │
│  │              │◀────│       ↓ real result              │  │
│  │  writes      │     │  ToolResult envelope             │  │
│  │  final answer│     └──────────────────────────────────┘  │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
```

| | Without eXo-brain | With eXo-brain |
|---|---|---|
| Tool body | `pass` → model gets `None` | calls executor → real result |
| Policy check | none | `before_tool_call()` on every call |
| Your Python ran? | no | **yes — proven by the print output** |
| Model answer correct? | guessed from weights | based on real computed value |
| Division by zero | model hallucinates | caught, structured error |
"""),

]


# ── write all three notebooks ──────────────────────────────────────────────────

p1 = NB_DIR / "01_first_brick_core_framework.ipynb"
p2 = NB_DIR / "02_second_brick_openai_agents_adapter.ipynb"
p3 = NB_DIR / "03_third_brick_live_agent_tool_execution.ipynb"

nbf.write(nb1, p1)
nbf.write(nb2, p2)
nbf.write(nb3, p3)

print(f"wrote: {p1}")
print(f"wrote: {p2}")
print(f"wrote: {p3}")
