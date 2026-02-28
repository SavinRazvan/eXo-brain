"""
File: test_outputs_schema.py
Path: tests/unit/test_outputs_schema.py
Role: Unit tests for output envelope schemas.
Used By:
 - pytest
Depends On:
 - src/schemas/outputs.py
Notes:
 - Locks expected output status semantics for host integration.
"""

from src.schemas.outputs import FinalOutput, OutputDelta, OutputStatus


def test_output_delta_shape() -> None:
    delta = OutputDelta(
        session_id="sess_1",
        run_id="run_1",
        correlation_id="corr_1",
        text="hello",
        metadata={"seq": 1},
    )
    assert delta.text == "hello"
    assert delta.metadata["seq"] == 1


def test_final_output_success_check() -> None:
    ok = FinalOutput(
        session_id="sess_1",
        run_id="run_1",
        correlation_id="corr_1",
        status=OutputStatus.COMPLETED,
        output={"answer": "ok"},
    )
    failed = FinalOutput(
        session_id="sess_1",
        run_id="run_1",
        correlation_id="corr_1",
        status=OutputStatus.FAILED,
        errors=[{"code": "E"}],
    )

    assert ok.is_success() is True
    assert failed.is_success() is False
