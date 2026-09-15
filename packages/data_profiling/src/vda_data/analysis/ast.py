from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from vda_data.ingestion import ParsedCsv


class AnalysisError(ValueError):
    """An analysis plan is outside the approved AST catalog."""


Operation = Literal["count", "sum", "mean", "min", "max"]


@dataclass(frozen=True)
class AnalysisPlan:
    analysis_id: str
    column: str | None
    operation: Operation
    filter_column: str | None = None
    filter_equals: str | None = None
    version: int = 1

    def validate(self, source: ParsedCsv) -> None:
        if self.operation not in {"count", "sum", "mean", "min", "max"}:
            raise AnalysisError("operation is not in the approved catalog")
        if self.column is not None and self.column not in source.headers:
            raise AnalysisError("column is not present in source")
        if self.filter_column is not None and self.filter_column not in source.headers:
            raise AnalysisError("filter column is not present in source")
        if self.filter_column is None and self.filter_equals is not None:
            raise AnalysisError("filter_equals requires filter_column")


@dataclass(frozen=True)
class AnalysisResult:
    analysis_id: str
    source_sha256: str
    mode: Literal["preview", "official"]
    row_count_evaluated: int
    value: str
    evidence_ref: str
    limitations: tuple[str, ...]


def execute_plan(
    source: ParsedCsv,
    plan: AnalysisPlan,
    *,
    mode: Literal["preview", "official"] = "preview",
    official_approved: bool = False,
    preview_limit: int = 10_000,
) -> AnalysisResult:
    plan.validate(source)
    if mode == "official" and not official_approved:
        raise AnalysisError("official execution requires human approval")
    rows = source.rows if mode == "official" else source.rows[:preview_limit]
    if plan.filter_column is not None:
        index = source.headers.index(plan.filter_column)
        rows = tuple(row for row in rows if row[index] == plan.filter_equals)
    values = [row[source.headers.index(plan.column)] for row in rows] if plan.column else []
    numeric: list[Decimal] = []
    for value in values:
        if value is None:
            continue
        try:
            numeric.append(Decimal(value))
        except InvalidOperation as exc:
            raise AnalysisError("numeric operation received non-numeric value") from exc
    if plan.operation == "count":
        value = str(len(rows))
    elif not numeric:
        raise AnalysisError("numeric operation has no finite values")
    elif plan.operation == "sum":
        value = format(sum(numeric, Decimal(0)), "f")
    elif plan.operation == "mean":
        value = format(sum(numeric, Decimal(0)) / Decimal(len(numeric)), "f")
    elif plan.operation == "min":
        value = format(min(numeric), "f")
    else:
        value = format(max(numeric), "f")
    limitations = () if mode == "official" else (f"preview capped at {preview_limit} rows",)
    return AnalysisResult(
        plan.analysis_id,
        source.source_sha256,
        mode,
        len(rows),
        value,
        f"analysis:{plan.analysis_id}:source:{source.source_sha256}",
        limitations,
    )
