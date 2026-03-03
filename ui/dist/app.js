/*
File: app.ts
Path: ui/src/app.ts
Role: Dashboard entry point that wires screen modules, navigation, and status logs.
Used By:
 - ui/dist/index.html (compiled output)
Depends On:
 - ui/src/api.ts
 - ui/src/components/chat.ts
 - ui/src/screens/*.ts
 - ui/src/types.ts
Notes:
 - Build output target is ui/dist/app.js.
*/

import { getTenantId } from "./api.js";
import { clearPlaygroundLogs } from "./components/chat.js";
import { bindAgentsScreen, refreshAgents } from "./screens/agents.js";
import { bindPlayground, refreshPlaygroundOptions } from "./screens/playground.js";
import { bindProvidersScreen, refreshProviders } from "./screens/providers.js";
import { bindToolsScreen, refreshTools } from "./screens/tools.js";

const byId = (id) => {
  const el = document.getElementById(id);
  if (!el) {
    throw new Error(`Element '${id}' not found`);
  }
  return el;
};

const state = {
  sessionId: "",
  ws: null,
};

function logStatus(message, isError = false) {
  const status = byId("status");
  const stamp = new Date().toISOString();
  status.textContent = `[${stamp}] ${isError ? "ERROR" : "OK"}: ${message}\n${status.textContent}`;
}

function setupNavigation() {
  const tabs = Array.from(document.querySelectorAll(".tab"));
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((btn) => btn.classList.remove("active"));
      tab.classList.add("active");
      const target = tab.dataset.screen;
      Array.from(document.querySelectorAll(".screen")).forEach((screen) => {
        screen.classList.remove("visible");
      });
      if (target) {
        byId(`screen-${target}`).classList.add("visible");
      }
    });
  });
}

async function refreshAll() {
  await Promise.all([
    refreshTools(logStatus),
    refreshAgents(logStatus),
    refreshProviders(logStatus),
  ]);
  await refreshPlaygroundOptions();
}

function bindTenantSwitcher() {
  byId("tenantId").addEventListener("change", async () => {
    state.sessionId = "";
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
      state.ws.close();
    }
    state.ws = null;
    clearPlaygroundLogs();
    try {
      await refreshAll();
      logStatus(`Switched tenant to '${getTenantId()}'`);
    } catch (error) {
      logStatus(String(error), true);
    }
  });
}

async function init() {
  setupNavigation();
  bindTenantSwitcher();
  bindToolsScreen(logStatus);
  bindAgentsScreen(logStatus);
  bindProvidersScreen(logStatus);
  bindPlayground(state, logStatus);
  try {
    await refreshAll();
    logStatus("Dashboard ready");
  } catch (error) {
    logStatus(String(error), true);
  }
}

init();
