from decimal import Decimal

import pytest
from vda_data.ingestion import IngestionError, IngestionPolicy, parse_csv_bytes
from vda_data.profiling import METRIC_FAMILIES, profile_csv
from vda_data.quality import QUALITY_RULES, evaluate_quality


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
    assert {result.rule: result.status for result in results}["accepted_values"] == "fail"
