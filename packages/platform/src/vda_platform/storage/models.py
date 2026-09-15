from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    conversations: Mapped[list[Conversation]] = relationship(back_populates="workspace")


class Principal(Base):
    __tablename__ = "principals"
    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    principal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    principal_id: Mapped[str] = mapped_column(ForeignKey("principals.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResourceGrant(Base):
    __tablename__ = "resource_grants"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    resource_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    resource_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    principal_id: Mapped[str] = mapped_column(ForeignKey("principals.id"), primary_key=True)
    can_read: Mapped[bool] = mapped_column(Boolean, nullable=False)
    can_write: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SessionRecord(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    principal_id: Mapped[str] = mapped_column(ForeignKey("principals.id"), nullable=False)
    issuer: Mapped[str] = mapped_column(String(512), nullable=False)
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    policy_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    workspace: Mapped[Workspace] = relationship(back_populates="conversations")
    members: Mapped[list[ConversationMember]] = relationship(back_populates="conversation")
    messages: Mapped[list[Message]] = relationship(back_populates="conversation")


class ConversationMember(Base):
    __tablename__ = "conversation_members"
    __table_args__ = (UniqueConstraint("conversation_id", "principal_id", "joined_sequence"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    principal_id: Mapped[str] = mapped_column(String(256), nullable=False)
    joined_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    left_sequence: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    conversation: Mapped[Conversation] = relationship(back_populates="members")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("conversation_id", "sender_id", "client_message_id"),)
    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"), nullable=False, index=True
    )
    sender_id: Mapped[str] = mapped_column(String(256), nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    client_message_id: Mapped[str] = mapped_column(String(256), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    policy_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    event_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(512), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    root_task_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    parent_task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RunRecord(Base):
    __tablename__ = "runs"
    __table_args__ = (
        ForeignKeyConstraint(["workspace_id", "task_id"], ["tasks.workspace_id", "tasks.id"]),
    )
    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    bot_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(256), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    checkpoint_revision: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    checkpoint_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    wait_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    result_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    supersedes_run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AttemptRecord(Base):
    __tablename__ = "attempts"
    __table_args__ = (
        ForeignKeyConstraint(["workspace_id", "run_id"], ["runs.workspace_id", "runs.id"]),
    )
    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str] = mapped_column(String(256), nullable=False)
    fence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ToolExecution(Base):
    __tablename__ = "tool_executions"
    __table_args__ = (
        ForeignKeyConstraint(["workspace_id", "run_id"], ["runs.workspace_id", "runs.id"]),
        ForeignKeyConstraint(
            ["workspace_id", "attempt_id"], ["attempts.workspace_id", "attempts.id"]
        ),
    )
    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"), nullable=False)
    operation_key: Mapped[str] = mapped_column(String(512), nullable=False)
    tool_id: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_version: Mapped[str] = mapped_column(String(64), nullable=False)
    effect_class: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    input_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    output_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EffectRecord(Base):
    __tablename__ = "effects"
    __table_args__ = (
        ForeignKeyConstraint(["workspace_id", "run_id"], ["runs.workspace_id", "runs.id"]),
        ForeignKeyConstraint(
            ["workspace_id", "attempt_id"], ["attempts.workspace_id", "attempts.id"]
        ),
    )
    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"), nullable=False)
    operation_key: Mapped[str] = mapped_column(String(512), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    result_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
