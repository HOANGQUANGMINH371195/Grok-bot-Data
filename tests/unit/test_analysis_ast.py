import pytest
from vda_data.analysis import AnalysisError, AnalysisPlan, execute_plan
from vda_data.ingestion import parse_csv_bytes


def test_preview_is_labeled_and_official_requires_human_approval() -> None:
    source = parse_csv_bytes(b"region,amount\nNorth,10.5\nSouth,20.0\n")
    plan = AnalysisPlan("a1", "amount", "sum", filter_column="region", filter_equals="North")
    preview = execute_plan(source, plan)
    assert preview.mode == "preview"
    assert preview.value == "10.5"
    assert preview.limitations
    with pytest.raises(AnalysisError, match="human approval"):
        execute_plan(source, plan, mode="official")
    official = execute_plan(source, plan, mode="official", official_approved=True)
    assert official.mode == "official"
    assert official.limitations == ()


def test_ast_rejects_raw_sql_like_operation_and_unknown_column() -> None:
    source = parse_csv_bytes(b"amount\n10\n")
    with pytest.raises(AnalysisError, match="catalog"):
        execute_plan(source, AnalysisPlan("a1", "amount", "raw_sql"))  # type: ignore[arg-type]
    with pytest.raises(AnalysisError, match="not present"):
        execute_plan(source, AnalysisPlan("a2", "missing", "sum"))
