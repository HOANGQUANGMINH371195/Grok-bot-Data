import csv
import json
from pathlib import Path

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
