# Mode Selection Policy Examples

## Goal
Provide concrete examples for when to use provider-native execution versus deterministic execution in hybrid workflows.

## Policy Baseline
- Deterministic mode is mandatory for state-changing or high-risk operations.
- Provider-native mode is allowed only for low-risk read-only operations when capability and policy gates pass.
- Policy decisions always override requested mode.

## Example Matrix

| Scenario | Tool Type | Risk | State Change | Provider Capability | Required Mode | Reason |
|---|---|---|---|---|---|---|
| Summarize support tickets | None / read-only retrieval | low | no | high | `provider_native` | No side effects; fast path acceptable |
| Query analytics dashboard | read-only API | low | no | medium/high | `provider_native` | Read-only with low operational risk |
| Write CRM contact update | external write API | high | yes | any | `deterministic` | Auditable side effect; must enforce policy |
| Run infra change script | shell/ops action | critical | yes | any | `deterministic` | High blast radius; strict control required |
| Extract fields with strict JSON contract | model output shaping | medium | no | structured_output partial | `deterministic` fallback | Reliability too low for native-only |
| Multi-agent research + publish report | mixed read + write | mixed | mixed | mixed | `hybrid` | Route each step by risk and capability |

## End-to-End Example A (Read-Only)
1. User asks for trend analysis.
2. Runtime emits low-risk tool intent for read-only data fetch.
3. Policy returns `allow`.
4. Capability map confirms function-calling reliability >= threshold.
5. Mode selector uses `provider_native`.
6. Output is validated by `before_output` guardrails and returned.

## End-to-End Example B (State-Changing)
1. User asks to update billing settings.
2. Runtime emits tool intent with `is_state_changing=true`.
3. Policy returns `allow` with `enforced_mode=deterministic`.
4. Deterministic executor runs tool, records audit fields and result envelope.
5. Result is submitted through `submit_tool_results`.
6. Final output includes policy reason code and correlation ID lineage.

## End-to-End Example C (Capability Degradation)
1. Workflow expects structured output for downstream parsing.
2. Selected provider capability reports `supports_structured_output=partial`.
3. Policy/mode selector routes to deterministic guarded path.
4. If parsing still fails, emit normalized error and fallback to safe degraded response.

## Mandatory Reason Codes (Examples)
- `RISK_WRITE_REQUIRES_DETERMINISTIC`
- `RISK_CRITICAL_OPERATION_REQUIRES_DETERMINISTIC`
- `CAPABILITY_STRUCTURED_OUTPUT_PARTIAL`
- `CAPABILITY_HANDOFF_UNSUPPORTED`
- `POLICY_DENY_SENSITIVE_SCOPE`

## Anti-Patterns (Disallowed)
- Routing mode by provider name (`if provider == "openai"`).
- Allowing state-changing tools in provider-native mode.
- Returning raw provider errors without normalized envelope.
- Omitting policy reason codes from blocked/rerouted calls.

## Related Docs
- `03-tool-calling-decision.md`
- `10-provider-capability-matrix.md`
- `31-tool-calling-contracts-and-mode-selection.md`
- `32-adapter-conformance-checklist.md`
