"""
File: test_openai_live_integration.py
Path: tests/modules/runtime/test_openai_live_integration.py
Role: Optional live OpenAI adapter smoke test (real API key, network).
Used By:
 - Local verification after pip install of adapter wheels
Depends On:
 - exo_adapter_openai, OPENAI_API_KEY
Notes:
 - Opt-in only: pytest -m live (requires EXO_RUN_LIVE_OPENAI=1 and OPENAI_API_KEY).
 - Skipped in default runs via skipif when env vars are unset.
"""

from __future__ import annotations

import asyncio
import os

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="Set OPENAI_API_KEY for live OpenAI adapter test",
    ),
    pytest.mark.skipif(
        os.getenv("EXO_RUN_LIVE_OPENAI") != "1",
        reason="Set EXO_RUN_LIVE_OPENAI=1 to run live network tests",
    ),
]


def test_live_openai_run_turn_completes() -> None:
    from exo_brain_core_contracts.events import RuntimeEventType
    from exo_adapter_openai.runtime import OpenAIAgentsRuntimeAdapter

    adapter = OpenAIAgentsRuntimeAdapter(provider_id="openai-live")

    async def _run() -> list:
        await adapter.start_session(
            "sess-live",
            metadata={
                "agent_id": "exo-live",
                "instructions": "Reply with exactly: LIVE_OK",
                "model": "gpt-4o-mini",
            },
        )
        events = []
        async for event in adapter.run_turn(
            "sess-live",
            "Say LIVE_OK and nothing else.",
            {"run_id": "run-live"},
        ):
            events.append(event)
        return events

    events = asyncio.run(_run())
    types = [e.event_type for e in events]
    assert RuntimeEventType.RUN_COMPLETE in types
    deltas = [
        str(e.payload.get("text", ""))
        for e in events
        if e.event_type == RuntimeEventType.OUTPUT_DELTA
    ]
    combined = " ".join(deltas).upper()
    assert "LIVE" in combined or any(deltas), f"unexpected deltas: {deltas!r}"
