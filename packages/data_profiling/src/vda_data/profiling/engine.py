from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from vda_data.ingestion import IngestionPolicy, ParsedCsv, parse_csv_bytes

METRIC_FAMILIES: tuple[str, ...] = (
    "row_count",
    "column_count",
    "null_count",
    "non_null_count",
    "distinct_count",
    "duplicate_count",
    "distinct_ratio",
    "min",
    "max",
    "mean",
    "median",
    "stddev",
    "quantiles",
    "sum",
    "zero_count",
    "negative_count",
    "positive_count",
    "finite_count",
    "invalid_numeric_count",
    "string_length_min",
    "string_length_max",
    "string_length_mean",
    "empty_string_count",
    "whitespace_count",
    "date_parse_count",
    "email_like_count",
    "top_values",
    "cardinality",
)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class ProfileResult:
    source_sha256: str
    row_count: int
    column_count: int
    columns: dict[str, dict[str, Any]]
    metric_families: tuple[str, ...] = METRIC_FAMILIES

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_sha256": self.source_sha256,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "metric_families": list(self.metric_families),
            "columns": self.columns,
        }


def _decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        number = Decimal(value.strip())
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _mean(values: list[Decimal]) -> Decimal | None:
    return sum(values, Decimal(0)) / Decimal(len(values)) if values else None


def _median(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def _stddev(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    mean = _mean(values)
    assert mean is not None
    variance = sum((value - mean) ** 2 for value in values) / Decimal(len(values))
    return variance.sqrt()


def profile_csv(payload: bytes, policy: IngestionPolicy | None = None) -> ProfileResult:
    return profile_parsed(parse_csv_bytes(payload, policy))


def profile_parsed(source: ParsedCsv) -> ProfileResult:
    columns: dict[str, dict[str, Any]] = {}
    for index, header in enumerate(source.headers):
        values = [row[index] for row in source.rows]
        non_null = [value for value in values if value is not None]
        numeric = [number for value in non_null if (number := _decimal(value)) is not None]
        invalid_numeric = sum(value is not None and _decimal(value) is None for value in values)
        distinct = set(non_null)
        mean = _mean(numeric)
        median = _median(numeric)
        stats: dict[str, Any] = {
            "row_count": source.row_count,
            "column_count": source.column_count,
            "null_count": len(values) - len(non_null),
            "non_null_count": len(non_null),
            "distinct_count": len(distinct),
            "duplicate_count": len(non_null) - len(distinct),
            "distinct_ratio": str(Decimal(len(distinct)) / Decimal(len(non_null)))
            if non_null
            else None,
            "min": _decimal_text(min(numeric))
            if numeric
            else (min(non_null) if non_null else None),
            "max": _decimal_text(max(numeric))
            if numeric
            else (max(non_null) if non_null else None),
            "mean": _decimal_text(mean),
            "median": _decimal_text(median),
            "stddev": _decimal_text(_stddev(numeric)),
            "quantiles": {
                "p25": _decimal_text(_quantile(numeric, Decimal("0.25"))),
                "p50": _decimal_text(_quantile(numeric, Decimal("0.50"))),
                "p75": _decimal_text(_quantile(numeric, Decimal("0.75"))),
            },
            "sum": _decimal_text(sum(numeric, Decimal(0)) if numeric else None),
            "zero_count": sum(number == 0 for number in numeric),
            "negative_count": sum(number < 0 for number in numeric),
            "positive_count": sum(number > 0 for number in numeric),
            "finite_count": len(numeric),
            "invalid_numeric_count": invalid_numeric,
            "string_length_min": min((len(value) for value in non_null), default=None),
            "string_length_max": max((len(value) for value in non_null), default=None),
            "string_length_mean": (sum(len(value) for value in non_null) / len(non_null))
            if non_null
            else None,
            "empty_string_count": sum(value == "" for value in values),
            "whitespace_count": sum(
                value is not None and value != value.strip() for value in values
            ),
            "date_parse_count": sum(_is_date(value) for value in non_null),
            "email_like_count": sum(bool(_EMAIL_RE.fullmatch(value)) for value in non_null),
            "top_values": _top_values(non_null),
            "cardinality": len(distinct),
        }
        columns[header] = stats
    return ProfileResult(source.source_sha256, source.row_count, source.column_count, columns)


def _quantile(values: list[Decimal], quantile: Decimal) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    position = Decimal(len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - Decimal(lower))


def _is_date(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _top_values(values: list[str], limit: int = 5) -> list[dict[str, int | str]]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return [
        {"value": value, "count": count}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]
