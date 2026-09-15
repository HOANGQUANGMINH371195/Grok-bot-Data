"""Canonical typed profiling metrics and bounded compute supervision."""

from .engine import METRIC_FAMILIES, ProfileResult, profile_csv, profile_parquet, profile_parsed
from .supervisor import ComputeError, ComputeLimitError, ComputeLimits, ComputeSupervisor

__all__ = [
    "METRIC_FAMILIES",
    "ProfileResult",
    "ComputeError",
    "ComputeLimitError",
    "ComputeLimits",
    "ComputeSupervisor",
    "profile_csv",
    "profile_parquet",
    "profile_parsed",
]
