from decimal import Decimal
from pathlib import Path

import pytest
from vda_data.ingestion import IngestionError, IngestionPolicy, parse_csv_bytes
from vda_data.profiling import (
    METRIC_FAMILIES,
    ComputeError,
    ComputeLimitError,
    ComputeLimits,
    ComputeSupervisor,
    profile_csv,
    profile_parquet,
)
from vda_data.quality import QUALITY_RULES, RULESET_HASH, evaluate_quality


def test_parser_rejects_duplicate_headers_and_caps() -> None:
    with pytest.raises(IngestionError, match="duplicate headers"):
        parse_csv_bytes(b"a,a\n1,2\n")
    with pytest.raises(IngestionError, match="max_file_bytes"):
        parse_csv_bytes(b"a\n1\n", IngestionPolicy(max_file_bytes=2))


def test_profile_has_exact_metric_families_and_finite_decimal_values() -> None:
    result = profile_csv(b"amount,label\n10.50,A\n, A\n-1.25,B\nNaN,B\n")
    assert result.metric_families == METRIC_FAMILIES
    amount = result.columns["amount"]
    assert amount["row_count"] == 4
    assert amount["null_count"] == 1
    assert amount["finite_count"] == 2
    assert amount["invalid_numeric_count"] == 1
    assert Decimal(amount["sum"]) == Decimal("9.25")


def test_profile_flat_parquet_uses_the_same_metric_contract() -> None:
    payload = (Path(__file__).parents[1] / "fixtures/data/flat_small.parquet").read_bytes()
    result = profile_parquet(payload)
    assert result.metric_families == METRIC_FAMILIES
    assert result.row_count == 3
    assert result.columns["amount"]["null_count"] == 1
    assert result.columns["amount"]["sum"] == "12.75"


def test_quality_returns_all_eight_rules_and_negative_outcomes() -> None:
    source = parse_csv_bytes(b"id,status\n1,ok\n1,bad\n")
    results = evaluate_quality(
        source,
        not_null=("status",),
        unique=("id",),
        accepted_values={"status": ("ok",)},
    )
    assert tuple(result.rule for result in results) == QUALITY_RULES
    assert {result.rule: result.status for result in results}["unique"] == "fail"
    assert {result.rule: result.status for result in results}["allowed_values"] == "fail"


def test_profile_exposes_typed_28_metric_catalog_and_pair_alignment() -> None:
    result = profile_csv(
        b"id,x,y,email\n1,1,10,a@example.test\n2,,20,b@example.test\n3,3,30,\n1,1,10,a@example.test\n"
    )

    assert len(METRIC_FAMILIES) == 28
    assert result.table_metrics is not None
    assert result.table_metrics["table.duplicate_extra_count"]["value"]["value"] == 1
    x_metrics = result.columns["x"]["profile_metrics"]
    assert Decimal(x_metrics["column.stddev_sample"]["value"]["value"]).quantize(
        Decimal("0.0001")
    ) == Decimal("1.1547")
    assert x_metrics["column.histogram"]["value"]["bins"]
    assert x_metrics["column.single_candidate_key"]["value"]["value"] is False
    assert (
        result.columns["email"]["profile_metrics"]["column.pii_signal_counts"]["value"]["value"]["email"]
        == 3
    )
    pair = result.pair_metrics["pair.pearson_correlation:x:y"] if result.pair_metrics else None
    assert pair is not None
    assert pair["status"] == "ok"
    assert pair["value"]["value"] == "1"


def test_compute_supervisor_rejects_limits_and_terminates_over_deadline() -> None:
    result = ComputeSupervisor().profile(b"a,b\n1,2\n", "csv")
    assert result.row_count == 1
    with pytest.raises(ComputeLimitError, match="max_file_bytes"):
        ComputeSupervisor(ComputeLimits(ingestion=IngestionPolicy(max_file_bytes=1))).profile(
            b"a\n1\n", "csv"
        )
    with pytest.raises(ComputeLimitError, match="deadline"):
        ComputeSupervisor(ComputeLimits(deadline_seconds=0.0001)).profile(b"a\n1\n", "csv")
    with pytest.raises(ComputeError, match="malformed CSV"):
        ComputeSupervisor().profile(b"a\n\"unterminated\n", "csv")


def test_quality_ruleset_is_canonical_bounded_and_versioned() -> None:
    source = parse_csv_bytes(b"email,status\na@example.test,ok\nbad,bad\n")
    results = evaluate_quality(
        source,
        approved_patterns={"email": "email"},
        row_count_range=(1, 3),
        expected_headers=("email", "status"),
    )

    assert tuple(result.rule for result in results) == QUALITY_RULES
    assert len(results) == 8
    assert results[0].ruleset_hash == RULESET_HASH
    assert {result.rule: result.status for result in results}["approved_pattern"] == "fail"
    assert {result.rule: result.status for result in results}["row_count_range"] == "pass"
    assert {result.rule: result.status for result in results}["schema_matches"] == "pass"
