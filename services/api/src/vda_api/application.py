from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from vda_adapters.fake_model import FakeModelProvider
from vda_adapters.s3 import InMemoryObjectStore, ObjectStoreError
from vda_data.evidence import EvidenceRef
from vda_data.ingestion import ArtifactVersion, IngestionPolicy, SourceRegistry, SourceRegistryError
from vda_data.profiling import (
    ComputeError,
    ComputeLimitError,
    ComputeSupervisor,
    ProfileResult,
)
from vda_platform.conversation import ConversationOutbox, ConversationState, MessageAck
from vda_platform.runtime import BotRuntime, BotTurn
from vda_platform.tools import ToolRegistry


class LocalApiError(ValueError):
    """Local demo command failed its workspace or membership contract."""


class LocalProfileError(LocalApiError):
    """A visible artifact could not be profiled within local compute controls."""


class ProfileRunner(Protocol):
    def profile(self, payload: bytes, format_name: str) -> ProfileResult: ...


@dataclass
class LocalConversation:
    workspace_id: str
    owner_id: str
    outbox: ConversationOutbox
    bot_templates: dict[str, str]


@dataclass(frozen=True)
class LocalDataset:
    dataset_id: str
    workspace_id: str
    owner_id: str
    source_dataset_id: str


@dataclass(frozen=True)
class ProfileColumnSummary:
    name: str
    physical_type: str
    non_null_count: int
    null_count: int
    null_rate: str | None
    distinct_non_null_count: int
    pii_signal_counts: dict[str, int]


@dataclass(frozen=True)
class LocalProfile:
    profile_id: str
    dataset_id: str
    workspace_id: str
    artifact_id: str
    source_sha256: str
    row_count: int
    column_count: int
    method_version: str
    evidence: EvidenceRef
    columns: tuple[ProfileColumnSummary, ...]


class LocalApplication:
    """Contract harness for the local demo; production uses DB-backed repositories."""

    def __init__(self, profile_runner: ProfileRunner | None = None) -> None:
        self._conversations: dict[str, LocalConversation] = {}
        self._object_store = InMemoryObjectStore()
        self._sources = SourceRegistry(self._object_store)
        self._profile_runner = profile_runner or ComputeSupervisor()
        self._datasets: dict[tuple[str, str], LocalDataset] = {}
        self._profiles: dict[str, LocalProfile] = {}
        root = Path(__file__).resolve().parents[4]
        self._tool_registry = ToolRegistry.from_contract_root(root)

    @property
    def max_upload_bytes(self) -> int:
        return IngestionPolicy().max_file_bytes

    def create_dataset(self, workspace_id: str, dataset_id: str, actor_id: str) -> LocalDataset:
        if not workspace_id or not dataset_id or not actor_id:
            raise LocalApiError("workspace, dataset, and actor are required")
        key = (workspace_id, dataset_id)
        existing = self._datasets.get(key)
        if existing is not None:
            if existing.owner_id != actor_id:
                raise PermissionError("dataset is not visible to actor")
            return existing
        identity = f"{workspace_id}:{dataset_id}".encode()
        source_dataset_id = f"local-{hashlib.sha256(identity).hexdigest()[:24]}"
        self._sources.create_dataset(source_dataset_id, workspace_id, actor_id)
        dataset = LocalDataset(dataset_id, workspace_id, actor_id, source_dataset_id)
        self._datasets[key] = dataset
        return dataset

    def upload_dataset(
        self,
        workspace_id: str,
        dataset_id: str,
        actor_id: str,
        upload_id: str,
        filename: str,
        payload: bytes,
        *,
        expected_sha256: str | None = None,
    ) -> ArtifactVersion:
        dataset = self._dataset(workspace_id, dataset_id, actor_id)
        if not upload_id:
            raise LocalApiError("upload_id is required")
        session = self._sources.begin_upload(
            dataset.source_dataset_id,
            actor_id,
            filename,
            upload_id=f"{dataset.source_dataset_id}:{upload_id}",
        )
        return self._sources.complete_upload(
            session.upload_id,
            actor_id,
            payload,
            expected_sha256=expected_sha256,
            expected_size=len(payload),
        )

    def profile_dataset(
        self,
        workspace_id: str,
        dataset_id: str,
        actor_id: str,
        artifact_id: str,
    ) -> LocalProfile:
        dataset = self._dataset(workspace_id, dataset_id, actor_id)
        try:
            artifact = self._sources.get_version(artifact_id, actor_id)
        except SourceRegistryError as exc:
            raise LocalApiError("artifact is not available in this dataset") from exc
        if artifact.dataset_id != dataset.source_dataset_id:
            raise LocalApiError("artifact is not available in this dataset")
        cached = self._profiles.get(artifact.artifact_id)
        if cached is not None:
            return cached
        try:
            source = self._object_store.get(artifact.object_key, artifact.object_version_id)
        except ObjectStoreError as exc:
            raise LocalApiError("artifact source is unavailable") from exc
        try:
            result = self._profile_runner.profile(source.payload, artifact.format)
        except ComputeLimitError as exc:
            raise LocalProfileError("profile exceeded local compute limits") from exc
        except ComputeError as exc:
            raise LocalProfileError("profile compute failed") from exc
        if result.source_sha256 != artifact.source_sha256:
            raise LocalProfileError("profile source integrity check failed")
        profile = _local_profile(dataset, artifact, result)
        self._profiles[artifact.artifact_id] = profile
        return profile

    def create_conversation(
        self,
        workspace_id: str,
        conversation_id: str,
        owner_id: str,
        members: list[str],
        bot_templates: dict[str, str] | None = None,
    ) -> LocalConversation:
        if conversation_id in self._conversations:
            raise LocalApiError("conversation already exists")
        if owner_id not in members:
            raise LocalApiError("owner must be a member")
        state = ConversationState(conversation_id)
        for member_id in dict.fromkeys(members):
            state.add_member(member_id)
        templates = dict(bot_templates or {})
        for member_id in members:
            if member_id.startswith("bot"):
                templates.setdefault(member_id, "DataAssistant")
        unknown = set(templates.values()) - {
            "DataAssistant", "DataSteward", "DataAnalyst", "ReportWriter"
        }
        if unknown:
            raise LocalApiError("unknown bot template")
        conversation = LocalConversation(
            workspace_id, owner_id, ConversationOutbox(workspace_id, state), templates
        )
        self._conversations[conversation_id] = conversation
        return conversation

    def get(self, conversation_id: str) -> LocalConversation:
        try:
            return self._conversations[conversation_id]
        except KeyError as exc:
            raise LocalApiError("conversation not found") from exc

    def send(
        self, conversation_id: str, actor_id: str, client_message_id: str, body: str
    ) -> MessageAck:
        conversation = self.get(conversation_id)
        return conversation.outbox.append_human_message(actor_id, client_message_id, body)

    def read(self, conversation_id: str, actor_id: str):
        conversation = self.get(conversation_id)
        return conversation.outbox.conversation.visible_messages(actor_id)

    def read_events(self, conversation_id: str, actor_id: str, after_seq: int):
        if after_seq < 0:
            raise LocalApiError("after_seq must be non-negative")
        conversation = self.get(conversation_id)
        visible_ids = {
            message.message_id
            for message in conversation.outbox.conversation.visible_messages(actor_id)
        }
        events = tuple(
            event
            for event in conversation.outbox.events
            if event.event_sequence > after_seq
            and event.payload.get("message_id") in visible_ids
        )
        high_watermark = max(
            (event.event_sequence for event in conversation.outbox.events), default=0
        )
        return events, high_watermark

    def run_bot_turn(
        self, conversation_id: str, actor_id: str, bot_id: str, turn_id: str
    ) -> tuple[BotTurn, MessageAck | None]:
        conversation = self.get(conversation_id)
        if not conversation.outbox.conversation.is_active_member(actor_id):
            raise PermissionError("actor is not an active member")
        template = conversation.bot_templates.get(bot_id)
        if template is None or not conversation.outbox.conversation.is_active_member(bot_id):
            raise PermissionError("bot is not an active member")
        provider = FakeModelProvider()
        runtime = BotRuntime(provider, self._tool_registry)
        history = tuple(message.body for message in conversation.outbox.conversation.messages)
        result = runtime.execute(
            actor_id=actor_id,
            bot_id=bot_id,
            bot_template=template,
            workspace_id=conversation.workspace_id,
            conversation_id=conversation_id,
            fence=1,
            idempotency_key=turn_id,
            system="Answer only with verified evidence and ask for missing approvals.",
            history=history,
        )
        if result.status.value != "ok" or not result.text:
            return result, None
        ack = conversation.outbox.append_bot_message(bot_id, f"{turn_id}:response", result.text)
        return result, ack

    def _dataset(self, workspace_id: str, dataset_id: str, actor_id: str) -> LocalDataset:
        try:
            dataset = self._datasets[(workspace_id, dataset_id)]
        except KeyError as exc:
            raise LocalApiError("dataset not found") from exc
        if dataset.owner_id != actor_id:
            raise PermissionError("dataset is not visible to actor")
        return dataset


def _local_profile(
    dataset: LocalDataset, artifact: ArtifactVersion, result: ProfileResult
) -> LocalProfile:
    columns = tuple(_profile_column(name, summary) for name, summary in result.columns.items())
    evidence = EvidenceRef(
        evidence_id=f"profile:{artifact.artifact_id}:{result.method_version}",
        source_sha256=artifact.source_sha256,
        source_version=artifact.object_version_id,
        method_version=result.method_version,
        claim="deterministic profile summary",
        cell_refs=("table.row_count", "table.column_count"),
        limitations=("local demo profile is not an Official execution",),
        approved=False,
    )
    return LocalProfile(
        profile_id=f"profile:{artifact.artifact_id}:{result.method_version}",
        dataset_id=dataset.dataset_id,
        workspace_id=dataset.workspace_id,
        artifact_id=artifact.artifact_id,
        source_sha256=artifact.source_sha256,
        row_count=result.row_count,
        column_count=result.column_count,
        method_version=result.method_version,
        evidence=evidence,
        columns=columns,
    )


def _profile_column(name: str, summary: dict[str, Any]) -> ProfileColumnSummary:
    metrics = summary["profile_metrics"]
    pii_values = _metric_value(metrics["column.pii_signal_counts"])
    pii_signal_counts = {
        signal: int(count)
        for signal, count in pii_values.items()
        if isinstance(signal, str) and isinstance(count, int)
    }
    physical_type = _metric_value(metrics["column.physical_type"])
    null_rate = _metric_value(metrics["column.null_rate"])
    return ProfileColumnSummary(
        name=name,
        physical_type=physical_type if isinstance(physical_type, str) else "unknown",
        non_null_count=_integer_metric(metrics["column.non_null_count"]),
        null_count=_integer_metric(metrics["column.null_count"]),
        null_rate=null_rate if isinstance(null_rate, str) else None,
        distinct_non_null_count=_integer_metric(metrics["column.distinct_non_null_count"]),
        pii_signal_counts=pii_signal_counts,
    )


def _metric_value(metric: dict[str, Any]) -> Any:
    value = metric.get("value")
    return value.get("value") if isinstance(value, dict) else None


def _integer_metric(metric: dict[str, Any]) -> int:
    value = _metric_value(metric)
    if not isinstance(value, int):
        raise LocalApiError("profile returned an invalid integer metric")
    return value
