import hashlib

import pytest
from vda_adapters.s3 import InMemoryObjectStore
from vda_data.ingestion import (
    IngestionPolicy,
    SourceRegistry,
    SourceRegistryError,
    SourceStatus,
)


def test_upload_admits_csv_as_immutable_ready_artifact_and_is_idempotent() -> None:
    payload = b"id,amount\n1,10.50\n2,2.25\n"
    registry = SourceRegistry(InMemoryObjectStore())
    registry.create_dataset("sales", "workspace-a", "owner")
    session = registry.begin_upload("sales", "owner", "sales.csv", upload_id="upload-1")

    first = registry.complete_upload(
        session.upload_id,
        "owner",
        payload,
        expected_sha256=hashlib.sha256(payload).hexdigest(),
        expected_size=len(payload),
    )
    second = registry.complete_upload(session.upload_id, "owner", payload)
    assert first == second
    assert first.status is SourceStatus.READY
    assert first.headers == ("id", "amount")
    assert first.row_count == 2
    with pytest.raises(SourceRegistryError, match="different payload"):
        registry.complete_upload(session.upload_id, "owner", b"id,amount\n3,99\n")

    deduplicated_session = registry.begin_upload(
        "sales", "owner", "sales.csv", upload_id="upload-2"
    )
    assert registry.complete_upload(deduplicated_session.upload_id, "owner", payload) == first
    with pytest.raises(SourceRegistryError, match="different payload"):
        registry.complete_upload(
            deduplicated_session.upload_id, "owner", b"id,amount\n3,99\n"
        )


def test_begin_upload_reuses_only_the_same_session_metadata() -> None:
    registry = SourceRegistry(InMemoryObjectStore())
    registry.create_dataset("sales", "workspace-a", "owner")
    first = registry.begin_upload("sales", "owner", "sales.csv", upload_id="upload-retry")
    retry = registry.begin_upload("sales", "owner", "sales.csv", upload_id="upload-retry")
    assert retry == first
    with pytest.raises(SourceRegistryError, match="different metadata"):
        registry.begin_upload("sales", "owner", "sales.parquet", upload_id="upload-retry")


def test_upload_rejects_acl_hash_format_and_malformed_payload() -> None:
    registry = SourceRegistry(InMemoryObjectStore(), IngestionPolicy(max_file_bytes=64))
    registry.create_dataset("sales", "workspace-a", "owner")
    with pytest.raises(SourceRegistryError, match="write"):
        registry.begin_upload("sales", "intruder", "sales.csv", upload_id="bad-1")
    registry.grant("sales", "owner", "editor", write=True)
    session = registry.begin_upload("sales", "editor", "sales.csv", upload_id="upload-2")
    with pytest.raises(SourceRegistryError, match="SHA"):
        registry.complete_upload(session.upload_id, "editor", b"id\n1\n", expected_sha256="0" * 64)
    with pytest.raises(SourceRegistryError, match="exceeds upload limit"):
        registry.complete_upload(session.upload_id, "editor", b"x" * 65)
    with pytest.raises(SourceRegistryError, match="format"):
        registry.begin_upload("sales", "editor", "sales.xlsx", upload_id="bad-2")
    with pytest.raises(SourceRegistryError, match="upload rejected"):
        registry.complete_upload(session.upload_id, "editor", b"not,csv\n\"broken\n")


def test_resource_acl_and_tombstone_are_enforced_for_parquet() -> None:
    from pathlib import Path

    payload = (Path(__file__).parents[1] / "fixtures/data/flat_small.parquet").read_bytes()
    registry = SourceRegistry(InMemoryObjectStore())
    registry.create_dataset("sales", "workspace-a", "owner")
    session = registry.begin_upload("sales", "owner", "sales.parquet", upload_id="upload-3")
    artifact = registry.complete_upload(session.upload_id, "owner", payload)
    with pytest.raises(SourceRegistryError, match="read"):
        registry.get_version(artifact.artifact_id, "other")
    registry.grant("sales", "owner", "reader", write=False)
    assert registry.get_version(artifact.artifact_id, "reader") == artifact
    tombstoned = registry.tombstone(artifact.artifact_id, "owner")
    assert tombstoned.status is SourceStatus.TOMBSTONED
    with pytest.raises(SourceRegistryError, match="tombstoned"):
        registry.get_version(artifact.artifact_id, "reader")
