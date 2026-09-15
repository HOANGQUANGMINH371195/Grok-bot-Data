import pytest
from vda_data.drift import DriftError, DriftMapping, compare_numeric
from vda_data.ingestion import parse_csv_bytes


def test_drift_requires_approved_same_dataset_mapping() -> None:
    baseline = parse_csv_bytes(b"amount\n10\n20\n")
    current = parse_csv_bytes(b"amount\n20\n40\n")
    mapping = DriftMapping("dataset-1", "v1", "v2", "amount", approved_by="owner")
    result = compare_numeric(
        baseline, current, mapping, baseline_source_version="v1", current_source_version="v2"
    )
    assert result.absolute_delta == "15"
    assert result.limitations == ("descriptive drift; not a causal claim",)
    with pytest.raises(DriftError, match="approval"):
        compare_numeric(
            baseline,
            current,
            DriftMapping("dataset-1", "v1", "v2", "amount"),
            baseline_source_version="v1",
            current_source_version="v2",
        )


def test_drift_rejects_cross_version_mapping() -> None:
    source = parse_csv_bytes(b"amount\n1\n")
    mapping = DriftMapping("dataset-1", "v1", "v2", "amount", approved_by="owner")
    with pytest.raises(DriftError, match="versions"):
        compare_numeric(
            source, source, mapping, baseline_source_version="v0", current_source_version="v2"
        )
