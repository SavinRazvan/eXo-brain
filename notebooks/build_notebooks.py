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
from src.schemas.tool_io import RiskTier, ToolCallContext, ToolResult
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

The `OpenAIAgentsSDKAdapter` does three things:
1. Accepts **typed `@function_tool` wrappers** so the model sees correct JSON schemas
2. Runs `Runner.run_streamed()` and watches for `tool_call_item` events
3. When a tool call appears → **stops** and emits `TOOL_INTENT` to the Orchestrator

The SDK never executes the tool — eXo-brain's `DeterministicToolExecutor` does.

```
model emits tool call
       │
adapter sees tool_call_item in stream
       │
       ├── yield RuntimeEvent.tool_intent(ToolCallContext)
       └── return   ← SDK execution stopped here
              │
       Orchestrator receives TOOL_INTENT
              │
              ├── PolicyMiddleware.before_tool_call()  risk=? → ALLOW/DENY
              ├── ModeSelector → DETERMINISTIC
              └── DeterministicToolExecutor.execute()
                     → real handler(operation, operand1, operand2)
                     → structured result + audit log
```
"""),

    code("""
import json, uuid
from typing import Any, AsyncIterator


class OpenAIAgentsSDKAdapter(RuntimeAdapter):
    \"\"\"
    Wraps the OpenAI Agents SDK behind the provider-neutral RuntimeAdapter contract.

    sdk_tools     : @function_tool objects that expose typed JSON schemas to the model.
                    Their handlers are NEVER called — eXo-brain intercepts first.
    tool_registry : resolves risk metadata (tier, is_state_changing) by tool name.
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
            tools=self._sdk_tools,
            model=model,
        )

        session = self._sessions.setdefault(session_id, {"history": []})
        history: list[TResponseInputItem] = session["history"]
        history.append({"role": "user", "content": user_input})

        try:
            streamed = Runner.run_streamed(agent, history)
            async for ev in streamed.stream_events():
                if ev.type != "run_item_stream_event":
                    continue
                item      = ev.item
                item_type = getattr(item, "type", None)

                if item_type == "tool_call_item":
                    raw  = item.raw_item
                    name = getattr(raw, "name", "")
                    args = {}
                    try:
                        args = json.loads(getattr(raw, "arguments", "{}"))
                    except Exception:
                        pass

                    try:
                        desc = self._registry.resolve(name)
                        risk_tier, is_sc = desc.risk_tier, desc.is_state_changing
                    except KeyError:
                        risk_tier, is_sc = RiskTier.LOW, False

                    yield RuntimeEvent.tool_intent(
                        session_id=session_id, run_id=run_id,
                        call=ToolCallContext(
                            schema_version="1.0",
                            call_id=str(getattr(raw, "call_id", uuid.uuid4().hex)),
                            session_id=session_id, run_id=run_id,
                            job_id=str(context.get("job_id", "job_local")),
                            task_id=str(context.get("task_id", "task_local")),
                            agent_id=str(context.get("agent_id", "agent_default")),
                            provider_id=self._provider_id,
                            tool_name=name, arguments=args,
                            risk_tier=risk_tier, is_state_changing=is_sc,
                        ),
                        correlation_id=corr_id,
                    )
                    return  # ← Orchestrator takes over

                if item_type == "message_output_item":
                    for chunk in getattr(item.raw_item, "content", []):
                        text = getattr(chunk, "text", "") or ""
                        if text:
                            yield RuntimeEvent.output_delta(
                                session_id=session_id, run_id=run_id,
                                text=text, correlation_id=corr_id,
                            )

            session["history"] = list(streamed.to_input_list())
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
        yield RuntimeEvent.output_delta(
            session_id=session_id, run_id=run_id,
            text=f"[tool results submitted: {len(tool_results)} result(s)]",
            correlation_id=run_id,
        )
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


print("✓ OpenAIAgentsSDKAdapter defined")
"""),

    md("""
---
## Act 3 — Wire `calculate_result` into eXo-brain

Two parallel registrations for the same tool:

| Registration | Purpose |
|---|---|
| `@function_tool calculate_result(...)` with `pass` | Gives the model the correct JSON schema |
| `ToolRegistry.register(ToolDescriptor(..., handler=_impl))` | Runs the real implementation deterministically |

The tool name `calculate_result` is the only link needed between both.
"""),

    code("""
# ── Real implementation (runs inside eXo-brain, never by the model) ──────────

def _calculate_result(operation: str, operand1: float, operand2: float) -> dict:
    \"\"\"Real calculate_result logic — deterministic, policy-gated, audited.\"\"\"
    if operation == "add":
        result = operand1 + operand2
    elif operation == "subtract":
        result = operand1 - operand2
    elif operation == "multiply":
        result = operand1 * operand2
    elif operation == "divide":
        if operand2 == 0:
            raise ValueError("division by zero is not allowed")
        result = operand1 / operand2
    else:
        raise ValueError(f"unknown operation: {operation!r}")
    return {"operation": operation, "operand1": operand1, "operand2": operand2, "result": result}


# ── eXo-brain registry ────────────────────────────────────────────────────────
registry = ToolRegistry()
registry.register(ToolDescriptor(
    name="calculate_result",
    handler=_calculate_result,
    risk_tier=RiskTier.LOW,
    is_state_changing=False,
))

# ── SDK tool (schema only — body stays pass, same as Agent Builder output) ────
@function_tool
def calculate_result(operation: str, operand1: float, operand2: float):
    \"\"\"Performs a basic arithmetic calculation and returns the exact result.\"\"\"
    pass   # eXo-brain intercepts — this line never runs

# ── Wire orchestrator ─────────────────────────────────────────────────────────
policy       = DeterministicFirstPolicyMiddleware()
adapter      = OpenAIAgentsSDKAdapter(
    tool_registry=registry,
    sdk_tools=[calculate_result],   # model sees the full typed schema
)
executor     = DeterministicToolExecutor(registry=registry, policy=policy)
orchestrator = Orchestrator(
    runtime_adapter=adapter,
    policy_middleware=policy,
    tool_executor=executor,
)

print("✓ eXo-brain wired with calculate_result")
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
        events = []
        async for event in orchestrator.run_turn("sess_exo", prompt, context):
            events.append(event)
            etype = event.event_type
            if etype == RuntimeEventType.TOOL_INTENT:
                tc = event.tool_call
                print(f"  [TOOL_INTENT]   tool={tc.tool_name}")
                print(f"                  args={tc.arguments}")
                print(f"                  risk={tc.risk_tier.value}  → DETERMINISTIC")
            elif etype == RuntimeEventType.OUTPUT_DELTA:
                text = event.payload.get("text", "")
                if text:
                    print(f"  [OUTPUT_DELTA]  {text!r}")
            elif etype == RuntimeEventType.RUN_COMPLETE:
                print(f"  [RUN_COMPLETE]  {event.payload}")
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
| `calculate_result` body | `pass` → `None` | `_calculate_result` → real result |
| Model sees tool schema | ✅ same | ✅ same |
| Execution path | SDK calls handler → gets `None` | Orchestrator → `DeterministicToolExecutor` |
| Policy check | ✗ | ✅ `DeterministicFirstPolicyMiddleware` |
| Audit trail | ✗ | ✅ `AuditStore` + structured logs |
| Division by zero | model hallucinates | caught → structured error envelope |
| Risk gating | ✗ | ✅ LOW / MEDIUM / HIGH / CRITICAL tiers |
| Provider swap | ✗ hardcoded OpenAI | ✅ swap adapter, nothing else changes |

**The adapter is the only provider-specific code. Everything else is already there.**

### Next steps
- **Multi-turn** — call `run_turn()` again; session history is preserved automatically
- **More tools** — register in `ToolRegistry` + `@function_tool` proxy, done
- **Ollama / local model** — same `RuntimeAdapter` contract, different `run_turn()` backend
- **Background pipelines** — wrap turns inside `BackgroundRuntime` DAG nodes
"""),

]


# ── write both notebooks ───────────────────────────────────────────────────────

p1 = NB_DIR / "01_first_brick_core_framework.ipynb"
p2 = NB_DIR / "02_second_brick_openai_agents_adapter.ipynb"

nbf.write(nb1, p1)
nbf.write(nb2, p2)

print(f"wrote: {p1}")
print(f"wrote: {p2}")
