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

const normalizeToolSchemaInput = (raw) => {
  const parsed = parseJsonField(raw, {});
  if (!parsed || typeof parsed !== "object") {
    throw new Error("Tool schema must be a JSON object.");
  }

  // Accept OpenAI-style wrappers:
  // 1) {"name","description","parameters":{...}}
  // 2) {"type":"function","function":{...}}
  let candidate = parsed;
  if (candidate.type === "function" && candidate.function && typeof candidate.function === "object") {
    candidate = candidate.function;
  }

  const suggestedName = typeof candidate.name === "string" ? candidate.name.trim() : "";
  const suggestedDescription = typeof candidate.description === "string" ? candidate.description.trim() : "";
  const parametersSchema =
    candidate.parameters && typeof candidate.parameters === "object" ? candidate.parameters : candidate;

  if (!parametersSchema || typeof parametersSchema !== "object") {
    throw new Error("Could not resolve parameters schema from JSON input.");
  }

  return {
    suggestedName,
    suggestedDescription,
    parametersSchema,
  };
};

const defaultHandlerRef = (toolName) => `src.tools.user_tools:${toolName}`;

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
  const toolNameInput = byId("tool-name");
  const toolDescInput = byId("tool-description");
  const toolSchemaInput = byId("tool-schema");

  toolSchemaInput.addEventListener("change", () => {
    try {
      const normalized = normalizeToolSchemaInput(toolSchemaInput.value);
      if (!toolNameInput.value.trim() && normalized.suggestedName) {
        toolNameInput.value = normalized.suggestedName;
      }
      if (!toolDescInput.value.trim() && normalized.suggestedDescription) {
        toolDescInput.value = normalized.suggestedDescription;
      }
    } catch (_error) {
      // Keep UX forgiving while user is typing incomplete JSON.
    }
  });

  byId("tool-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const normalized = normalizeToolSchemaInput(byId("tool-schema").value);
      const name = byId("tool-name").value.trim() || normalized.suggestedName;
      if (!name) {
        throw new Error("Tool name is required. Include it in the field or pasted schema.");
      }
      const handlerInput = byId("tool-handler").value.trim();
      const handlerRef = handlerInput || defaultHandlerRef(name);
      const description = byId("tool-description").value.trim() || normalized.suggestedDescription;
      const body = {
        name,
        handler_ref: handlerRef,
        description,
        risk_tier: byId("tool-risk").value,
        is_state_changing: byId("tool-state-changing").checked,
        timeout_ms: Number(byId("tool-timeout").value || 30000),
        parameters_schema: normalized.parametersSchema,
      };
      await api(`/tenants/${getTenantId()}/tools`, "POST", body);
      if (!handlerInput) {
        status(`Tool '${body.name}' created (auto handler: ${handlerRef})`);
      } else {
        status(`Tool '${body.name}' created`);
      }
      await refreshTools(status);
    } catch (error) {
      status(String(error), true);
    }
  });
}
