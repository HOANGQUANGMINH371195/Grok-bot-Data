import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for relative in (
    "services/api/src",
    "packages/platform/src",
    "packages/data_profiling/src",
    "packages/adapters/src",
):
    sys.path.insert(0, str(ROOT / relative))
