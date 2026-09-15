import pytest
from vda_data.charts import ChartError, ChartSpec, validate_chart


def test_chart_subset_requires_result_and_evidence_binding() -> None:
    spec = ChartSpec("chart-1", "bar", "region", "amount", "analysis:a1", ("e1",))
    assert validate_chart(spec, {"region", "amount"}) == spec
    with pytest.raises(ChartError, match="evidence"):
        validate_chart(
            ChartSpec("chart-2", "line", "region", "amount", "analysis:a1", ()),
            {"region", "amount"},
        )


def test_chart_rejects_unknown_field() -> None:
    with pytest.raises(ChartError, match="unknown"):
        validate_chart(
            ChartSpec("chart-1", "bar", "unknown", "amount", "analysis:a1", ("e1",)), {"amount"}
        )
