from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from scipy.stats import chi2_contingency, ttest_ind  # type: ignore[import-untyped]


class StatisticsError(ValueError):
    """Input violates the bounded statistics catalog."""


@dataclass(frozen=True)
class StatisticsResult:
    test: Literal["welch_t", "chi_square"]
    statistic: float
    p_value: float
    alpha: float
    family: str
    correction: Literal["holm", "none"]
    assumptions: tuple[str, ...]
    limitations: tuple[str, ...]


def welch_t(
    baseline: tuple[float, ...],
    current: tuple[float, ...],
    *,
    alpha: float = 0.05,
    family: str = "default",
    correction: Literal["holm", "none"] = "holm",
) -> StatisticsResult:
    _validate_numeric(baseline, current, alpha=alpha)
    statistic, p_value = ttest_ind(baseline, current, equal_var=False)
    return StatisticsResult(
        "welch_t",
        float(statistic),
        float(p_value),
        alpha,
        family,
        correction,
        ("independent observations", "finite numeric values", "two-sided test"),
        ("descriptive association; not a causal claim",),
    )


def chi_square(
    table: tuple[tuple[int, ...], ...],
    *,
    alpha: float = 0.05,
    family: str = "default",
    correction: Literal["holm", "none"] = "holm",
) -> StatisticsResult:
    if len(table) < 2 or any(len(row) < 2 for row in table):
        raise StatisticsError("chi-square requires at least a 2x2 table")
    if any(value < 0 for row in table for value in row):
        raise StatisticsError("chi-square counts cannot be negative")
    if not 0 < alpha < 1:
        raise StatisticsError("alpha must be between zero and one")
    statistic, p_value, _, _ = chi2_contingency(table, correction=False)
    return StatisticsResult(
        "chi_square",
        float(statistic),
        float(p_value),
        alpha,
        family,
        correction,
        (
            "non-negative counts",
            "independent observations",
            "expected counts are inspected by caller",
        ),
        ("descriptive association; not a causal claim",),
    )


def _validate_numeric(*groups: tuple[float, ...], alpha: float) -> None:
    if any(len(group) < 2 for group in groups):
        raise StatisticsError("each group needs at least two observations")
    if any(
        not isinstance(value, (int, float))
        or value != value
        or value in (float("inf"), float("-inf"))
        for group in groups
        for value in group
    ):
        raise StatisticsError("statistics require finite numeric values")
    if not 0 < alpha < 1:
        raise StatisticsError("alpha must be between zero and one")
