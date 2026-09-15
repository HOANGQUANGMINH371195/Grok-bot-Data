import csv
import json
from pathlib import Path

from vda_data.ingestion import parse_csv_bytes
from vda_data.profiling import profile_csv

ROOT = Path(__file__).parents[1]


def test_sales_fixture_matches_pinned_shape() -> None:
    fixture = ROOT / "fixtures/data/sales_small.csv"
    with fixture.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    expected = json.loads((ROOT / "fixtures/expected/profile_sales_small.json").read_text())
    assert len(rows) == expected["rows"]
    assert len(rows[0]) == expected["columns"]
    assert sum(row["amount"] == "" for row in rows) == expected["null_counts"]["amount"]


def test_fixture_policy_rejects_unbounded_inputs_and_human_authority() -> None:
    policy = json.loads((ROOT / "fixtures/policies/default.json").read_text())
    assert policy["max_file_bytes"] == 256 * 1024 * 1024
    assert "human_approval" in policy["deny"]


def test_decimal_fixture_keeps_exact_values_as_strings_until_typed_conversion() -> None:
    fixture = json.loads((ROOT / "fixtures/data/decimal_nulls.json").read_text())
    assert fixture["columns"]["amount"] == ["10.50", None, "0.00", "-1.25"]
    assert fixture["expected"]["amount_sum"] == "9.25"


def test_unicode_multiline_fixture_is_parsed_without_row_splitting() -> None:
    parsed = parse_csv_bytes((ROOT / "fixtures/data/unicode_multiline.csv").read_bytes())

    assert parsed.headers == ("id", "description", "value")
    assert parsed.rows[0][1] == "café, line one\nline two"
    assert parsed.rows[1] == ("2", "東京", "2.50")


def test_adversarial_fixture_remains_data_and_is_never_evaluated() -> None:
    parsed = parse_csv_bytes((ROOT / "fixtures/data/adversarial.csv").read_bytes())

    assert parsed.rows[0][1].startswith("=HYPERLINK")
    assert parsed.rows[1][1] == "{{ untrusted_template }}"
    assert parsed.rows[0][2] == "x" * 50


def test_pii_and_quality_provider_policy_fixtures_are_pinned() -> None:
    pii = profile_csv((ROOT / "fixtures/data/pii.csv").read_bytes())
    assert pii.columns["email"]["email_like_count"] == 1
    assert pii.columns["phone"]["email_like_count"] == 0

    quality = json.loads((ROOT / "fixtures/expected/quality_sales_small.json").read_text())
    assert set(quality["rules"]) == {
        "not_null",
        "unique",
        "range",
        "allowed_values",
        "approved_pattern",
        "row_count_range",
        "schema_matches",
        "freshness",
    }
    provider = json.loads((ROOT / "fixtures/providers/fake_model.json").read_text())
    assert set(provider["failure_cases"]) == {
        "timeout",
        "rate_limit",
        "malformed_tool_call",
        "private_scope_request",
    }
