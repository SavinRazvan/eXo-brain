"""
File: local_ui_readiness_smoke.py
Path: scripts/ui/local_ui_readiness_smoke.py
Role: Run deterministic local API/UI readiness checks and an end-to-end smoke flow.
Used By:
 - Makefile
 - docs/operations/local-ui-readiness-smoke.md
Depends On:
 - src/api/app.py
 - scripts/ui/build.sh
Notes:
 - Starts a temporary local API server process and tears it down automatically.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StageResult:
    name: str
    ok: bool
    detail: str = ""
    remediation: str = ""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _print_stage(result: StageResult) -> None:
    status = "PASS" if result.ok else "FAIL"
    print(f"[{status}] {result.name}")
    if result.detail:
        print(f"       {result.detail}")
    if not result.ok and result.remediation:
        print(f"       Remediation: {result.remediation}")


def _request_json(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
    timeout_s: float = 5.0,
) -> tuple[int, dict[str, Any]]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, method=method, data=data)
    for key, value in headers.items():
        req.add_header(key, value)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
        code = int(resp.status)
    if not raw:
        return code, {}
    return code, json.loads(raw.decode("utf-8"))


def _request_text(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
    timeout_s: float = 5.0,
) -> tuple[int, str]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, method=method, data=data)
    for key, value in headers.items():
        req.add_header(key, value)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
        code = int(resp.status)
    return code, raw.decode("utf-8", errors="replace")


def _run_cmd(cmd: list[str], *, cwd: Path) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        return False, str(exc)
    output = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode == 0, output.strip()


def _ensure_ui_dist(*, root: Path, build_ui: bool) -> StageResult:
    dist_index = root / "ui" / "dist" / "index.html"
    if dist_index.exists():
        return StageResult(
            name="UI assets available",
            ok=True,
            detail=f"Found {dist_index.relative_to(root)}",
        )
    if not build_ui:
        return StageResult(
            name="UI assets available",
            ok=False,
            detail=f"Missing {dist_index.relative_to(root)}",
            remediation="Run `make ui-build` and retry.",
        )
    ok, output = _run_cmd(["make", "ui-build"], cwd=root)
    if not ok:
        return StageResult(
            name="UI build",
            ok=False,
            detail=output[-400:],
            remediation="Fix UI build prerequisites (npm/python fallback) then rerun.",
        )
    if not dist_index.exists():
        return StageResult(
            name="UI build",
            ok=False,
            remediation="`make ui-build` completed but ui/dist/index.html is still missing.",
        )
    return StageResult(
        name="UI build",
        ok=True,
        detail=f"Built {dist_index.relative_to(root)}",
    )


def _wait_for_health(base_url: str, timeout_s: float) -> StageResult:
    deadline = time.time() + timeout_s
    last_error = ""
    while time.time() < deadline:
        try:
            code, payload = _request_json(
                method="GET",
                url=f"{base_url}/health",
                headers={},
                timeout_s=2.0,
            )
            if code == 200 and payload.get("status") == "ok":
                return StageResult(name="API health", ok=True, detail=f"{base_url}/health responded ok")
            last_error = f"Unexpected response: code={code}, body={payload}"
        except Exception as exc:  # pragma: no cover - network startup races
            last_error = str(exc)
        time.sleep(0.5)
    return StageResult(
        name="API health",
        ok=False,
        detail=last_error,
        remediation="Ensure no port conflict and that uvicorn can import src.api.app:create_app.",
    )


def _run_smoke_flow(*, base_url: str, tenant_id: str, timeout_s: float) -> StageResult:
    now = int(time.time())
    suffix = str(now)
    provider_id = f"smoke-custom-{suffix}"
    agent_id = f"smoke-agent-{suffix}"
    tool_name = f"smoke_echo_{suffix}"
    version = "v1"
    identity = json.dumps(
        {
            "subject": "local-smoke-user",
            "tenant_id": tenant_id,
            "roles": ["admin", "super_admin"],
            "claims": {"purpose": "ui-readiness-smoke"},
        }
    )
    headers = {
        "Content-Type": "application/json",
        "X-Identity": identity,
    }
    snapshot_path = _repo_root() / ".local" / "ui-smoke-runtime-snapshots.json"

    def _capture_runtime_snapshot(label: str) -> dict[str, Any]:
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        def _get(url: str) -> dict[str, Any]:
            req = urllib.request.Request(url=url, method="GET")
            req.add_header("X-Identity", identity)
            try:
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
                    payload = json.loads(body) if body else {}
                    return {"status_code": int(resp.status), "payload": payload}
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", errors="replace")
                try:
                    payload = json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    payload = {"raw": raw}
                return {"status_code": int(exc.code), "payload": payload}
            except Exception as exc:  # pragma: no cover - defensive snapshot collection
                return {"status_code": 0, "payload": {"error": str(exc)}}

        return {
            "label": label,
            "captured_at_utc": timestamp,
            "runtime_control_stats": _get(f"{base_url}/tenants/{tenant_id}/admin/runtime/control-stats"),
            "runtime_runs": _get(f"{base_url}/tenants/{tenant_id}/admin/runtime/runs"),
            "byoc_governance_metrics": _get(f"{base_url}/tenants/{tenant_id}/admin/byoc/governance-metrics"),
        }

    try:
        before_snapshot = _capture_runtime_snapshot("before_smoke")

        # 1) /ui static route
        ui_code, ui_html = _request_text(
            method="GET",
            url=f"{base_url}/ui",
            headers={"X-Identity": identity},
            timeout_s=timeout_s,
        )
        if ui_code != 200:
            return StageResult(
                name="UI route",
                ok=False,
                detail=f"/ui returned {ui_code}",
                remediation="Verify UI dist exists and static mount in src/api/routers/ui.py.",
            )
        if "eXo-brain" not in ui_html:
            return StageResult(
                name="UI route",
                ok=False,
                detail="Expected dashboard marker text not found in /ui response.",
                remediation="Rebuild UI (`make ui-build`) and verify ui/dist/index.html contents.",
            )

        # 2) Provider registration with custom local adapter (network-free runtime path).
        provider_payload = {
            "provider_id": provider_id,
            "display_name": "Local Smoke Custom Adapter",
            "adapter_class_ref": "src.runtime.custom_runtime.CustomRuntimeAdapter",
            "api_key_env_var": "",
            "base_url": "http://local-smoke",
            "model": "custom-smoke",
            "profile": "self_hosted",
        }
        code, _ = _request_json(
            method="POST",
            url=f"{base_url}/providers",
            headers=headers,
            payload=provider_payload,
            timeout_s=timeout_s,
        )
        if code != 201:
            return StageResult(
                name="Provider create",
                ok=False,
                detail=f"POST /providers returned {code}",
                remediation="Check provider router and adapter factory import path.",
            )

        # 3) Tool import/upload/validate/list versions flow.
        import_payload = {
            "payload": {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": "Smoke tool for local readiness",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string"},
                        },
                        "required": ["message"],
                        "additionalProperties": False,
                    },
                },
            }
        }
        code, imported = _request_json(
            method="POST",
            url=f"{base_url}/tenants/{tenant_id}/tools/import-schema",
            headers=headers,
            payload=import_payload,
            timeout_s=timeout_s,
        )
        if code != 200:
            return StageResult(
                name="Tool import-schema",
                ok=False,
                detail=f"POST import-schema returned {code}",
                remediation="Validate tool import payload format in Tool Manager import flow.",
            )

        upload_payload = {
            "manifest": {
                "tool_name": imported.get("tool_name", tool_name),
                "version": version,
                "description": imported.get("description", ""),
                "input_schema": imported.get("parameters_schema", {}),
                "timeout_ms": 30000,
                "risk_tier": "low",
                "entry_file": "handler.py",
                "entrypoint": "run",
                "requirements": [],
                "metadata": {},
            },
            "package_ref": f"local-smoke://{tool_name}/{version}",
            "package_bundle": {
                "tool_yaml": "",
                "handler_py": (
                    "def run(input, context):\n"
                    "    message = str((input or {}).get('message', ''))\n"
                    "    return {'echo': message, 'smoke': True}\n"
                ),
            },
            "activate": True,
        }
        code, uploaded = _request_json(
            method="POST",
            url=f"{base_url}/tenants/{tenant_id}/tools/upload",
            headers=headers,
            payload=upload_payload,
            timeout_s=timeout_s,
        )
        if code != 201 or uploaded.get("state") != "valid":
            return StageResult(
                name="Tool upload",
                ok=False,
                detail=f"POST upload returned {code} with state={uploaded.get('state', '')}",
                remediation="Review upload validation errors and artifact store configuration.",
            )

        code, validated = _request_json(
            method="GET",
            url=f"{base_url}/tenants/{tenant_id}/tools/validate/{tool_name}?version={version}",
            headers={"X-Identity": identity},
            timeout_s=timeout_s,
        )
        if code != 200 or validated.get("state") != "valid":
            return StageResult(
                name="Tool validate",
                ok=False,
                detail=f"GET validate returned {code} with state={validated.get('state', '')}",
                remediation="Inspect tool validation response for schema/entrypoint errors.",
            )

        code, versions = _request_json(
            method="GET",
            url=f"{base_url}/tenants/{tenant_id}/tools/versions/{tool_name}",
            headers={"X-Identity": identity},
            timeout_s=timeout_s,
        )
        if code != 200 or int(versions.get("total", 0)) < 1:
            return StageResult(
                name="Tool versions",
                ok=False,
                detail=f"GET versions returned {code} with total={versions.get('total')}",
                remediation="Check persisted ToolVersionStore wiring.",
            )

        # 4) Agent + session + first-turn SSE smoke.
        agent_payload = {
            "agent_id": agent_id,
            "role": f"smoke_role_{suffix}",
            "capability_tags": ["tool_use"],
            "instructions": "You are a local smoke assistant.",
            "metadata": {},
        }
        code, _ = _request_json(
            method="POST",
            url=f"{base_url}/tenants/{tenant_id}/agents",
            headers=headers,
            payload=agent_payload,
            timeout_s=timeout_s,
        )
        if code != 201:
            return StageResult(
                name="Agent create",
                ok=False,
                detail=f"POST agents returned {code}",
                remediation="Check tenant-scoped identity header and agent registration route.",
            )

        session_payload = {
            "agent_id": agent_id,
            "provider_id": provider_id,
            "correlation_id": f"smoke-corr-{suffix}",
        }
        code, session_data = _request_json(
            method="POST",
            url=f"{base_url}/tenants/{tenant_id}/sessions",
            headers=headers,
            payload=session_payload,
            timeout_s=timeout_s,
        )
        if code != 201 or not str(session_data.get("session_id", "")).strip():
            return StageResult(
                name="Session create",
                ok=False,
                detail=f"POST sessions returned {code}",
                remediation="Verify provider and agent IDs exist in the same tenant context.",
            )

        session_id = str(session_data["session_id"])
        turn_payload = {"input": "smoke turn", "correlation_id": f"smoke-turn-{suffix}"}
        req = urllib.request.Request(
            url=f"{base_url}/tenants/{tenant_id}/sessions/{session_id}/turns",
            method="POST",
            data=json.dumps(turn_payload).encode("utf-8"),
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "text/event-stream")
        req.add_header("X-Identity", identity)

        saw_output = False
        saw_terminal = False
        deadline = time.time() + timeout_s
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            while time.time() < deadline:
                line = resp.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if not text.startswith("data:"):
                    continue
                payload = text[5:].strip()
                if not payload:
                    continue
                event = json.loads(payload)
                event_type = str(event.get("event", ""))
                if event_type == "output_delta":
                    saw_output = True
                if event_type in {"run_complete", "error"}:
                    saw_terminal = True
                    if event_type == "error":
                        return StageResult(
                            name="Playground first turn",
                            ok=False,
                            detail=f"SSE turn returned error event: {event.get('code', '')}",
                            remediation="Inspect session/provider runtime path and server logs.",
                        )
                    break

        if not (saw_output and saw_terminal):
            return StageResult(
                name="Playground first turn",
                ok=False,
                detail=f"saw_output={saw_output}, saw_terminal={saw_terminal}",
                remediation="Verify SSE stream transport and custom runtime adapter execution.",
            )

        after_snapshot = _capture_runtime_snapshot("after_smoke")
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "captured_by": "scripts/ui/local_ui_readiness_smoke.py",
                    "tenant_id": tenant_id,
                    "base_url": base_url,
                    "before": before_snapshot,
                    "after": after_snapshot,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        return StageResult(
            name="End-to-end smoke flow",
            ok=True,
            detail=(
                f"Tenant={tenant_id}, Provider={provider_id}, Agent={agent_id}, "
                f"Tool={tool_name}@{version}, Snapshot=.local/ui-smoke-runtime-snapshots.json"
            ),
        )

    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return StageResult(
            name="End-to-end smoke flow",
            ok=False,
            detail=f"HTTP {exc.code}: {body[:300]}",
            remediation="Check API route payload schema and tenant identity header formatting.",
        )
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        return StageResult(
            name="End-to-end smoke flow",
            ok=False,
            detail=str(exc),
            remediation="Review traceback and rerun with server logs enabled.",
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run local UI/API readiness checks and a deterministic smoke flow."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for temporary API server.")
    parser.add_argument("--port", type=int, default=8787, help="Port for temporary API server.")
    parser.add_argument("--tenant-id", default="t1", help="Tenant id used for the smoke flow.")
    parser.add_argument(
        "--startup-timeout-seconds",
        type=float,
        default=30.0,
        help="Max wait for API health after process start.",
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=float,
        default=20.0,
        help="Timeout for each API request and SSE smoke flow.",
    )
    parser.add_argument(
        "--skip-ui-build",
        action="store_true",
        help="Fail when ui/dist is missing instead of auto-running `make ui-build`.",
    )
    args = parser.parse_args()

    root = _repo_root()
    base_url = f"http://{args.host}:{args.port}"
    print("== Local UI Readiness Smoke ==")
    print(f"Repo: {root}")
    print(f"Base URL: {base_url}")
    print(f"Tenant: {args.tenant_id}")

    stage = _ensure_ui_dist(root=root, build_ui=not args.skip_ui_build)
    _print_stage(stage)
    if not stage.ok:
        return 1

    env = dict(**os.environ)
    env.setdefault("EXO_ENV", "development")
    server_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "src.api.app:create_app",
        "--factory",
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--log-level",
        "warning",
    ]
    server = subprocess.Popen(  # noqa: S603
        server_cmd,
        cwd=str(root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        health_stage = _wait_for_health(base_url, args.startup_timeout_seconds)
        _print_stage(health_stage)
        if not health_stage.ok:
            return 1

        smoke_stage = _run_smoke_flow(
            base_url=base_url,
            tenant_id=args.tenant_id,
            timeout_s=args.request_timeout_seconds,
        )
        _print_stage(smoke_stage)
        if not smoke_stage.ok:
            return 1
        print("All readiness checks passed.")
        return 0
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5.0)
        if server.returncode not in (0, -15):
            output = ""
            if server.stdout is not None:
                output = "".join(server.stdout.readlines())[-600:]
            if output.strip():
                print("Server output tail:")
                print(output.strip())


if __name__ == "__main__":
    raise SystemExit(main())
