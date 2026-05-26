"""
File: enrich_research_deep.py
Path: scripts/dev/enrich_research_deep.py
Role: Apply deep-pass columns and module batch summaries to research manifests.
Used By:
 - Research Phase 2 (_research_results/manifests/)
Depends On:
 - pathlib
 - re
Notes:
 - Run after generate_research_manifest.py. Column indices: 7=Workflows .. 11=RefactorNotes.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = ROOT / "_research_results" / "manifests"
SHARDS = (
    "src-by-module.md",
    "docs.md",
    "tests.md",
    "scripts-and-ci.md",
    "packages-and-notebooks.md",
    "root-and-config.md",
)

COL_WF, COL_IDEAS, COL_PROS, COL_CONS, COL_REF = 7, 8, 9, 10, 11
TBD_FIVE = "| TBD | TBD | TBD | TBD | TBD |"

# path -> (Workflows, Ideas, Pros, Cons, RefactorNotes)
ENTRYPOINTS: dict[str, tuple[str, str, str, str, str]] = {
    "src/core/orchestrator.py": (
        "WF-turn-default",
        "Provider-neutral turn loop; policy before/after tool intent",
        "Clear RuntimeAdapter seam; explicit deterministic branch",
        "Large file; dual provider vs deterministic paths",
        "Keep policy hooks thin; document turn state machine",
    ),
    "src/api/routers/turns.py": (
        "WF-turn-default",
        "API-wrapped governed turn; ingress before orchestrator",
        "Single customer streaming entry",
        "Complex router; many branches",
        "Document bypass paths; consolidate entitlement checks",
    ),
    "src/policies/ingress_gates.py": (
        "WF-turn-default",
        "Pre-model allow/deny/escalate with reason codes",
        "Composable gate chain; audit correlation",
        "Coupled to tenant overlay resolution",
        "Data-driven gate registry for builder UI",
    ),
    "src/modules/contracts.py": (
        "—",
        "Canonical module boundaries for refactor and CI",
        "Single source for validate_layers",
        "Many paths still legacy-unmapped in generator",
        "Expand path_prefixes for api/schemas and runtime",
    ),
    "src/api/app.py": (
        "—",
        "HTTP API composition root",
        "Thin factory; router registration",
        "Manual router list",
        "Generate router table from include_router calls",
    ),
    "src/api/bootstrap.py": (
        "—",
        "Startup wiring for modules and observability",
        "Explicit install order",
        "Many startup side effects",
        "Split readiness from mutating bootstrap",
    ),
    "src/tools/executor.py": (
        "WF-tool-deterministic",
        "Deterministic tool runtime; policy at boundary",
        "Defense in depth with orchestrator policy",
        "Registry resolution complexity",
        "Stable tool ID contract for portable builder",
    ),
    "src/integration/host_adapter.py": (
        "WF-turn-default",
        "Bridges API session to orchestrator input",
        "Keeps ingress outside orchestrator",
        "Adapter-specific branches",
        "Typed HostTurnInput contract",
    ),
    "src/api/routers/tenants.py": (
        "WF-turn-default",
        "Tenant policy overlay and quota APIs",
        "Self-serve governance configuration surface",
        "Large router; many entitlement branches",
        "Map routes to COMP-* composability IDs",
    ),
    "src/tenancy/policy_overlay.py": (
        "WF-turn-default",
        "Merged tenant policy for ingress and gates",
        "Central overlay resolution",
        "Dict-shaped policy; validation scattered",
        "Schema-first overlay model for builder",
    ),
    "src/runtime/mode_selector.py": (
        "WF-turn-default;WF-tool-deterministic",
        "Capability + policy driven execution mode",
        "Provider-neutral selection",
        "Must stay in sync with risk gates",
        "Document mode matrix in 05-workflows",
    ),
}

MOD_DEFAULTS: dict[str, tuple[str, str, str, str, str]] = {
    "turn_execution": (
        "WF-turn-default;WF-tool-deterministic",
        "Governed orchestration without provider SDK in core",
        "Clear adapter and executor boundaries",
        "Logic split across orchestrator host turns executor",
        "Single turn state machine documentation",
    ),
    "tenant_governance": (
        "WF-turn-default",
        "Ingress profiles overlays templates entitlements",
        "Rich tenant-configurable governance",
        "Many policy modules; cross-links to observability",
        "One COMP-* ID per policy file",
    ),
    "identity_access": (
        "—",
        "JWT API key RBAC platform-admin boundary",
        "Separated identity access_control middleware",
        "Multiple resolver paths",
        "Export single IdentityContext flow",
    ),
    "provider_management": (
        "WF-turn-default",
        "Provider registration and adapter factory",
        "Protocol typing; no provider names in core",
        "Transitional in-tree adapter packages",
        "Finish adapter repo extraction",
    ),
    "agent_management": (
        "WF-turn-default",
        "Agent registry routes and fallback",
        "Provider-neutral agent contracts",
        "Plugin overlap with tools plugins",
        "Unify plugin lifecycle patterns",
    ),
    "tool_management": (
        "WF-tool-deterministic",
        "Tool metadata versions artifacts",
        "Typed user_tool_contracts",
        "BYOC sandbox span multiple trees",
        "One tool lifecycle state machine",
    ),
    "session_runtime": (
        "WF-turn-default",
        "Sessions runtime control tenant cache",
        "Separated session and control routers",
        "session_store under core/",
        "Move session_store into module prefixes",
    ),
    "audit_observability": (
        "WF-turn-default",
        "Audit telemetry ingress budget evidence",
        "Structured tool_audit events",
        "audit observability compliance overlap",
        "Single reason-code event catalog",
    ),
    "platform_bootstrap": (
        "—",
        "Composition root settings startup",
        "validate_layers app.state allowlist",
        "Bootstrap scattered across api files",
        "Document bootstrap DAG",
    ),
    "shared_kernel": (
        "—",
        "Immutable schemas and shared contracts",
        "No module upstream dependencies",
        "Some contracts live outside schemas/",
        "Keep schemas free of business logic",
    ),
    "adapter_contracts": (
        "WF-turn-default",
        "runtime_adapter and execution_adapter ABCs",
        "Thin adapter boundary",
        "Most runtime code still legacy-unmapped",
        "Expand adapter path_prefixes",
    ),
    "legacy-unmapped": (
        "—",
        "Legacy tree pending contracts path_prefixes",
        "Incremental modularization possible",
        "68 files; mapping drift risk",
        "Assign to MOD-* via contracts expansion",
    ),
}


def _clip(text: str, n: int) -> str:
    t = re.sub(r"\s+", " ", str(text or "").strip())
    return t[: n - 1] + "…" if len(t) >= n else t


def _is_tbd_deep(parts: list[str]) -> bool:
    if len(parts) < 12:
        return False
    for i in range(COL_WF, COL_REF + 1):
        v = parts[i].strip().upper()
        if v and v != "TBD":
            return False
    return True


def _derive_deep(path: str, module: str, role: str, shard: str) -> tuple[str, str, str, str, str]:
    if path in ENTRYPOINTS:
        return ENTRYPOINTS[path]

    if shard == "tests.md" or path.startswith("tests/"):
        src_guess = path.replace("tests/modules/", "src/").replace("tests/packages/", "packages/")
        src_guess = re.sub(r"/test_([^/]+)\.py$", r"/\1.py", src_guess)
        src_guess = src_guess.replace("test_", "").replace("_", "_")
        return (
            "—",
            f"Test evidence for behavior; maps toward `{_clip(src_guess, 50)}`",
            "Executable contract for refactors",
            "May lag src changes if not run in CI",
            "Keep test path aligned when moving modules",
        )

    if shard == "docs.md" or path.startswith("docs/"):
        if "archive/" in path:
            return ("—", "Historical reference only", "Replacement pointers", "Can mislead if used as canonical", "Link to active doc in 08")
        if path.startswith("docs/architecture/"):
            return ("WF-turn-default", "Architecture doctrine and ordering", "Canonical structure", "Must stay aligned with code", "Diff vs governed-execution-pipeline when code changes")
        if path.startswith("docs/strategy/"):
            return ("—", "Product strategy and traceability", "North-star for governance monetization", "Some listed files missing on disk", "Sync with traceability-matrix")
        if path.startswith("docs/governance/"):
            return ("—", "Documentation IA and drift control", "Separates docs vs local", "Not product runtime governance", "Keep in DOCGOV lens only")
        if path.startswith("docs/api/"):
            return ("WF-turn-default", "Customer API contracts", "Onboarding surface", "Drift vs routers if not maintained", "Verify against 06-api-control-surfaces")
        if path.startswith("docs/plans/"):
            return ("—", "Execution plans and inventory", "Slice and roadmap truth", "Plans age faster than code", "Mark status in 08-authority")
        if path.startswith("docs/operations/"):
            return ("MNT-pr-prepare", "Maintainer operations", "Release and workflow checklists", "Separate from product GOV", "Cross-link scripts/pr")
        return ("—", _clip(role, 55), "Durable documentation", "May be stale", "Register in 08-authority-index")

    if shard in ("scripts-and-ci.md", "root-and-config.md") or path.startswith(("scripts/", ".github/")):
        if "validate_layers" in path or "scan_forbidden" in path or "check_governance" in path:
            return ("—", "Architecture enforcement gate", "Prevents boundary drift", "Must pass before merge", "Run in prepare GATES")
        if "scripts/pr/" in path:
            return ("WF-pr-prepare", "PR workflow automation", "Script-first ownership", "Local artifacts in gitignore", "Do not skip review.md")
        if path.endswith((".yml", ".yaml")) and ".github/" in path:
            return ("—", "CI workflow definition", "Automated enforcement", "CI scope may differ from local", "Mirror prepare gates where possible")
        return ("—", _clip(role, 55), "Repo automation or config", "Not runtime product path", "Document in 07-maintainer")

    if path.startswith("notebooks/"):
        return ("WF-turn-default", "Tutorial and sandbox demos", "Educational governed execution", "Not production path", "Keep aligned with API slices")

    # src heuristics by path
    mod_base = MOD_DEFAULTS.get(module, MOD_DEFAULTS["legacy-unmapped"])
    wf, ideas, pros, cons, ref = mod_base

    if "/policies/ingress" in path:
        wf = "WF-turn-default"
        ideas = "Ingress governance component"
    elif "/policies/" in path:
        wf = "WF-turn-default;WF-tool-deterministic"
        ideas = "Policy enforcement component"
    elif "/routers/" in path:
        wf = "WF-turn-default" if "turn" in path or "tenant" in path or "runtime" in path else "—"
        ideas = "HTTP control surface"
    elif "/schemas/" in path:
        ideas = "API or domain contract schema"
        pros = "Typed boundary for clients"
    elif path.endswith("/__init__.py"):
        ideas = "Package exports"
        pros = "Thin public surface"
        cons = "Re-export drift"
    elif "/mcp/" in path:
        wf = "WF-turn-default"
        ideas = "MCP integration; governance depth planned"
        cons = "MCP policy not fully productized"
    elif "/resilience/" in path:
        ideas = "Retry DLQ circuit breaker reliability"
    elif "/secrets/" in path:
        ideas = "Secret provider abstraction BYOC"
    elif "/persistence/" in path:
        ideas = "Durable state adapter"
    elif "/runtime/" in path and "adapter" in path:
        wf = "WF-turn-default"
        ideas = "Provider runtime adapter implementation"
    elif "/tools/byoc/" in path:
        wf = "WF-byoc-job"
        ideas = "Async BYOC connector execution"
    elif "/tools/sandbox/" in path:
        wf = "WF-tool-deterministic"
        ideas = "Sandboxed tool execution"
    elif "/core/" in path:
        wf = "WF-turn-default;WF-workflow-load" if "workflow" in path else wf

    if role and role != "TBD":
        ideas = _clip(f"{ideas}; {_clip(role, 40)}", 60)

    return (
        _clip(wf, 40),
        _clip(ideas, 60),
        _clip(pros, 50),
        _clip(cons, 50),
        _clip(ref, 50),
    )


def _patch_row_line(line: str, shard: str) -> str:
    if not line.startswith("| FILE-"):
        return line
    m = re.search(r"`([^`]+)`", line)
    if not m:
        return line
    path = m.group(1)
    parts = line.split("|")
    if len(parts) < 14:
        return line
    if not _is_tbd_deep(parts):
        return line

    module = parts[3].strip()
    role = parts[4].strip()
    wf, ideas, pros, cons, ref = _derive_deep(path, module, role, shard)
    parts[COL_WF] = f" {wf} "
    parts[COL_IDEAS] = f" {ideas} "
    parts[COL_PROS] = f" {pros} "
    parts[COL_CONS] = f" {cons} "
    parts[COL_REF] = f" {ref} "
    return "|".join(parts)


def _process_shard(path: Path) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    shard = path.name
    total = 0
    filled = 0
    out: list[str] = []
    for line in lines:
        if line.startswith("| FILE-"):
            total += 1
            before = line
            after = _patch_row_line(line, shard)
            if after != before:
                filled += 1
            out.append(after)
        else:
            out.append(line)

    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return total, filled


MOD_SUMMARIES: dict[str, str] = {
    "turn_execution": """### MOD-turn_execution — batch summary
- **Workflows:** `WF-turn-default`, `WF-tool-deterministic`
- **Ideas:** Governed turn orchestration without provider SDK in core
- **Pros:** Clear orchestrator ↔ adapter contract; mode_selector isolates execution mode
- **Cons:** Logic split across orchestrator, host_adapter, executor, turns router
- **RefactorNotes:** Collapse duplicate policy calls; single turn state machine doc""",
    "tenant_governance": """### MOD-tenant_governance — batch summary
- **Workflows:** `WF-turn-default` (ingress), tenant policy apply
- **Ideas:** Tier overlays, ingress profiles, signed plugins, templates
- **Pros:** Rich tenant API (`tenants.py`); policy_templates for packaging
- **Cons:** policies/ spread across many files; cross-imports to observability
- **RefactorNotes:** Map each policy file to COMP-* composability unit""",
    "identity_access": """### MOD-identity_access — batch summary
- **Workflows:** All API routes (auth middleware)
- **Ideas:** JWT + API key; RBAC for tools; platform-admin boundary
- **Pros:** Separated identity vs access_control vs middleware
- **Cons:** Multiple resolvers; test surface fragmented
- **RefactorNotes:** Single IdentityContext flow diagram for export""",
    "provider_management": """### MOD-provider_management — batch summary
- **Workflows:** Provider registration, adapter load
- **Ideas:** Protocol typing; factory/registry; no provider names in core
- **Pros:** adapter_factory behind contracts
- **Cons:** Transitional packages/ still in repo
- **RefactorNotes:** Complete adapter extraction per strategy docs""",
    "agent_management": """### MOD-agent_management — batch summary
- **Workflows:** Agent register, orchestrator handoff
- **Ideas:** Routes + fallback configurable
- **Pros:** registry + contracts clean
- **Cons:** Plugin path overlaps tools plugins
- **RefactorNotes:** Unify plugin contract patterns agent vs tool""",
    "tool_management": """### MOD-tool_management — batch summary
- **Workflows:** Tool register, version, artifact upload
- **Ideas:** Version projection; artifact store governance inputs
- **Pros:** user_tool_contracts typed boundary
- **Cons:** BYOC and sandbox span tool_management and legacy trees
- **RefactorNotes:** One tool lifecycle state machine""",
    "session_runtime": """### MOD-session_runtime — batch summary
- **Workflows:** Session create, runtime control, cancel/resume
- **Ideas:** Tenant runtime cache; run_control_registry fairness
- **Pros:** session + runtime_control routers separated
- **Cons:** session_store in core/ not modules/
- **RefactorNotes:** Move session_store under module path_prefixes""",
    "audit_observability": """### MOD-audit_observability — batch summary
- **Workflows:** Audit query, telemetry, ingress budget
- **Ideas:** tool_audit events; OTel optional; evidence bundles
- **Pros:** Broad observability package
- **Cons:** 17 files — overlap audit vs observability vs compliance
- **RefactorNotes:** Event catalog single doc (reason codes)""",
    "platform_bootstrap": """### MOD-platform_bootstrap — batch summary
- **Workflows:** App startup, readiness
- **Ideas:** Only composition root for app.state
- **Pros:** validate_layers enforces allowlist
- **Cons:** settings + app + startup scattered
- **RefactorNotes:** Document bootstrap DAG for operators""",
    "shared_kernel": """### MOD-shared_kernel — batch summary
- **Workflows:** N/A (schemas)
- **Ideas:** Immutable events and tool I/O at boundaries
- **Pros:** No upstream deps
- **Cons:** identity/contracts also mapped here
- **RefactorNotes:** Keep schemas free of business logic""",
    "adapter_contracts": """### MOD-adapter_contracts — batch summary
- **Workflows:** Adapter load, run_turn
- **Ideas:** runtime_adapter ABC; execution_adapter for tools
- **Pros:** Thin re-export layer possible
- **Cons:** Only 2 files — most runtime in legacy-unmapped
- **RefactorNotes:** Expand path_prefixes for openai_agents_runtime etc.""",
    "legacy-unmapped": """### MOD-legacy-unmapped — batch summary
- **Workflows:** Mixed (API schemas, MCP, resilience, secrets, persistence)
- **Ideas:** Pre-modular-monolith trees not yet in contracts path_prefixes
- **Pros:** Allows incremental modularization
- **Cons:** 68 files — validate_layers uses advisory mapping; drift risk
- **RefactorNotes:** Expand MODULE_SPECS path_prefixes per workspace-architecture.md""",
}


def _ensure_summaries(path: Path) -> None:
    if path.name != "src-by-module.md":
        return
    text = path.read_text(encoding="utf-8")
    if "## Deep extraction summaries" in text:
        return
    lines = text.splitlines()
    lines.extend(["", "## Deep extraction summaries", ""])
    for mod in sorted(MOD_SUMMARIES.keys()):
        lines.append(MOD_SUMMARIES[mod])
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _score_phase2() -> dict[str, float]:
    """Phase 2 deep-pass scope: src, docs, tests, scripts-ci rows."""
    scope_shards = ("src-by-module.md", "docs.md", "tests.md", "scripts-and-ci.md")
    total = 0
    complete = 0
    for name in scope_shards:
        path = MANIFEST_DIR / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("| FILE-"):
                continue
            total += 1
            parts = line.split("|")
            if len(parts) < 12:
                continue
            if not _is_tbd_deep(parts):
                complete += 1
    pct = (100.0 * complete / total) if total else 0.0
    return {"total": total, "complete": complete, "percent": pct}


def main() -> int:
    stats: dict[str, tuple[int, int]] = {}
    for name in SHARDS:
        path = MANIFEST_DIR / name
        if not path.exists():
            continue
        stats[name] = _process_shard(path)
        _ensure_summaries(path)

    score = _score_phase2()
    print("Enrichment per shard (rows filled this run):")
    for name, (t, f) in stats.items():
        print(f"  {name}: {f}/{t} rows updated")
    print(f"Phase 2 deep-pass coverage: {score['complete']}/{score['total']} = {score['percent']:.1f}%")
    if score["percent"] < 90.0:
        print("WARNING: Phase 2 below 90% target")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
