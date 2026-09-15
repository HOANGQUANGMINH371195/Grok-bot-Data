from datetime import UTC, datetime, timedelta

import pytest
from vda_platform.identity import SessionError, SessionManager


def test_session_cookie_is_opaque_and_csrf_is_bound_to_live_session() -> None:
    tokens = iter(("session-cookie", "csrf-cookie"))
    manager = SessionManager(lambda: next(tokens))
    cookie, csrf = manager.create(
        "human-1",
        "https://issuer.example",
        "subject-1",
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert cookie.token == "session-cookie"
    current = datetime(2026, 1, 1, tzinfo=UTC)
    assert manager.authenticate(cookie.token, now=current).principal_id == "human-1"
    assert (
        manager.verify_csrf(cookie.token, csrf, now=current).session_id == cookie.session.session_id
    )
    with pytest.raises(SessionError, match="csrf"):
        manager.verify_csrf(cookie.token, "wrong", now=current)


def test_session_expiry_and_revoke_are_fail_closed() -> None:
    tokens = iter(("session-cookie", "csrf-cookie", "session-cookie-2", "csrf-cookie-2"))
    manager = SessionManager(lambda: next(tokens))
    cookie, _ = manager.create(
        "human-1",
        "issuer",
        "subject",
        now=datetime(2026, 1, 1, tzinfo=UTC),
        ttl=timedelta(minutes=5),
    )
    with pytest.raises(SessionError, match="expired"):
        manager.authenticate(cookie.token, now=datetime(2026, 1, 1, 0, 5, tzinfo=UTC))
    cookie, _ = manager.create("human-2", "issuer", "subject-2")
    manager.revoke(cookie.token)
    with pytest.raises(SessionError, match="revoked"):
        manager.authenticate(cookie.token)


def test_empty_or_invalid_session_inputs_are_rejected() -> None:
    manager = SessionManager(lambda: "token")
    with pytest.raises(SessionError, match="required"):
        manager.authenticate("")
    with pytest.raises(SessionError, match="ttl"):
        manager.create("human", "issuer", "subject", ttl=timedelta(0))
