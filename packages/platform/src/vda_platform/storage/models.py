from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
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
