from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from vda_data.ingestion import IngestionError, IngestionPolicy, parse_parquet_bytes

FIXTURE = Path(__file__).parents[1] / "fixtures/data/flat_small.parquet"


def _parquet_bytes() -> bytes:
    table = pa.table(
        {"amount": pa.array(["10.50", None, "2.25"]), "region": pa.array(["N", "S", "N"])}
    )
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink, compression="none")
    return sink.getvalue().to_pybytes()


def test_pinned_flat_fixture_has_stable_hash_and_shape() -> None:
    payload = FIXTURE.read_bytes()
    parsed = parse_parquet_bytes(payload)
    assert (
        parsed.source_sha256
        == "9fadeb1287486298247ab5974f35c537aecfb75380dea56f0cc382fc45005ec4"
    )
    assert parsed.headers == ("order_id", "amount", "region")
    assert parsed.row_count == 3
    assert parsed.rows[1][1] is None


def test_parquet_parser_preserves_nulls_and_decimal_strings() -> None:
    parsed = parse_parquet_bytes(_parquet_bytes())
    assert parsed.headers == ("amount", "region")
    assert parsed.rows[0][0] == "10.50"
    assert parsed.rows[1][0] is None
    assert len(parsed.source_sha256) == 64


def test_parquet_parser_enforces_column_cap() -> None:
    with pytest.raises(IngestionError, match="max_columns"):
        parse_parquet_bytes(_parquet_bytes(), IngestionPolicy(max_columns=1))


def test_parquet_parser_rejects_nested_types() -> None:
    table = pa.table({"nested": pa.array([["a"], ["b"]], type=pa.list_(pa.string()))})
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink, compression="none")
    with pytest.raises(IngestionError, match="nested"):
        parse_parquet_bytes(sink.getvalue().to_pybytes())
