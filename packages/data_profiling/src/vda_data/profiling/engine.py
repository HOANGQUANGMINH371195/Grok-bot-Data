from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from vda_data.ingestion import (
    IngestionPolicy,
    ParsedCsv,
    ParsedParquet,
    parse_csv_bytes,
    parse_parquet_bytes,
)

ParsedTable = ParsedCsv | ParsedParquet
METHOD_VERSION = "profile-v1"

# This order is part of the result contract. The compatibility ``columns``
# view retains the short aliases used by the first local demo.
METRIC_FAMILIES: tuple[str, ...] = (
    "table.row_count",
    "table.column_count",
    "table.duplicate_extra_count",
    "table.duplicate_extra_rate",
    "column.physical_type",
    "column.non_null_count",
    "column.null_count",
    "column.null_rate",
    "column.empty_string_count",
    "column.whitespace_only_count",
    "column.distinct_non_null_count",
    "column.distinct_ratio",
    "column.min",
    "column.max",
    "column.sum",
    "column.mean",
    "column.stddev_sample",
    "column.finite_count",
    "column.q25",
    "column.median",
    "column.q75",
    "column.iqr_outlier_count",
    "column.histogram",
    "column.top_values",
    "pair.pearson_correlation",
    "column.single_candidate_key",
    "column.pii_signal_counts",
    "column.invalid_cast_count",
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9 .()\-]{6,}[0-9]$")
_IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
_CREDIT_CARD_RE = re.compile(r"^(?:\d[ -]*?){13,19}$")


@dataclass(frozen=True)
class ProfileResult:
    source_sha256: str
    row_count: int
    column_count: int
    columns: dict[str, dict[str, Any]]
    metric_families: tuple[str, ...] = METRIC_FAMILIES
    metrics: dict[str, dict[str, Any]] | None = None
    table_metrics: dict[str, dict[str, Any]] | None = None
    pair_metrics: dict[str, dict[str, Any]] | None = None
    method_version: str = METHOD_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_sha256": self.source_sha256,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "metric_families": list(self.metric_families),
            "method_version": self.method_version,
            "table_metrics": self.table_metrics or {},
            "columns": self.columns,
            "pair_metrics": self.pair_metrics or {},
            "metrics": self.metrics or {},
        }


def profile_csv(payload: bytes, policy: IngestionPolicy | None = None) -> ProfileResult:
    return profile_parsed(parse_csv_bytes(payload, policy))


def profile_parquet(payload: bytes, policy: IngestionPolicy | None = None) -> ProfileResult:
    return profile_parsed(parse_parquet_bytes(payload, policy))


def profile_parsed(source: ParsedTable) -> ProfileResult:
    row_count = source.row_count
    table_metrics = _table_metrics(source)
    columns: dict[str, dict[str, Any]] = {}
    metrics: dict[str, dict[str, Any]] = {}

    for index, header in enumerate(source.headers):
        values = [row[index] for row in source.rows]
        stats, exact_metrics, _ = _column_metrics(values, row_count, source.column_count)
        columns[header] = stats
        for metric_name, metric in exact_metrics.items():
            metrics[f"{header}.{metric_name}"] = metric
    pair_metrics = _pair_metrics(source)
    metrics.update(pair_metrics)
    metrics.update(table_metrics)
    return ProfileResult(
        source.source_sha256,
        row_count,
        source.column_count,
        columns,
        METRIC_FAMILIES,
        metrics,
        table_metrics,
        pair_metrics,
        METHOD_VERSION,
    )


def _table_metrics(source: ParsedTable) -> dict[str, dict[str, Any]]:
    distinct_rows = len(set(source.rows))
    duplicate_extra = source.row_count - distinct_rows
    return {
        "table.row_count": _metric("ok", _typed_int(source.row_count), source.row_count),
        "table.column_count": _metric("ok", _typed_int(source.column_count), source.column_count),
        "table.duplicate_extra_count": _metric(
            "ok", _typed_int(duplicate_extra), source.row_count
        ),
        "table.duplicate_extra_rate": _metric(
            "ok" if source.row_count else "not_applicable",
            _typed_decimal(Decimal(duplicate_extra) / Decimal(source.row_count))
            if source.row_count
            else None,
            source.row_count,
        ),
    }


def _column_metrics(
    values: list[str | None], row_count: int, column_count: int
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[Decimal]]:
    non_null = [value for value in values if value is not None]
    numeric, nonfinite_count, invalid_count = _numeric_values(non_null)
    distinct = set(non_null)
    physical_type = _physical_type(non_null)
    null_count = row_count - len(non_null)
    null_rate = Decimal(null_count) / Decimal(row_count) if row_count else None
    mean = _mean(numeric)
    median = _quantile(numeric, Decimal("0.5"))
    q25 = _quantile(numeric, Decimal("0.25"))
    q75 = _quantile(numeric, Decimal("0.75"))
    stddev = _sample_stddev(numeric)
    pii = _pii_signals(non_null)
    histogram = _histogram(numeric)
    candidate_key = row_count > 0 and null_count == 0 and len(distinct) == row_count

    exact: dict[str, dict[str, Any]] = {
        "column.physical_type": _metric(
            "ok", {"type": "string", "value": physical_type}, row_count
        ),
        "column.non_null_count": _metric("ok", _typed_int(len(non_null)), row_count),
        "column.null_count": _metric("ok", _typed_int(null_count), row_count),
        "column.null_rate": _metric(
            "ok" if row_count else "not_applicable",
            _typed_decimal(null_rate) if null_rate is not None else None,
            row_count,
        ),
        "column.empty_string_count": _metric(
            "ok", _typed_int(sum(value == "" for value in non_null)), row_count
        ),
        "column.whitespace_only_count": _metric(
            "ok", _typed_int(sum(value.strip() == "" for value in non_null)), row_count
        ),
        "column.distinct_non_null_count": _metric(
            "ok", _typed_int(len(distinct)), len(non_null)
        ),
        "column.distinct_ratio": _metric(
            "ok" if non_null else "not_applicable",
            _typed_decimal(Decimal(len(distinct)) / Decimal(len(non_null)))
            if non_null
            else None,
            len(non_null),
        ),
        "column.min": _numeric_or_string_metric("min", numeric, non_null, row_count),
        "column.max": _numeric_or_string_metric("max", numeric, non_null, row_count),
        "column.sum": _metric(
            "ok" if numeric else "not_applicable",
            _typed_decimal(sum(numeric, Decimal(0))) if numeric else None,
            len(numeric),
            excluded_count=nonfinite_count + invalid_count,
        ),
        "column.mean": _metric(
            "ok" if numeric else "not_applicable",
            _typed_decimal(mean) if mean is not None else None,
            len(numeric),
            excluded_count=nonfinite_count + invalid_count,
        ),
        "column.stddev_sample": _metric(
            "ok" if stddev is not None else "not_applicable",
            _typed_decimal(stddev) if stddev is not None else None,
            len(numeric),
            excluded_count=nonfinite_count + invalid_count,
            limitations=("sample standard deviation requires at least two finite values",),
        ),
        "column.finite_count": _metric(
            "ok", _typed_int(len(numeric)), len(non_null), excluded_count=nonfinite_count
        ),
        "column.q25": _quantile_metric(q25, numeric, nonfinite_count + invalid_count),
        "column.median": _quantile_metric(median, numeric, nonfinite_count + invalid_count),
        "column.q75": _quantile_metric(q75, numeric, nonfinite_count + invalid_count),
        "column.iqr_outlier_count": _iqr_metric(numeric, q25, q75),
        "column.histogram": _metric(
            "ok" if histogram is not None else "not_applicable",
            histogram,
            len(numeric),
            excluded_count=nonfinite_count + invalid_count,
        ),
        "column.top_values": _metric(
            "ok" if non_null else "not_applicable",
            _top_values(non_null) if non_null else None,
            len(non_null),
        ),
        "column.single_candidate_key": _metric(
            "ok", {"type": "boolean", "value": candidate_key}, row_count
        ),
        "column.pii_signal_counts": _metric(
            "ok", {"type": "object", "value": pii}, len(non_null)
        ),
        "column.invalid_cast_count": _metric(
            "ok", _typed_int(invalid_count), len(non_null), excluded_count=nonfinite_count
        ),
    }

    # Compatibility projection retained for the existing local demo.
    legacy = {
        "row_count": row_count,
        "column_count": column_count,
        "null_count": null_count,
        "non_null_count": len(non_null),
        "distinct_count": len(distinct),
        "duplicate_count": len(non_null) - len(distinct),
        "distinct_ratio": str(Decimal(len(distinct)) / Decimal(len(non_null)))
        if non_null
        else None,
        "min": _decimal_text(min(numeric)) if numeric else (min(non_null) if non_null else None),
        "max": _decimal_text(max(numeric)) if numeric else (max(non_null) if non_null else None),
        "mean": _decimal_text(mean),
        "median": _decimal_text(median),
        "stddev": _decimal_text(stddev),
        "quantiles": {
            "p25": _decimal_text(q25),
            "p50": _decimal_text(median),
            "p75": _decimal_text(q75),
        },
        "sum": _decimal_text(sum(numeric, Decimal(0)) if numeric else None),
        "zero_count": sum(number == 0 for number in numeric),
        "negative_count": sum(number < 0 for number in numeric),
        "positive_count": sum(number > 0 for number in numeric),
        "finite_count": len(numeric),
        "invalid_numeric_count": invalid_count + nonfinite_count,
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
        "top_values": _top_values(non_null, limit=5),
        "cardinality": len(distinct),
        "profile_metrics": exact,
    }
    return legacy, exact, numeric


def _metric(
    status: str,
    value: Any,
    denominator: int | None,
    *,
    unit: str | None = None,
    exactness: str = "exact",
    excluded_count: int = 0,
    limitations: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "status": status,
        "value": value,
        "denominator": denominator,
        "unit": unit,
        "method_version": METHOD_VERSION,
        "exactness": exactness,
        "excluded_count": excluded_count,
        "limitations": list(limitations),
    }


def _numeric_or_string_metric(
    name: str,
    numeric: list[Decimal],
    non_null: list[str],
    denominator: int,
) -> dict[str, Any]:
    if numeric:
        value = min(numeric) if name == "min" else max(numeric)
        return _metric(
            "ok", _typed_decimal(value), denominator, excluded_count=len(non_null) - len(numeric)
        )
    if non_null:
        string_value = min(non_null) if name == "min" else max(non_null)
        return _metric("ok", {"type": "string", "value": string_value}, denominator)
    return _metric("not_applicable", None, denominator)


def _quantile_metric(
    value: Decimal | None, numeric: list[Decimal], excluded_count: int
) -> dict[str, Any]:
    return _metric(
        "ok" if value is not None else "not_applicable",
        _typed_decimal(value) if value is not None else None,
        len(numeric),
        excluded_count=excluded_count,
    )


def _iqr_metric(
    numeric: list[Decimal], q25: Decimal | None, q75: Decimal | None
) -> dict[str, Any]:
    if not numeric or q25 is None or q75 is None:
        return _metric("not_applicable", None, len(numeric))
    spread = q75 - q25
    lower = q25 - Decimal("1.5") * spread
    upper = q75 + Decimal("1.5") * spread
    count = sum(value < lower or value > upper for value in numeric)
    return _metric(
        "ok",
        _typed_int(count),
        len(numeric),
        limitations=("strictly outside Tukey fences",),
    )


def _pair_metrics(source: ParsedTable) -> dict[str, dict[str, Any]]:
    selected: list[tuple[str, dict[int, Decimal]]] = []
    for index, header in enumerate(source.headers):
        finite_by_row = {
            row_index: parsed
            for row_index, row in enumerate(source.rows)
            if (parsed := _decimal_any(row[index])) is not None and parsed.is_finite()
        }
        if finite_by_row:
            selected.append((header, finite_by_row))
    selected = selected[:20]
    result: dict[str, dict[str, Any]] = {}
    for index, (left_name, left) in enumerate(selected):
        for right_name, right in selected[index + 1 :]:
            pairs = [
                (left[row_index], right[row_index])
                for row_index in sorted(set(left) & set(right))
            ]
            key = f"pair.pearson_correlation:{left_name}:{right_name}"
            variable = (
                len(pairs) >= 3
                and len({x for x, _ in pairs}) > 1
                and len({y for _, y in pairs}) > 1
            )
            result[key] = _metric(
                "ok" if variable else "not_applicable",
                _typed_decimal(_pearson(pairs)) if variable else None,
                len(pairs),
                limitations=("pairwise finite observations",),
            )
    return result


def _pearson(pairs: list[tuple[Decimal, Decimal]]) -> Decimal:
    xs = [pair[0] for pair in pairs]
    ys = [pair[1] for pair in pairs]
    mean_x = _mean(xs)
    mean_y = _mean(ys)
    assert mean_x is not None and mean_y is not None
    covariance = sum(((x - mean_x) * (y - mean_y) for x, y in pairs), Decimal(0))
    variance_x = sum(((x - mean_x) ** 2 for x in xs), Decimal(0))
    variance_y = sum(((y - mean_y) ** 2 for y in ys), Decimal(0))
    return covariance / (variance_x * variance_y).sqrt()


def _numeric_values(values: list[str]) -> tuple[list[Decimal], int, int]:
    finite: list[Decimal] = []
    nonfinite = 0
    invalid = 0
    for value in values:
        parsed = _decimal_any(value)
        if parsed is None:
            invalid += 1
        elif parsed.is_finite():
            finite.append(parsed)
        else:
            nonfinite += 1
    return finite, nonfinite, invalid


def _decimal_any(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value.strip())
    except InvalidOperation:
        return None


def _physical_type(values: list[str]) -> str:
    if not values:
        return "unknown"
    parsed = [_decimal_any(value) for value in values]
    if all(value is not None and value.is_finite() for value in parsed):
        return "numeric"
    if all(_decimal_any(value) is not None for value in values):
        return "numeric_nonfinite"
    if all(_is_date(value) for value in values):
        return "timestamp"
    return "string"


def _mean(values: list[Decimal]) -> Decimal | None:
    return sum(values, Decimal(0)) / Decimal(len(values)) if values else None


def _sample_stddev(values: list[Decimal]) -> Decimal | None:
    if len(values) < 2:
        return None
    mean = _mean(values)
    assert mean is not None
    return (sum((value - mean) ** 2 for value in values) / Decimal(len(values) - 1)).sqrt()


def _quantile(values: list[Decimal], quantile: Decimal) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    position = Decimal(len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - Decimal(lower))


def _histogram(values: list[Decimal]) -> dict[str, Any] | None:
    if not values:
        return None
    lower, upper = min(values), max(values)
    if lower == upper:
        return {
            "bins": [
                {"left": _decimal_text(lower), "right": _decimal_text(upper), "count": len(values)}
            ],
            "closed": "last",
        }
    width = (upper - lower) / Decimal(20)
    counts = [0] * 20
    for value in values:
        index = int((value - lower) / width)
        counts[min(index, 19)] += 1
    bins = []
    for index, count in enumerate(counts):
        left = lower + width * Decimal(index)
        right = upper if index == 19 else lower + width * Decimal(index + 1)
        bins.append({"left": _decimal_text(left), "right": _decimal_text(right), "count": count})
    return {"bins": bins, "closed": "last"}


def _top_values(values: list[str], limit: int = 20) -> list[dict[str, int | str]]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], _canonical_sort(item[0])))
    top: list[dict[str, int | str]] = [
        {"value": value, "count": count} for value, count in ordered[:limit]
    ]
    other = sum(count for _, count in ordered[limit:])
    if other:
        top.append({"value": "OTHER", "count": other})
    return top


def _canonical_sort(value: str) -> tuple[int, object]:
    parsed = _decimal_any(value)
    if parsed is not None and parsed.is_finite():
        return (0, parsed)
    if _is_date(value):
        return (1, value)
    return (2, value)


def _pii_signals(values: list[str]) -> dict[str, int]:
    return {
        "email": sum(bool(_EMAIL_RE.fullmatch(value)) for value in values),
        "phone": sum(bool(_PHONE_RE.fullmatch(value)) for value in values),
        "ipv4": sum(bool(_IPV4_RE.fullmatch(value)) for value in values),
        "credit_card": sum(
            bool(_CREDIT_CARD_RE.fullmatch(value.replace(" ", ""))) for value in values
        ),
    }


def _is_date(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _typed_int(value: int) -> dict[str, Any]:
    return {"type": "int64", "value": value}


def _typed_decimal(value: Decimal | None) -> dict[str, Any] | None:
    return None if value is None else {"type": "decimal", "value": format(value, "f")}


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")
