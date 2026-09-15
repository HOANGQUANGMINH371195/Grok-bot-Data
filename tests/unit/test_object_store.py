import pytest
from vda_adapters.s3 import InMemoryObjectStore, ObjectStoreError


def test_object_store_is_immutable_and_content_addressed() -> None:
    store = InMemoryObjectStore()
    first = store.put_immutable("workspace/source.csv", b"id\n1\n")
    assert store.put_immutable("workspace/source.csv", b"id\n1\n") == first
    with pytest.raises(ObjectStoreError, match="immutable"):
        store.put_immutable("workspace/source.csv", b"id\n2\n")


def test_tombstone_keeps_hash_but_blocks_reads() -> None:
    store = InMemoryObjectStore()
    object_ref = store.put_immutable("source", b"payload")
    deleted = store.tombstone("source", object_ref.version_id)
    assert deleted.deleted is True
    assert deleted.sha256 == object_ref.sha256
    with pytest.raises(ObjectStoreError, match="tombstoned"):
        store.get("source", object_ref.version_id)
