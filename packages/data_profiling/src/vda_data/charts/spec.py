from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


class ChartError(ValueError):
    """Chart is outside the approved Vega-Lite subset or lacks evidence binding."""


ChartType = Literal["bar", "line", "histogram"]


@dataclass(frozen=True)
class ChartSpec:
    chart_id: str
    chart_type: ChartType
    x_field: str
    y_field: str
    result_ref: str
    evidence_refs: tuple[str, ...]


def validate_chart(spec: ChartSpec, available_fields: set[str]) -> ChartSpec:
    if spec.chart_type not in {"bar", "line", "histogram"}:
        raise ChartError("chart type is outside approved subset")
    if spec.x_field not in available_fields or spec.y_field not in available_fields:
        raise ChartError("chart binding references unknown result field")
    if not spec.result_ref or not spec.evidence_refs:
        raise ChartError("chart must bind to result and evidence")
    return spec
