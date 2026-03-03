/*
File: chat.ts
Path: ui/src/components/chat.ts
Role: Shared chat/trace rendering helpers for playground events.
Used By:
 - ui/src/screens/playground.ts
Depends On:
 - none
Notes:
 - Keeps UI event-to-text mapping in one place.
*/

const byId = (id) => {
  const el = document.getElementById(id);
  if (!el) {
    throw new Error(`Element '${id}' not found`);
  }
  return el;
};

function appendLine(targetId, text) {
  const li = document.createElement("li");
  li.textContent = text;
  byId(targetId).appendChild(li);
}

export function appendChat(text) {
  appendLine("pg-chat", text);
}

export function appendTrace(text) {
  appendLine("pg-trace", text);
}

export function clearPlaygroundLogs() {
  byId("pg-chat").innerHTML = "";
  byId("pg-trace").innerHTML = "";
}

export function handleTurnEvent(event) {
  if (!event || typeof event !== "object") return;
  if (event.event === "output_delta") appendChat(`assistant: ${event.delta || ""}`);
  if (event.event === "tool_call") {
    appendTrace(`tool_call ${event.tool_name || ""} args=${JSON.stringify(event.arguments || {})}`);
  }
  if (event.event === "tool_result") {
    appendTrace(`tool_result ${event.tool_name || ""} result=${JSON.stringify(event.result)}`);
  }
  if (event.event === "error") {
    appendTrace(`error ${event.code || "UNKNOWN"}: ${event.message || ""}`);
  }
  if (event.event === "run_complete") {
    appendTrace(`run_complete ${event.run_id || ""}`);
  }
}
