from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from .csv_parser import IngestionError, IngestionPolicy


@dataclass(frozen=True)
class ParsedParquet:
    source_sha256: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str | None, ...], ...]
    encoding: str = "parquet"

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def column_count(self) -> int:
        return len(self.headers)


def parse_parquet_bytes(payload: bytes, policy: IngestionPolicy | None = None) -> ParsedParquet:
    policy = policy or IngestionPolicy()
    if len(payload) > policy.max_file_bytes:
        raise IngestionError("source exceeds max_file_bytes")
    try:
        table = pq.read_table(pa.BufferReader(payload), use_threads=False)
    except (pa.ArrowException, ValueError) as exc:
        raise IngestionError("malformed Parquet") from exc
    if table.num_rows > policy.max_rows:
        raise IngestionError("source exceeds max_rows")
    if table.num_columns > policy.max_columns:
        raise IngestionError("source exceeds max_columns")
    if table.nbytes > policy.max_decoded_bytes:
        raise IngestionError("source exceeds max_decoded_bytes")
    if any(
        pa.types.is_struct(field.type)
        or pa.types.is_list(field.type)
        or pa.types.is_map(field.type)
        for field in table.schema
    ):
        raise IngestionError("nested Parquet types are not supported in R1")
    return _to_rows(table, payload)


def _to_rows(table: pa.Table, payload: bytes) -> ParsedParquet:
    headers = tuple(str(name) for name in table.column_names)
    rows: list[tuple[str | None, ...]] = []
    for row in table.to_pylist():
        values: list[str | None] = []
        for header in headers:
            value = row[header]
            values.append(None if value is None else str(value))
        rows.append(tuple(values))
    return ParsedParquet(hashlib.sha256(payload).hexdigest(), headers, tuple(rows))
