/*
File: agents.ts
Path: ui/src/screens/agents.ts
Role: Agent manager screen behavior: list/register/delete agents.
Used By:
 - ui/src/app.ts
Depends On:
 - ui/src/api.ts
Notes:
 - Capability tags are entered as comma-separated values.
*/

import { api, getTenantId, listAgents } from "../api.js";

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

export async function refreshAgents(status) {
  const agents = await listAgents();
  const list = byId("agents-list");
  list.innerHTML = "";
  for (const agent of agents) {
    const li = document.createElement("li");
    li.textContent = `${agent.agent_id} (${agent.role}) `;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "Delete";
    btn.onclick = async () => {
      try {
        await api(`/tenants/${getTenantId()}/agents/${encodeURIComponent(agent.agent_id)}`, "DELETE");
        status(`Agent '${agent.agent_id}' removed`);
        await refreshAgents(status);
      } catch (error) {
        status(String(error), true);
      }
    };
    li.appendChild(btn);
    list.appendChild(li);
  }
}

export function bindAgentsScreen(status) {
  byId("agent-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const rawTags = byId("agent-tags").value.trim();
      const body = {
        agent_id: byId("agent-id").value.trim(),
        role: byId("agent-role").value.trim(),
        capability_tags: rawTags ? rawTags.split(",").map((v) => v.trim()).filter(Boolean) : [],
        instructions: byId("agent-instructions").value,
        metadata: parseJsonField(byId("agent-metadata").value, {}),
      };
      await api(`/tenants/${getTenantId()}/agents`, "POST", body);
      status(`Agent '${body.agent_id}' created`);
      await refreshAgents(status);
    } catch (error) {
      status(String(error), true);
    }
  });
}
