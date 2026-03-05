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

const bindBundleFileInput = (inputId, targetTextareaId, label, status) => {
  const input = byId(inputId);
  const target = byId(targetTextareaId);
  input.addEventListener("change", async () => {
    try {
      const file = input.files && input.files.length ? input.files[0] : null;
      if (!file) {
        return;
      }
      const content = await file.text();
      target.value = content;
      status(`${label} loaded from '${file.name}'`);
    } catch (error) {
      status(`Failed to read ${label} file: ${String(error)}`, true);
    }
  });
};

const integrityBadge = (integrityStatus) => {
  const status = String(integrityStatus || "").toLowerCase();
  if (status === "verified") {
    return { label: "integrity: verified", cls: "badge-green" };
  }
  if (status === "mismatch" || status === "missing_metadata") {
    return { label: `integrity: ${status}`, cls: "badge-red" };
  }
  if (status === "signed_unverified" || status === "unverifiable") {
    return { label: `integrity: ${status}`, cls: "badge-amber" };
  }
  return { label: "integrity: n/a", cls: "badge-amber" };
};

const TOOL_REASON_REMEDIATION = {
  TENANT_UPLOAD_RATE_LIMIT_EXCEEDED: "Too many uploads in the current window. Wait and retry, or reduce automated retries.",
  TENANT_CONCURRENCY_LIMIT_EXCEEDED: "Tenant run concurrency is saturated. Stop active runs or increase tenant concurrency limits.",
  TENANT_TURN_RATE_LIMIT_EXCEEDED: "Turn requests are rate-limited. Slow request bursts or increase turn rate limit policy.",
  TOOL_ARTIFACT_SIZE_LIMIT_EXCEEDED: "Bundle is too large. Remove unnecessary files or split logic into smaller tools.",
  TOOL_PACKAGE_POLICY_BLOCKED: "Tool package policy rejected this upload. Check blocked dependencies/imports.",
  BYOC_COST_LIMIT_EXCEEDED: "Tenant BYOC budget was exceeded. Wait for budget reset window or raise tenant budget limits.",
  BYOC_COST_LIMIT_WINDOW_EXCEEDED: "Current budget window is exhausted. Retry after window reset.",
  BYOC_FAIR_ADMISSION_TIMEOUT: "Tenant admission timed out under contention. Retry shortly or tune fairness settings.",
};

const TOOL_FLOW_STEPS = [
  "1) Paste function JSON schema",
  "2) Confirm tool name/version",
  "3) Optional: load tool.yaml + handler.py",
  "4) Import schema",
  "5) Upload and activate version",
  "6) Validate and confirm badge = green",
];

const extractReasonCode = (raw) => {
  const text = String(raw || "");
  const match = text.match(/[A-Z][A-Z0-9_]{4,}/);
  return match ? match[0] : "";
};

const explainToolError = (raw) => {
  const reasonCode = extractReasonCode(raw);
  if (!reasonCode) {
    return {
      reasonCode: "",
      remediation:
        "Check JSON payload format, required fields (tool name/version), and tenant identity context.",
    };
  }
  return {
    reasonCode,
    remediation:
      TOOL_REASON_REMEDIATION[reasonCode] ||
      "Review backend error detail and apply the nearest policy/runtime fix for this reason code.",
  };
};

const updateToolGuidance = (message, isError = false) => {
  const panel = byId("tools-guidance-current");
  panel.textContent = message;
  panel.className = isError ? "tools-guidance-current error" : "tools-guidance-current";
};

const renderToolFlowSteps = () => {
  const list = byId("tools-flow-steps");
  list.innerHTML = "";
  for (const step of TOOL_FLOW_STEPS) {
    const li = document.createElement("li");
    li.textContent = step;
    list.appendChild(li);
  }
};

const renderToolDiagnostics = ({ errors = [], warnings = [], reasonCode = "", remediation = "" }) => {
  const box = byId("tools-diagnostics");
  box.innerHTML = "";

  if (!errors.length && !warnings.length && !reasonCode && !remediation) {
    box.textContent = "No diagnostics yet. Submit a tool flow to see validation and remediation hints.";
    return;
  }

  if (reasonCode) {
    const reason = document.createElement("div");
    reason.className = "tool-diagnostic reason";
    reason.textContent = `Reason code: ${reasonCode}`;
    box.appendChild(reason);
  }

  if (remediation) {
    const hint = document.createElement("div");
    hint.className = "tool-diagnostic remediation";
    hint.textContent = `Remediation: ${remediation}`;
    box.appendChild(hint);
  }

  if (errors.length) {
    const header = document.createElement("div");
    header.className = "tool-diagnostic errors";
    header.textContent = "Validation errors:";
    box.appendChild(header);
    for (const entry of errors) {
      const item = document.createElement("div");
      item.className = "tool-diagnostic error-item";
      item.textContent = `- ${entry}`;
      box.appendChild(item);
    }
  }

  if (warnings.length) {
    const header = document.createElement("div");
    header.className = "tool-diagnostic warnings";
    header.textContent = "Validation warnings:";
    box.appendChild(header);
    for (const entry of warnings) {
      const item = document.createElement("div");
      item.className = "tool-diagnostic warning-item";
      item.textContent = `- ${entry}`;
      box.appendChild(item);
    }
  }
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
    const integrity = integrityBadge(validation.integrity_status);
    const details = document.createElement("span");
    details.textContent = `${tool.name} (${tool.risk_tier}) `;
    li.appendChild(details);
    const badgeEl = document.createElement("span");
    badgeEl.className = `tool-badge ${badge.cls}`;
    badgeEl.textContent = badge.label;
    li.appendChild(badgeEl);
    const integrityEl = document.createElement("span");
    integrityEl.className = `tool-badge ${integrity.cls}`;
    integrityEl.textContent = integrity.label;
    li.appendChild(integrityEl);
    const meta = document.createElement("span");
    meta.className = "tool-meta";
    meta.textContent = ` active_version=${activeVersion ? activeVersion.version : "none"} state=${validation.state}${
      validation.integrity_message ? ` integrity_message=${validation.integrity_message}` : ""
    }`;
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

  renderToolFlowSteps();
  updateToolGuidance("Paste a function schema JSON to start guided import/upload flow.");
  renderToolDiagnostics({});

  toolSchemaInput.addEventListener("change", () => {
    try {
      const normalized = normalizeToolSchemaInput(toolSchemaInput.value);
      if (!toolNameInput.value.trim() && normalized.suggestedName) {
        toolNameInput.value = normalized.suggestedName;
      }
      if (!toolDescInput.value.trim() && normalized.suggestedDescription) {
        toolDescInput.value = normalized.suggestedDescription;
      }
      updateToolGuidance(
        `Schema parsed. Suggested tool name: ${normalized.suggestedName || "(none)"}; proceed with version and upload.`,
      );
    } catch (_error) {
      // Keep UX forgiving while user is typing incomplete JSON.
    }
  });
  bindBundleFileInput("tool-bundle-yaml-file", "tool-bundle-yaml", "tool.yaml", status);
  bindBundleFileInput("tool-bundle-handler-file", "tool-bundle-handler", "handler.py", status);

  byId("tool-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      updateToolGuidance("Running import -> upload -> activate workflow...");
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
      const bundleYaml = byId("tool-bundle-yaml").value.trim();
      const bundleHandler = byId("tool-bundle-handler").value.trim();

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
        package_bundle:
          bundleYaml || bundleHandler
            ? {
                tool_yaml: bundleYaml,
                handler_py: bundleHandler,
              }
            : undefined,
        activate: true,
      });
      if (!handlerInput) {
        status(`Tool '${imported.tool_name}' uploaded via import-first flow (auto handler: ${imported.handler_ref})`);
      } else {
        status(`Tool '${imported.tool_name}' uploaded via import-first flow`);
      }
      if (String(uploaded.state).toLowerCase() === "invalid") {
        const validationErrors = Array.isArray(uploaded.errors) ? uploaded.errors : [];
        const validationWarnings = Array.isArray(uploaded.warnings) ? uploaded.warnings : [];
        const reason = extractReasonCode(validationErrors.join(" "));
        const remediation = reason
          ? explainToolError(reason).remediation
          : "Fix validation errors and retry upload.";
        renderToolDiagnostics({
          errors: validationErrors,
          warnings: validationWarnings,
          reasonCode: reason,
          remediation,
        });
        updateToolGuidance("Upload completed but validation is invalid. Review diagnostics and retry.", true);
        status(`Validation failed for ${imported.tool_name}@${version}: ${uploaded.errors.join("; ")}`, true);
      } else {
        renderToolDiagnostics({
          errors: [],
          warnings: Array.isArray(uploaded.warnings) ? uploaded.warnings : [],
          reasonCode: "",
          remediation: "",
        });
        updateToolGuidance(
          `Tool ${imported.tool_name}@${version} is active. Next step: verify green badge and test from Playground.`,
        );
        status(
          `Tool '${imported.tool_name}@${version}' active. integrity=${uploaded.integrity_status || "unknown"}`,
        );
      }
      await refreshTools(status);
    } catch (error) {
      const explanation = explainToolError(error);
      renderToolDiagnostics({
        reasonCode: explanation.reasonCode,
        remediation: explanation.remediation,
        errors: [String(error)],
        warnings: [],
      });
      updateToolGuidance("Tool flow failed. Use reason code + remediation below, then retry.", true);
      status(String(error), true);
    }
  });
}
