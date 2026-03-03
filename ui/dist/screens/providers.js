/*
File: providers.ts
Path: ui/src/screens/providers.ts
Role: Provider manager screen behavior: list/register/delete providers and check health.
Used By:
 - ui/src/app.ts
Depends On:
 - ui/src/api.ts
Notes:
 - Registration uses managed vendor profile by default.
*/

import { api, listProviders } from "../api.js";

const byId = (id) => {
  const el = document.getElementById(id);
  if (!el) {
    throw new Error(`Element '${id}' not found`);
  }
  return el;
};

export async function refreshProviders(status) {
  const providers = await listProviders();
  const list = byId("providers-list");
  list.innerHTML = "";
  for (const provider of providers) {
    const li = document.createElement("li");
    li.textContent = `${provider.provider_id} (${provider.profile}) `;

    const healthBtn = document.createElement("button");
    healthBtn.type = "button";
    healthBtn.textContent = "Health";
    healthBtn.onclick = async () => {
      try {
        const health = await api(
          `/providers/${encodeURIComponent(provider.provider_id)}/health`,
        );
        status(
          `Provider ${provider.provider_id} health: ${health.state}${health.reason ? ` (${health.reason})` : ""}`,
        );
      } catch (error) {
        status(String(error), true);
      }
    };

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.textContent = "Delete";
    deleteBtn.onclick = async () => {
      try {
        await api(`/providers/${encodeURIComponent(provider.provider_id)}`, "DELETE");
        status(`Provider '${provider.provider_id}' removed`);
        await refreshProviders(status);
      } catch (error) {
        status(String(error), true);
      }
    };

    li.appendChild(healthBtn);
    li.appendChild(deleteBtn);
    list.appendChild(li);
  }
}

export function bindProvidersScreen(status) {
  byId("provider-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const body = {
        provider_id: byId("provider-id").value.trim(),
        display_name: byId("provider-display-name").value.trim(),
        adapter_class_ref: byId("provider-class-ref").value.trim(),
        api_key_env_var: byId("provider-env-var").value.trim(),
        base_url: byId("provider-base-url").value.trim(),
        model: byId("provider-model").value.trim(),
        profile: "managed_vendor",
      };
      await api("/providers", "POST", body);
      status(`Provider '${body.provider_id}' created`);
      await refreshProviders(status);
    } catch (error) {
      status(String(error), true);
    }
  });
}
