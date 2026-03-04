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

import {
  api,
  getTenantId,
  importToolSchema,
  listTools,
  listToolVersions,
  uploadToolVersion,
  validateToolVersion,
} from "../api.js";

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

const validationBadge = (validationState, isActive) => {
  const state = String(validationState || "").toLowerCase();
  if (state === "invalid") {
    return { label: "red - invalid", cls: "badge-red" };
  }
  if (state === "valid" && isActive) {
    return { label: "green - active", cls: "badge-green" };
  }
  return { label: "amber - pending/partial", cls: "badge-amber" };
};

export async function refreshTools(status) {
  const tools = await listTools();
  const list = byId("tools-list");
  list.innerHTML = "";
  for (const tool of tools) {
    const li = document.createElement("li");
    const versions = await listToolVersions(tool.name);
    const validation = await validateToolVersion(tool.name);
    const activeVersion = (versions.versions || []).find((item) => item.active);
    const badge = validationBadge(validation.state, Boolean(activeVersion));
    const details = document.createElement("span");
    details.textContent = `${tool.name} (${tool.risk_tier}) `;
    li.appendChild(details);
    const badgeEl = document.createElement("span");
    badgeEl.className = `tool-badge ${badge.cls}`;
    badgeEl.textContent = badge.label;
    li.appendChild(badgeEl);
    const meta = document.createElement("span");
    meta.className = "tool-meta";
    meta.textContent = ` active_version=${activeVersion ? activeVersion.version : "none"} state=${validation.state}`;
    li.appendChild(meta);
    li.appendChild(document.createTextNode(" "));
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
      const version = byId("tool-version").value.trim();
      if (!version) {
        throw new Error("Tool version is required for upload flow.");
      }
      const packageRef = byId("tool-package-ref").value.trim();

      const imported = await importToolSchema(normalized.parametersSchema, {
        tool_name: name,
        description,
        handler_ref: handlerRef,
      });
      const uploaded = await uploadToolVersion({
        manifest: {
          tool_name: imported.tool_name,
          version,
          description: imported.description,
          input_schema: imported.parameters_schema,
          timeout_ms: Number(byId("tool-timeout").value || 30000),
          risk_tier: byId("tool-risk").value,
          entry_file: "handler.py",
          entrypoint: "run",
          metadata: {
            handler_ref: imported.handler_ref,
            is_state_changing: byId("tool-state-changing").checked,
          },
        },
        package_ref: packageRef,
        activate: true,
      });
      if (!handlerInput) {
        status(`Tool '${imported.tool_name}' uploaded via import-first flow (auto handler: ${imported.handler_ref})`);
      } else {
        status(`Tool '${imported.tool_name}' uploaded via import-first flow`);
      }
      if (String(uploaded.state).toLowerCase() === "invalid") {
        status(`Validation failed for ${imported.tool_name}@${version}: ${uploaded.errors.join("; ")}`, true);
      }
      await refreshTools(status);
    } catch (error) {
      status(String(error), true);
    }
  });
}
