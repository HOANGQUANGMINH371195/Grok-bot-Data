from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from vda_data.ingestion import ParsedCsv, ParsedParquet

QUALITY_RULES: tuple[str, ...] = (
    "not_null",
    "unique",
    "range",
    "allowed_values",
    "approved_pattern",
    "row_count_range",
    "schema_matches",
    "freshness",
)
RULESET_VERSION = "quality-v1"
APPROVED_PATTERNS: dict[str, str] = {
    "email": r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    "iso_date": r"^\d{4}-\d{2}-\d{2}(?:T.*)?$",
    "iso_country_code": r"^[A-Z]{2}$",
}
RULESET_HASH = hashlib.sha256(
    json.dumps(
        {"version": RULESET_VERSION, "rules": QUALITY_RULES, "patterns": APPROVED_PATTERNS},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
).hexdigest()

ParsedSource = ParsedCsv | ParsedParquet


@dataclass(frozen=True)
class QualityResult:
    rule: str
    status: str
    columns: tuple[str, ...]
    details: dict[str, Any]
    ruleset_version: str = RULESET_VERSION
    ruleset_hash: str = RULESET_HASH

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "status": self.status,
            "columns": list(self.columns),
            "details": self.details,
            "ruleset_version": self.ruleset_version,
            "ruleset_hash": self.ruleset_hash,
        }


def evaluate_quality(
    source: ParsedSource,
    *,
    not_null: tuple[str, ...] = (),
    unique: tuple[str, ...] = (),
    accepted_values: dict[str, tuple[str, ...]] | None = None,
    allowed_values: dict[str, tuple[str, ...]] | None = None,
    ranges: dict[str, tuple[str, str]] | None = None,
    approved_patterns: dict[str, str] | None = None,
    row_count_range: tuple[int, int] | None = None,
    freshness_column: str | None = None,
    freshness_max_age_seconds: int | None = None,
    expected_headers: tuple[str, ...] | None = None,
) -> tuple[QualityResult, ...]:
    values = allowed_values if allowed_values is not None else (accepted_values or {})
    return (
        _not_null(source, not_null),
        _unique(source, unique),
        _range(source, ranges or {}),
        _allowed_values(source, values),
        _approved_pattern(source, approved_patterns or {}),
        _row_count_range(source, row_count_range),
        _schema_matches(source, expected_headers),
        _freshness(source, freshness_column, freshness_max_age_seconds),
    )


def _result(
    rule: str, status: str, columns: tuple[str, ...], details: dict[str, Any]
) -> QualityResult:
    return QualityResult(rule, status, columns, details)


def _not_null(source: ParsedSource, columns: tuple[str, ...]) -> QualityResult:
    by_name = {name: index for index, name in enumerate(source.headers)}
    missing = [column for column in columns if column not in by_name]
    failures = [
        column
        for column in columns
        if column in by_name and any(row[by_name[column]] is None for row in source.rows)
    ]
    failed = missing + failures
    return _result("not_null", "fail" if failed else "pass", columns, {"failed_columns": failed})


def _unique(source: ParsedSource, columns: tuple[str, ...]) -> QualityResult:
    by_name = {name: index for index, name in enumerate(source.headers)}
    failures: list[str] = []
    for column in columns:
        if column not in by_name:
            failures.append(column)
            continue
        values = [row[by_name[column]] for row in source.rows]
        if any(value is None for value in values) or len(set(values)) != len(values):
            failures.append(column)
    return _result("unique", "fail" if failures else "pass", columns, {"failed_columns": failures})


def _range(source: ParsedSource, bounds: dict[str, tuple[str, str]]) -> QualityResult:
    by_name = {name: index for index, name in enumerate(source.headers)}
    failures: list[str] = []
    errors: list[str] = []
    for column, (lower, upper) in bounds.items():
        if column not in by_name:
            errors.append(column)
            continue
        try:
            low, high = Decimal(lower), Decimal(upper)
            if not low.is_finite() or not high.is_finite() or low > high:
                raise InvalidOperation
            for row in source.rows:
                raw = row[by_name[column]]
                if raw is None:
                    continue
                value = Decimal(raw)
                if not value.is_finite() or value < low or value > high:
                    failures.append(column)
                    break
        except (InvalidOperation, ValueError):
            errors.append(column)
    status = "error" if errors else ("fail" if failures else "pass")
    return _result(
        "range", status, tuple(bounds), {"failed_columns": failures, "error_columns": errors}
    )


def _allowed_values(source: ParsedSource, allowed: dict[str, tuple[str, ...]]) -> QualityResult:
    by_name = {name: index for index, name in enumerate(source.headers)}
    failures: list[str] = []
    errors: list[str] = []
    for column, values in allowed.items():
        if column not in by_name:
            errors.append(column)
            continue
        permitted = set(values)
        if any(
            row[by_name[column]] not in permitted
            for row in source.rows
            if row[by_name[column]] is not None
        ):
            failures.append(column)
    status = "error" if errors else ("fail" if failures else "pass")
    return _result(
        "allowed_values",
        status,
        tuple(allowed),
        {"failed_columns": failures, "error_columns": errors},
    )


def _approved_pattern(source: ParsedSource, patterns: dict[str, str]) -> QualityResult:
    by_name = {name: index for index, name in enumerate(source.headers)}
    failures: list[str] = []
    errors: list[str] = []
    for column, pattern_id in patterns.items():
        expression = APPROVED_PATTERNS.get(pattern_id)
        if column not in by_name or expression is None:
            errors.append(column)
            continue
        compiled = re.compile(expression)
        if any(
            value is not None and not compiled.fullmatch(value)
            for row in source.rows
            for value in (row[by_name[column]],)
        ):
            failures.append(column)
    status = "error" if errors else (
        "fail" if failures else ("skipped" if not patterns else "pass")
    )
    return _result(
        "approved_pattern",
        status,
        tuple(patterns),
        {"failed_columns": failures, "error_columns": errors, "pattern_ids": patterns},
    )


def _row_count_range(source: ParsedSource, bounds: tuple[int, int] | None) -> QualityResult:
    if bounds is None:
        return _result("row_count_range", "skipped", (), {"reason": "no_row_count_policy"})
    lower, upper = bounds
    if lower < 0 or upper < lower:
        return _result("row_count_range", "error", (), {"reason": "invalid_bounds"})
    passed = lower <= source.row_count <= upper
    return _result(
        "row_count_range",
        "pass" if passed else "fail",
        (),
        {"row_count": source.row_count, "lower": lower, "upper": upper},
    )


def _schema_matches(source: ParsedSource, expected: tuple[str, ...] | None) -> QualityResult:
    if expected is None:
        return _result("schema_matches", "skipped", (), {"reason": "no_expected_schema"})
    status = "pass" if source.headers == expected else "fail"
    return _result(
        "schema_matches", status, expected, {"actual": source.headers, "expected": expected}
    )


def _freshness(
    source: ParsedSource, column: str | None, max_age: int | None
) -> QualityResult:
    if column is None or max_age is None:
        return _result("freshness", "skipped", (), {"reason": "no_freshness_policy"})
    by_name = {name: index for index, name in enumerate(source.headers)}
    if column not in by_name or max_age < 0:
        return _result("freshness", "error", (column,), {"reason": "invalid_policy_or_column"})
    now = datetime.now(UTC)
    failures = 0
    errors = 0
    for row in source.rows:
        value = row[by_name[column]]
        if value is None:
            continue
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                errors += 1
                continue
            failures += (now - timestamp).total_seconds() > max_age
        except ValueError:
            errors += 1
    status = "error" if errors else ("fail" if failures else "pass")
    return _result(
        "freshness", status, (column,), {"failure_count": failures, "error_count": errors}
    )
