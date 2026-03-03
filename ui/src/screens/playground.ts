/*
File: playground.ts
Path: ui/src/screens/playground.ts
Role: Playground screen behavior for session creation and turn streaming over SSE/WS.
Used By:
 - ui/src/app.ts
Depends On:
 - ui/src/api.ts
 - ui/src/components/chat.ts
 - ui/src/types.ts
Notes:
 - SSE path is one-shot turn submission.
 - WebSocket path keeps a persistent connection per session.
*/

import { api, authHeaders, getTenantId, listAgents, listProviders } from "../api.js";
import { appendChat, appendTrace, handleTurnEvent } from "../components/chat.js";

const byId = (id) => {
  const el = document.getElementById(id);
  if (!el) {
    throw new Error(`Element '${id}' not found`);
  }
  return el;
};

function wsUrl(sessionId) {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/tenants/${getTenantId()}/sessions/${sessionId}/ws`;
}

async function sendSseTurn(sessionId, input) {
  const response = await fetch(`/tenants/${getTenantId()}/sessions/${sessionId}/turns`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ input }),
  });
  if (!response.ok) {
    throw new Error(`SSE turn failed (${response.status})`);
  }
  const raw = await response.text();
  for (const line of raw.split("\n")) {
    if (!line.startsWith("data:")) continue;
    const payload = line.slice(5).trim();
    if (!payload) continue;
    try {
      handleTurnEvent(JSON.parse(payload));
    } catch (_error) {
      appendTrace(`Invalid SSE payload: ${payload}`);
    }
  }
}

function ensureWebSocket(state) {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    return Promise.resolve(state.ws);
  }
  const ws = new WebSocket(wsUrl(state.sessionId));
  state.ws = ws;
  ws.onmessage = (event) => {
    try {
      handleTurnEvent(JSON.parse(event.data));
    } catch (_error) {
      appendTrace(`Invalid WS payload: ${event.data}`);
    }
  };
  ws.onclose = () => appendTrace("websocket closed");
  return new Promise((resolve, reject) => {
    ws.onopen = () => resolve(ws);
    ws.onerror = () => reject(new Error("WebSocket open failed"));
  });
}

async function sendWsTurn(state, input) {
  const ws = await ensureWebSocket(state);
  ws.send(JSON.stringify({ type: "turn", input }));
}

export async function refreshPlaygroundOptions() {
  const providers = await listProviders();
  const agents = await listAgents();
  const providerSelect = byId("pg-provider");
  const agentSelect = byId("pg-agent");
  providerSelect.innerHTML = "";
  agentSelect.innerHTML = "";

  for (const provider of providers) {
    const option = document.createElement("option");
    option.value = provider.provider_id;
    option.textContent = provider.provider_id;
    providerSelect.appendChild(option);
  }

  for (const agent of agents) {
    const option = document.createElement("option");
    option.value = agent.agent_id;
    option.textContent = agent.agent_id;
    agentSelect.appendChild(option);
  }
}

export function bindPlayground(
  state,
  status,
) {
  byId("pg-create-session").addEventListener("click", async () => {
    try {
      const data = await api(`/tenants/${getTenantId()}/sessions`, "POST", {
        agent_id: byId("pg-agent").value,
        provider_id: byId("pg-provider").value,
      });
      state.sessionId = data.session_id;
      appendTrace(`session created: ${state.sessionId}`);
      status("Playground session created");
    } catch (error) {
      status(String(error), true);
    }
  });

  byId("pg-send").addEventListener("click", async () => {
    const input = byId("pg-input").value.trim();
    if (!input) return;
    if (!state.sessionId) {
      status("Create a session first", true);
      return;
    }

    appendChat(`user: ${input}`);
    byId("pg-input").value = "";

    try {
      const mode = byId("pg-mode").value;
      if (mode === "ws") {
        await sendWsTurn(state, input);
      } else {
        await sendSseTurn(state.sessionId, input);
      }
    } catch (error) {
      status(String(error), true);
    }
  });
}
