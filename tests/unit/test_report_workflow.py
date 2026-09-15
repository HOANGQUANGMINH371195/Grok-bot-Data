import pytest
from vda_data.evidence import EvidenceManifest, EvidenceRef, EvidenceValidationError
from vda_data.reports import ReportError, ReportStatus, ReportWorkflow


def _evidence(approved: bool = True) -> EvidenceManifest:
    return EvidenceManifest(
        (
            EvidenceRef(
                "e1",
                "a" * 64,
                "source-v1",
                "profile-v1",
                "row count is 3",
                ("rows",),
                approved=approved,
            ),
        )
    )


def test_report_requires_distinct_human_reviewer_and_published_snapshot_stays_immutable() -> None:
    workflow = ReportWorkflow()
    workflow.create("r1", "w", "owner", "Sales", _evidence())
    workflow.patch("r1", "owner", "Verified report")
    snapshot = workflow.snapshot("r1", "owner")
    assert snapshot.snapshot_id == "r1:r1"
    workflow.request_submit("r1", "owner")
    with pytest.raises(ReportError, match="different reviewer"):
        workflow.review_and_publish("r1", "owner")
    with pytest.raises(ReportError, match="human reviewer"):
        workflow.review_and_publish("r1", "reviewer", is_bot=True)
    published = workflow.review_and_publish("r1", "reviewer")
    assert published.status is ReportStatus.PUBLISHED
    with pytest.raises(ReportError, match="only owner can patch"):
        workflow.patch("r1", "owner", "tamper")


def test_unapproved_evidence_cannot_be_snapshotted() -> None:
    workflow = ReportWorkflow()
    workflow.create("r1", "w", "owner", "Sales", _evidence(approved=False))
    with pytest.raises(EvidenceValidationError, match="approved"):
        workflow.snapshot("r1", "owner")
