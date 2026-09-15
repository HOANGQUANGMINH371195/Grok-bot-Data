import pytest
from vda_platform.runtime import Mailbox, MailboxError


def test_mailbox_correlation_is_idempotent_and_rejects_self_or_unknown_peer() -> None:
    mailbox = Mailbox("room", {"assistant", "analyst"})
    first = mailbox.send(
        correlation_id="corr-1",
        source_bot_id="assistant",
        target_bot_id="analyst",
        kind="request",
        body="profile",
    )
    assert (
        mailbox.send(
            correlation_id="corr-1",
            source_bot_id="assistant",
            target_bot_id="analyst",
            kind="request",
            body="profile",
        )
        == first
    )
    with pytest.raises(MailboxError):
        mailbox.send(
            correlation_id="corr-2",
            source_bot_id="assistant",
            target_bot_id="assistant",
            kind="fyi",
            body="x",
        )
    with pytest.raises(MailboxError):
        mailbox.send(
            correlation_id="corr-3",
            source_bot_id="assistant",
            target_bot_id="unknown",
            kind="fyi",
            body="x",
        )


def test_handoff_cas_and_bounce_limits() -> None:
    mailbox = Mailbox("room", {"assistant", "analyst", "steward"}, max_hops=2)
    mailbox.create_handoff("stage-1", "assistant")
    handoff = mailbox.handoff("stage-1", "assistant", "analyst", 0)
    assert handoff.hop_count == 1
    with pytest.raises(MailboxError):
        mailbox.handoff("stage-1", "assistant", "steward", 0)
    with pytest.raises(MailboxError):
        mailbox.handoff("stage-1", "analyst", "assistant", 1)
    next_handoff = mailbox.handoff("stage-1", "analyst", "steward", 1)
    assert next_handoff.hop_count == 2
    with pytest.raises(MailboxError):
        mailbox.handoff("stage-1", "steward", "assistant", 2)
