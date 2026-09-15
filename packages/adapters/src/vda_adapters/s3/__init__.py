"""Object-store port and deterministic local conformance adapter."""

from .store import ImmutableObject, InMemoryObjectStore, ObjectStoreError

__all__ = ["ImmutableObject", "InMemoryObjectStore", "ObjectStoreError"]
