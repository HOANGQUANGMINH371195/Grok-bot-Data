from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from vda_data.ingestion import ParsedCsv

QUALITY_RULES: tuple[str, ...] = (
    "not_null",
    "unique",
    "accepted_values",
    "range",
    "numeric_finite",
    "referential_integrity",
    "freshness",
    "schema",
)


@dataclass(frozen=True)
class QualityResult:
    rule: str
    status: str
    columns: tuple[str, ...]
    details: dict[str, Any]


def evaluate_quality(
    source: ParsedCsv,
    *,
    not_null: tuple[str, ...] = (),
    unique: tuple[str, ...] = (),
    accepted_values: dict[str, tuple[str, ...]] | None = None,
    ranges: dict[str, tuple[str, str]] | None = None,
    freshness_column: str | None = None,
    freshness_max_age_seconds: int | None = None,
    expected_headers: tuple[str, ...] | None = None,
) -> tuple[QualityResult, ...]:
    accepted_values = accepted_values or {}
    ranges = ranges or {}
    by_name = {name: index for index, name in enumerate(source.headers)}
    results: list[QualityResult] = []
    results.append(_not_null(source, by_name, not_null))
    results.append(_unique(source, by_name, unique))
    results.append(_accepted(source, by_name, accepted_values))
    results.append(_range(source, by_name, ranges))
    results.append(_finite(source))
    # Foreign-key validation requires an approved reference manifest; absent means not evaluated.
    results.append(
        QualityResult(
            "referential_integrity", "not_evaluated", (), {"reason": "no_reference_manifest"}
        )
    )
    results.append(_freshness(source, by_name, freshness_column, freshness_max_age_seconds))
    results.append(_schema(source, expected_headers))
    return tuple(results)


def _not_null(
    source: ParsedCsv, by_name: dict[str, int], columns: tuple[str, ...]
) -> QualityResult:
    failures = [
        column
        for column in columns
        if column not in by_name or any(row[by_name[column]] is None for row in source.rows)
    ]
    return QualityResult(
        "not_null", "fail" if failures else "pass", columns, {"failed_columns": failures}
    )


def _unique(source: ParsedCsv, by_name: dict[str, int], columns: tuple[str, ...]) -> QualityResult:
    failures: list[str] = []
    for column in columns:
        if column not in by_name:
            failures.append(column)
            continue
        values = [row[by_name[column]] for row in source.rows]
        if any(value is None for value in values) or len(set(values)) != len(values):
            failures.append(column)
    return QualityResult(
        "unique", "fail" if failures else "pass", columns, {"failed_columns": failures}
    )


def _accepted(
    source: ParsedCsv, by_name: dict[str, int], allowed: dict[str, tuple[str, ...]]
) -> QualityResult:
    failures: list[str] = []
    for column, values in allowed.items():
        if column not in by_name or any(
            row[by_name[column]] not in values
            for row in source.rows
            if row[by_name[column]] is not None
        ):
            failures.append(column)
    return QualityResult(
        "accepted_values",
        "fail" if failures else "pass",
        tuple(allowed),
        {"failed_columns": failures},
    )


def _range(
    source: ParsedCsv, by_name: dict[str, int], bounds: dict[str, tuple[str, str]]
) -> QualityResult:
    from decimal import Decimal, InvalidOperation

    failures: list[str] = []
    for column, (lower, upper) in bounds.items():
        if column not in by_name:
            failures.append(column)
            continue
        try:
            low, high = Decimal(lower), Decimal(upper)
            for row in source.rows:
                raw = row[by_name[column]]
                if raw is not None:
                    value = Decimal(raw)
                    if value < low or value > high:
                        failures.append(column)
                        break
        except (InvalidOperation, ValueError):
            failures.append(column)
    return QualityResult(
        "range", "fail" if failures else "pass", tuple(bounds), {"failed_columns": failures}
    )


def _finite(source: ParsedCsv) -> QualityResult:
    from decimal import Decimal, InvalidOperation

    invalid = 0
    for row in source.rows:
        for value in row:
            if value is None:
                continue
            try:
                number = Decimal(value)
            except InvalidOperation:
                continue
            invalid += not number.is_finite()
    return QualityResult(
        "numeric_finite", "fail" if invalid else "pass", (), {"invalid_count": invalid}
    )


def _freshness(
    source: ParsedCsv, by_name: dict[str, int], column: str | None, max_age: int | None
) -> QualityResult:
    if column is None or max_age is None:
        return QualityResult("freshness", "not_evaluated", (), {"reason": "no_freshness_policy"})
    if column not in by_name:
        return QualityResult("freshness", "fail", (column,), {"reason": "missing_column"})
    now = datetime.now(UTC)
    failures = 0
    for row in source.rows:
        value = row[by_name[column]]
        if value is None:
            continue
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            failures += (now - timestamp).total_seconds() > max_age
        except ValueError:
            failures += 1
    return QualityResult(
        "freshness", "fail" if failures else "pass", (column,), {"failure_count": failures}
    )


def _schema(source: ParsedCsv, expected: tuple[str, ...] | None) -> QualityResult:
    if expected is None:
        return QualityResult("schema", "not_evaluated", (), {"reason": "no_expected_schema"})
    status = "pass" if source.headers == expected else "fail"
    return QualityResult(
        "schema", status, expected, {"actual": source.headers, "expected": expected}
    )
