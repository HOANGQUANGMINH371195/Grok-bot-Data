from __future__ import annotations

import hashlib
from dataclasses import dataclass


class ObjectStoreError(ValueError):
    """Object version or immutability contract failed."""


@dataclass(frozen=True)
class ImmutableObject:
    key: str
    version_id: str
    sha256: str
    payload: bytes
    deleted: bool = False


class InMemoryObjectStore:
    """Offline adapter mirroring private versioned S3 semantics."""

    def __init__(self) -> None:
        self._objects: dict[tuple[str, str], ImmutableObject] = {}
        self._latest: dict[str, str] = {}

    def put_immutable(self, key: str, payload: bytes) -> ImmutableObject:
        if not key or not payload:
            raise ObjectStoreError("key and non-empty payload are required")
        digest = hashlib.sha256(payload).hexdigest()
        current_version = self._latest.get(key)
        if current_version is not None:
            current = self._objects[(key, current_version)]
            if current.sha256 != digest:
                raise ObjectStoreError("source key is immutable; create a new versioned key")
            return current
        version_id = f"v1-{digest[:16]}"
        object_ref = ImmutableObject(key, version_id, digest, bytes(payload))
        self._objects[(key, version_id)] = object_ref
        self._latest[key] = version_id
        return object_ref

    def get(self, key: str, version_id: str | None = None) -> ImmutableObject:
        version = version_id or self._latest.get(key)
        if version is None or (key, version) not in self._objects:
            raise ObjectStoreError("object version not found")
        object_ref = self._objects[(key, version)]
        if object_ref.deleted:
            raise ObjectStoreError("object version is tombstoned")
        return object_ref

    def tombstone(self, key: str, version_id: str) -> ImmutableObject:
        object_ref = self._objects.get((key, version_id))
        if object_ref is None:
            raise ObjectStoreError("object version not found")
        tombstone = ImmutableObject(
            object_ref.key,
            object_ref.version_id,
            object_ref.sha256,
            object_ref.payload,
            deleted=True,
        )
        self._objects[(key, version_id)] = tombstone
        return tombstone
