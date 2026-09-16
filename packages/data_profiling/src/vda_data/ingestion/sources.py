from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Protocol

from .csv_parser import IngestionError, IngestionPolicy, ParsedCsv, parse_csv_bytes
from .parquet_parser import ParsedParquet, parse_parquet_bytes


class SourceRegistryError(ValueError):
    """An upload, ACL, or immutable source transition is invalid."""


class SourceStatus(StrEnum):
    READY = "ready"
    REJECTED = "rejected"
    TOMBSTONED = "tombstoned"


Format = str


class ObjectRef(Protocol):
    key: str
    version_id: str
    sha256: str


class ObjectStore(Protocol):
    def put_immutable(self, key: str, payload: bytes) -> ObjectRef: ...

    def get(self, key: str, version_id: str | None = None) -> ObjectRef: ...

    def tombstone(self, key: str, version_id: str) -> ObjectRef: ...


@dataclass(frozen=True)
class Dataset:
    dataset_id: str
    workspace_id: str
    owner_id: str


@dataclass(frozen=True)
class UploadSession:
    upload_id: str
    dataset_id: str
    workspace_id: str
    actor_id: str
    filename: str
    format: Format
    max_bytes: int


@dataclass(frozen=True)
class ArtifactVersion:
    artifact_id: str
    dataset_id: str
    workspace_id: str
    source_sha256: str
    object_key: str
    object_version_id: str
    size_bytes: int
    format: Format
    headers: tuple[str, ...]
    row_count: int
    status: SourceStatus = SourceStatus.READY


@dataclass(frozen=True)
class _Grant:
    read: bool = False
    write: bool = False


class SourceRegistry:
    """Offline source admission with immutable object and current ACL checks.

    The registry deliberately accepts an object-store port rather than importing an
    S3 SDK. Production repositories can persist these records transactionally and
    use the same state transitions around the adapter.
    """

    def __init__(
        self, store: ObjectStore, policy: IngestionPolicy | None = None
    ) -> None:
        self._store = store
        self._policy = policy or IngestionPolicy()
        self._datasets: dict[str, Dataset] = {}
        self._grants: dict[tuple[str, str], _Grant] = {}
        self._uploads: dict[str, UploadSession] = {}
        self._completed_uploads: dict[str, str] = {}
        self._versions: dict[str, ArtifactVersion] = {}
        self._by_dataset_hash: dict[tuple[str, str], str] = {}

    def create_dataset(self, dataset_id: str, workspace_id: str, owner_id: str) -> Dataset:
        if not dataset_id or not workspace_id or not owner_id:
            raise SourceRegistryError("dataset, workspace, and owner are required")
        if dataset_id in self._datasets:
            raise SourceRegistryError("dataset already exists")
        dataset = Dataset(dataset_id, workspace_id, owner_id)
        self._datasets[dataset_id] = dataset
        self._grants[(dataset_id, owner_id)] = _Grant(read=True, write=True)
        return dataset

    def grant(self, dataset_id: str, owner_id: str, principal_id: str, *, write: bool) -> None:
        dataset = self._dataset(dataset_id)
        if dataset.owner_id != owner_id:
            raise SourceRegistryError("only dataset owner can grant access")
        if not principal_id:
            raise SourceRegistryError("principal is required")
        self._grants[(dataset_id, principal_id)] = _Grant(read=True, write=write)

    def begin_upload(
        self, dataset_id: str, actor_id: str, filename: str, *, upload_id: str
    ) -> UploadSession:
        dataset = self._dataset(dataset_id)
        if not self._grant(dataset_id, actor_id).write:
            raise SourceRegistryError("actor cannot write this dataset")
        format_name = _format_for_filename(filename)
        existing = self._uploads.get(upload_id)
        if existing is not None:
            if (
                existing.dataset_id == dataset.dataset_id
                and existing.actor_id == actor_id
                and existing.filename == filename
                and existing.format == format_name
            ):
                return existing
            raise SourceRegistryError("upload session already exists with different metadata")
        session = UploadSession(
            upload_id,
            dataset.dataset_id,
            dataset.workspace_id,
            actor_id,
            filename,
            format_name,
            self._policy.max_file_bytes,
        )
        self._uploads[upload_id] = session
        return session

    def complete_upload(
        self,
        upload_id: str,
        actor_id: str,
        payload: bytes,
        *,
        expected_sha256: str | None = None,
        expected_size: int | None = None,
    ) -> ArtifactVersion:
        session = self._upload(upload_id)
        if session.actor_id != actor_id or not self._grant(session.dataset_id, actor_id).write:
            raise SourceRegistryError("actor cannot complete this upload")
        if expected_size is not None and expected_size != len(payload):
            raise SourceRegistryError("payload size does not match expected_size")
        digest = hashlib.sha256(payload).hexdigest()
        if expected_sha256 is not None and expected_sha256 != digest:
            raise SourceRegistryError("payload SHA-256 does not match expected_sha256")
        if len(payload) > session.max_bytes:
            raise SourceRegistryError("payload exceeds upload limit")
        completed_id = self._completed_uploads.get(upload_id)
        if completed_id is not None:
            previous = self._versions[completed_id]
            if previous.source_sha256 != digest:
                raise SourceRegistryError("upload session already completed with different payload")
            return previous
        parsed = _parse(session.format, payload, self._policy)
        existing_id = self._by_dataset_hash.get((session.dataset_id, digest))
        if existing_id is not None:
            self._completed_uploads[upload_id] = existing_id
            return self._versions[existing_id]
        object_key = (
            f"workspaces/{session.workspace_id}/datasets/{session.dataset_id}/"
            f"versions/{digest}.{session.format}"
        )
        object_ref = self._store.put_immutable(object_key, payload)
        artifact_id = f"{session.dataset_id}:{digest[:16]}"
        version = ArtifactVersion(
            artifact_id,
            session.dataset_id,
            session.workspace_id,
            digest,
            object_ref.key,
            object_ref.version_id,
            len(payload),
            session.format,
            parsed.headers,
            parsed.row_count,
        )
        self._versions[artifact_id] = version
        self._by_dataset_hash[(session.dataset_id, digest)] = artifact_id
        self._completed_uploads[upload_id] = artifact_id
        return version

    def get_version(self, artifact_id: str, actor_id: str) -> ArtifactVersion:
        version = self._version(artifact_id)
        if not self._grant(version.dataset_id, actor_id).read:
            raise SourceRegistryError("actor cannot read this dataset")
        if version.status is SourceStatus.TOMBSTONED:
            raise SourceRegistryError("artifact is tombstoned")
        self._store.get(version.object_key, version.object_version_id)
        return version

    def tombstone(self, artifact_id: str, actor_id: str) -> ArtifactVersion:
        version = self._version(artifact_id)
        dataset = self._dataset(version.dataset_id)
        if dataset.owner_id != actor_id:
            raise SourceRegistryError("only dataset owner can tombstone an artifact")
        if version.status is SourceStatus.TOMBSTONED:
            return version
        self._store.tombstone(version.object_key, version.object_version_id)
        updated = replace(version, status=SourceStatus.TOMBSTONED)
        self._versions[artifact_id] = updated
        return updated

    def _dataset(self, dataset_id: str) -> Dataset:
        try:
            return self._datasets[dataset_id]
        except KeyError as exc:
            raise SourceRegistryError("dataset not found") from exc

    def _upload(self, upload_id: str) -> UploadSession:
        try:
            return self._uploads[upload_id]
        except KeyError as exc:
            raise SourceRegistryError("upload session not found") from exc

    def _version(self, artifact_id: str) -> ArtifactVersion:
        try:
            return self._versions[artifact_id]
        except KeyError as exc:
            raise SourceRegistryError("artifact not found") from exc

    def _grant(self, dataset_id: str, principal_id: str) -> _Grant:
        return self._grants.get((dataset_id, principal_id), _Grant())


def _format_for_filename(filename: str) -> Format:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix not in {"csv", "parquet"}:
        raise SourceRegistryError(
            "unsupported upload format; only CSV and flat Parquet are supported"
        )
    return suffix


def _parse(
    format_name: Format, payload: bytes, policy: IngestionPolicy
) -> ParsedCsv | ParsedParquet:
    try:
        if format_name == "csv":
            return parse_csv_bytes(payload, policy)
        return parse_parquet_bytes(payload, policy)
    except IngestionError as exc:
        raise SourceRegistryError(f"upload rejected: {exc}") from exc
