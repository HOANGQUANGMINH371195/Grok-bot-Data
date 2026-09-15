from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from vda_data.ingestion import ParsedCsv


class DriftError(ValueError):
    """A drift comparison lacks an approved same-dataset mapping."""


@dataclass(frozen=True)
class DriftMapping:
    dataset_id: str
    baseline_version: str
    current_version: str
    column: str
    approved_by: str | None = None


@dataclass(frozen=True)
class DriftResult:
    dataset_id: str
    column: str
    baseline_mean: str
    current_mean: str
    absolute_delta: str
    relative_delta: str | None
    limitations: tuple[str, ...]


def compare_numeric(
    baseline: ParsedCsv,
    current: ParsedCsv,
    mapping: DriftMapping,
    *,
    baseline_source_version: str,
    current_source_version: str,
) -> DriftResult:
    if not mapping.approved_by:
        raise DriftError("same-dataset mapping requires human approval")
    if (
        baseline_source_version != mapping.baseline_version
        or current_source_version != mapping.current_version
    ):
        raise DriftError("source versions do not match approved mapping")
    if mapping.column not in baseline.headers or mapping.column not in current.headers:
        raise DriftError("mapped column is missing")
    baseline_mean = _mean(baseline, mapping.column)
    current_mean = _mean(current, mapping.column)
    delta = current_mean - baseline_mean
    relative = None if baseline_mean == 0 else delta / baseline_mean
    return DriftResult(
        mapping.dataset_id,
        mapping.column,
        format(baseline_mean, "f"),
        format(current_mean, "f"),
        format(delta, "f"),
        None if relative is None else format(relative, "f"),
        ("descriptive drift; not a causal claim",),
    )


def _mean(source: ParsedCsv, column: str) -> Decimal:
    index = source.headers.index(column)
    values: list[Decimal] = []
    for row in source.rows:
        raw = row[index]
        if raw is None:
            continue
        try:
            value = Decimal(raw)
        except InvalidOperation as exc:
            raise DriftError("mapped column is not numeric") from exc
        if value.is_finite():
            values.append(value)
    if not values:
        raise DriftError("mapped column has no finite values")
    return sum(values, Decimal(0)) / Decimal(len(values))
