from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


class SessionError(PermissionError):
    """A session or CSRF credential is invalid, expired, or revoked."""


@dataclass(frozen=True)
class Session:
    session_id: str
    principal_id: str
    issuer: str
    subject: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class SessionCookie:
    token: str
    session: Session


@dataclass
class _StoredSession:
    session: Session
    token_hash: str
    csrf_hash: str


class SessionManager:
    """Opaque server-session contract for an OIDC callback boundary.

    The raw cookie and CSRF values are returned only at issuance. Persistence stores
    hashes, so a database dump cannot be replayed as a browser credential.
    """

    def __init__(self, token_factory: Callable[[], str] | None = None) -> None:
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(32))
        self._sessions: dict[str, _StoredSession] = {}

    def create(
        self,
        principal_id: str,
        issuer: str,
        subject: str,
        *,
        now: datetime | None = None,
        ttl: timedelta = timedelta(hours=8),
    ) -> tuple[SessionCookie, str]:
        if not principal_id or not issuer or not subject:
            raise SessionError("principal, issuer, and subject are required")
        if ttl <= timedelta(0):
            raise SessionError("session ttl must be positive")
        issued_at = _utc(now or datetime.now(UTC))
        token = self._token_factory()
        session = Session(
            secrets.token_urlsafe(18),
            principal_id,
            issuer,
            subject,
            issued_at,
            issued_at + ttl,
        )
        csrf = self._token_factory()
        self._sessions[session.session_id] = _StoredSession(
            session, _digest(token), _digest(csrf)
        )
        return SessionCookie(token, session), csrf

    def authenticate(self, token: str, *, now: datetime | None = None) -> Session:
        stored = self._find(token)
        current = _utc(now or datetime.now(UTC))
        if stored.session.revoked_at is not None:
            raise SessionError("session is revoked")
        if current >= stored.session.expires_at:
            raise SessionError("session is expired")
        return stored.session

    def verify_csrf(self, token: str, csrf: str, *, now: datetime | None = None) -> Session:
        session = self.authenticate(token, now=now)
        stored = self._sessions[session.session_id]
        if not secrets.compare_digest(stored.csrf_hash, _digest(csrf)):
            raise SessionError("csrf token is invalid")
        return session

    def revoke(self, token: str, *, now: datetime | None = None) -> Session:
        stored = self._find(token)
        if stored.session.revoked_at is not None:
            return stored.session
        revoked_at = _utc(now or datetime.now(UTC))
        stored.session = Session(
            stored.session.session_id,
            stored.session.principal_id,
            stored.session.issuer,
            stored.session.subject,
            stored.session.issued_at,
            stored.session.expires_at,
            revoked_at,
        )
        return stored.session

    def _find(self, token: str) -> _StoredSession:
        digest = _digest(token)
        for stored in self._sessions.values():
            if secrets.compare_digest(stored.token_hash, digest):
                return stored
        raise SessionError("session token is invalid")


def _digest(value: str) -> str:
    if not value:
        raise SessionError("credential is required")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
