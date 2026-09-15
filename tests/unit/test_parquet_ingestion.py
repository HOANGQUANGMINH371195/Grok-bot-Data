import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from vda_data.ingestion import IngestionError, IngestionPolicy, parse_parquet_bytes


def _parquet_bytes() -> bytes:
    table = pa.table(
        {"amount": pa.array(["10.50", None, "2.25"]), "region": pa.array(["N", "S", "N"])}
    )
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink, compression="none")
    return sink.getvalue().to_pybytes()


def test_parquet_parser_preserves_nulls_and_decimal_strings() -> None:
    parsed = parse_parquet_bytes(_parquet_bytes())
    assert parsed.headers == ("amount", "region")
    assert parsed.rows[0][0] == "10.50"
    assert parsed.rows[1][0] is None
    assert len(parsed.source_sha256) == 64


def test_parquet_parser_enforces_column_cap() -> None:
    with pytest.raises(IngestionError, match="max_columns"):
        parse_parquet_bytes(_parquet_bytes(), IngestionPolicy(max_columns=1))
