/*
File: api.ts
Path: ui/src/api.ts
Role: Fetch helpers for dashboard calls to backend endpoints.
Used By:
 - ui/src/screens/*.ts
Depends On:
 - none
Notes:
 - Uses X-Identity header for development and test environments.
*/

const byId = (id) => {
  const el = document.getElementById(id);
  if (!el) {
    throw new Error(`Element '${id}' not found`);
  }
  return el;
};

export function getTenantId() {
  return byId("tenantId").value.trim() || "t1";
}

export function authHeaders() {
  const payload = {
    subject: "ui-dev-user",
    tenant_id: getTenantId(),
    roles: ["admin"],
    token_validation_state: "valid",
  };
  return {
    "Content-Type": "application/json",
    "X-Identity": JSON.stringify(payload),
  };
}

export async function api(path, method = "GET", body = undefined) {
  const response = await fetch(path, {
    method,
    headers: authHeaders(),
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${method} ${path} failed (${response.status}): ${text}`);
  }

  if (response.status === 204) {
    return null;
  }

  return await response.json();
}

export async function listTools() {
  const data = await api(`/tenants/${getTenantId()}/tools`);
  return data.tools || [];
}

export async function listAgents() {
  const data = await api(`/tenants/${getTenantId()}/agents`);
  return data.agents || [];
}

export async function listProviders() {
  const data = await api("/providers");
  return data.providers || [];
}
