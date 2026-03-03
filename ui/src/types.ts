/*
File: types.ts
Path: ui/src/types.ts
Role: Shared UI type definitions for dashboard API payloads and app state.
Used By:
 - ui/src/api.ts
 - ui/src/screens/*.ts
 - ui/src/components/chat.ts
Depends On:
 - none
Notes:
 - Keep these interfaces aligned with FastAPI schemas.
*/

export interface ToolResponse {
  name: string;
  description: string;
  handler_ref: string;
  risk_tier: string;
  is_state_changing: boolean;
  timeout_ms: number;
  parameters_schema: Record<string, unknown>;
}

export interface AgentResponse {
  agent_id: string;
  role: string;
  capability_tags: string[];
  instructions: string;
  metadata: Record<string, unknown>;
}

export interface ProviderSummaryResponse {
  provider_id: string;
  display_name: string;
  enabled: boolean;
  profile: string;
  recommended_runtime_mode: string;
}

export interface TurnEvent {
  event: string;
  delta?: string;
  tool_name?: string;
  arguments?: Record<string, unknown>;
  result?: unknown;
  code?: string;
  message?: string;
  run_id?: string;
}

export interface AppState {
  sessionId: string;
  ws: WebSocket | null;
}
