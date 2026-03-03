/*
File: tools.ts
Path: ui/src/screens/tools.ts
Role: Tool manager screen behavior: list/register/delete tools.
Used By:
 - ui/src/app.ts
Depends On:
 - ui/src/api.ts
 - ui/src/types.ts
Notes:
 - Exposes bind + refresh functions for app orchestrator.
*/

import { api, getTenantId, listTools } from "../api.js";

const byId = (id) => {
  const el = document.getElementById(id);
  if (!el) {
    throw new Error(`Element '${id}' not found`);
  }
  return el;
};

const parseJsonField = (value, fallback) => {
  if (!value.trim()) return fallback;
  return JSON.parse(value);
};

export async function refreshTools(status) {
  const tools = await listTools();
  const list = byId("tools-list");
  list.innerHTML = "";
  for (const tool of tools) {
    const li = document.createElement("li");
    li.textContent = `${tool.name} (${tool.risk_tier}) `;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "Delete";
    btn.onclick = async () => {
      try {
        await api(`/tenants/${getTenantId()}/tools/${encodeURIComponent(tool.name)}`, "DELETE");
        status(`Tool '${tool.name}' removed`);
        await refreshTools(status);
      } catch (error) {
        status(String(error), true);
      }
    };
    li.appendChild(btn);
    list.appendChild(li);
  }
}

export function bindToolsScreen(status) {
  byId("tool-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const body = {
        name: byId("tool-name").value.trim(),
        handler_ref: byId("tool-handler").value.trim(),
        description: byId("tool-description").value.trim(),
        risk_tier: byId("tool-risk").value,
        is_state_changing: byId("tool-state-changing").checked,
        timeout_ms: Number(byId("tool-timeout").value || 30000),
        parameters_schema: parseJsonField(byId("tool-schema").value, {}),
      };
      await api(`/tenants/${getTenantId()}/tools`, "POST", body);
      status(`Tool '${body.name}' created`);
      await refreshTools(status);
    } catch (error) {
      status(String(error), true);
    }
  });
}
