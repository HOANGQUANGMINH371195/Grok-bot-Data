from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass


class IngestionError(ValueError):
    """A source failed a deterministic admission or parsing policy."""


@dataclass(frozen=True)
class IngestionPolicy:
    max_file_bytes: int = 256 * 1024 * 1024
    max_rows: int = 1_000_000
    max_columns: int = 200
    max_decoded_bytes: int = 1024 * 1024 * 1024


@dataclass(frozen=True)
class ParsedCsv:
    source_sha256: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str | None, ...], ...]
    encoding: str = "utf-8"

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def column_count(self) -> int:
        return len(self.headers)


def parse_csv_bytes(payload: bytes, policy: IngestionPolicy | None = None) -> ParsedCsv:
    policy = policy or IngestionPolicy()
    if len(payload) > policy.max_file_bytes:
        raise IngestionError("source exceeds max_file_bytes")
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise IngestionError("source must be valid UTF-8") from exc
    if len(text.encode("utf-8")) > policy.max_decoded_bytes:
        raise IngestionError("source exceeds max_decoded_bytes")

    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise IngestionError("source must contain a header") from exc
    if not headers or any(not header.strip() for header in headers):
        raise IngestionError("headers must be non-empty")
    if len(headers) > policy.max_columns:
        raise IngestionError("source exceeds max_columns")
    if len(set(headers)) != len(headers):
        raise IngestionError("duplicate headers are not allowed")

    rows: list[tuple[str | None, ...]] = []
    try:
        for row in reader:
            if len(rows) >= policy.max_rows:
                raise IngestionError("source exceeds max_rows")
            if len(row) != len(headers):
                raise IngestionError("row column count does not match header")
            rows.append(tuple(value if value != "" else None for value in row))
    except csv.Error as exc:
        raise IngestionError("malformed CSV") from exc
    return ParsedCsv(hashlib.sha256(payload).hexdigest(), tuple(headers), tuple(rows))
