"""
File: test_secrets_redaction.py
Path: tests/modules/observability/test_secrets_redaction.py
Role: Security tests for observability secret redaction guarantees.
Used By:
 - pytest
Depends On:
 - src/observability/logging.py
Notes:
 - Prevents secret material from leaking into structured logs.
"""

from src.observability.logging import LogLevel, StructuredLogger


def test_logger_redacts_sensitive_context_keys() -> None:
    logger = StructuredLogger()
    logger.log(
        level=LogLevel.INFO,
        event="security.test",
        message="redaction check",
        correlation_id="corr_1",
        context={"api_key": "super-secret", "token_value": "abc", "safe": "ok"},
    )
    record = logger.records()[0]
    assert record.context["api_key"] == "***REDACTED***"
    assert record.context["token_value"] == "***REDACTED***"
    assert record.context["safe"] == "ok"

