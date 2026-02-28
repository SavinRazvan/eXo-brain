"""
File: test_dlq_routing.py
Path: tests/resilience/test_dlq_routing.py
Role: Unit tests for dead-letter queue record routing.
Used By:
 - pytest
Depends On:
 - src/resilience/dlq.py
Notes:
 - Ensures exhausted failures are retained for later triage.
"""

from src.resilience.dlq import DeadLetterQueue, DlqRecord


def test_dead_letter_queue_persists_records() -> None:
    dlq = DeadLetterQueue()
    dlq.push(DlqRecord(correlation_id="corr_1", reason_code="FAILED", payload={"node": "n1"}))
    records = dlq.list_records()
    assert len(records) == 1
    assert records[0].reason_code == "FAILED"

