from __future__ import annotations

import math
import re
from dataclasses import dataclass


class EvidenceValidationError(ValueError):
    """An evidence reference is incomplete, mutable or unsafe."""


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    source_sha256: str
    source_version: str
    method_version: str
    claim: str
    cell_refs: tuple[str, ...]
    filters: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    approved: bool = False

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-f0-9]{64}", self.source_sha256):
            raise EvidenceValidationError("source_sha256 must be a lowercase SHA-256")
        if (
            not self.source_version
            or not self.method_version
            or not self.claim
            or not self.cell_refs
        ):
            raise EvidenceValidationError("source, method, claim and cell_refs are required")


@dataclass(frozen=True)
class EvidenceManifest:
    refs: tuple[EvidenceRef, ...]

    def __post_init__(self) -> None:
        if not self.refs:
            raise EvidenceValidationError("at least one evidence reference is required")

    def ids(self) -> tuple[str, ...]:
        return tuple(ref.evidence_id for ref in self.refs)

    def require_approved(self) -> None:
        if not all(ref.approved for ref in self.refs):
            raise EvidenceValidationError("all evidence references must be approved")


def validate_numeric_claim(value: float) -> float:
    if not math.isfinite(value):
        raise EvidenceValidationError("numeric claims must be finite")
    return value
