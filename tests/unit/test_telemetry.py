from vda_adapters.telemetry import redact_trace


def test_telemetry_redaction_drops_prompt_secret_and_pii() -> None:
    trace = redact_trace(
        "t1",
        "bot.run",
        {
            "tool_id": "profile.get",
            "prompt": "private",
            "api_secret": "x",
            "email": "a@example.test",
            "duration_ms": 3,
        },
    )
    assert trace.metadata == {"tool_id": "profile.get", "duration_ms": 3}
