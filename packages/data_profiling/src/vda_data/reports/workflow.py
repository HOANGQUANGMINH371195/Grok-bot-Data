from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from vda_data.evidence import EvidenceManifest


class ReportError(ValueError):
    """A report lifecycle or authority invariant was violated."""


class ReportStatus(StrEnum):
    DRAFT = "draft"
    SNAPSHOT = "snapshot"
    SUBMITTED = "submitted"
    PUBLISHED = "published"


@dataclass(frozen=True)
class Report:
    report_id: str
    workspace_id: str
    owner_id: str
    title: str
    body: str
    evidence: EvidenceManifest
    status: ReportStatus = ReportStatus.DRAFT
    snapshot_id: str | None = None
    submitter_id: str | None = None
    reviewer_id: str | None = None
    revision: int = 0


class ReportWorkflow:
    def __init__(self) -> None:
        self._reports: dict[str, Report] = {}

    def create(
        self,
        report_id: str,
        workspace_id: str,
        owner_id: str,
        title: str,
        evidence: EvidenceManifest,
    ) -> Report:
        if report_id in self._reports:
            raise ReportError("report already exists")
        report = Report(report_id, workspace_id, owner_id, title, "", evidence)
        self._reports[report_id] = report
        return report

    def patch(self, report_id: str, actor_id: str, body: str) -> Report:
        report = self._get(report_id)
        if report.status is not ReportStatus.DRAFT or actor_id != report.owner_id:
            raise ReportError("only owner can patch a draft")
        updated = replace(report, body=body, revision=report.revision + 1)
        self._reports[report_id] = updated
        return updated

    def snapshot(self, report_id: str, actor_id: str) -> Report:
        report = self._get(report_id)
        if report.status is not ReportStatus.DRAFT or actor_id != report.owner_id:
            raise ReportError("only owner can snapshot a draft")
        report.evidence.require_approved()
        updated = replace(
            report, status=ReportStatus.SNAPSHOT, snapshot_id=f"{report_id}:r{report.revision}"
        )
        self._reports[report_id] = updated
        return updated

    def request_submit(self, report_id: str, actor_id: str, *, is_bot: bool = False) -> Report:
        report = self._get(report_id)
        if is_bot or report.status is not ReportStatus.SNAPSHOT or actor_id != report.owner_id:
            raise ReportError("only human owner can request submit for a snapshot")
        updated = replace(report, status=ReportStatus.SUBMITTED, submitter_id=actor_id)
        self._reports[report_id] = updated
        return updated

    def review_and_publish(
        self, report_id: str, reviewer_id: str, *, is_bot: bool = False
    ) -> Report:
        report = self._get(report_id)
        if is_bot or report.status is not ReportStatus.SUBMITTED:
            raise ReportError("only a human reviewer can publish a submitted report")
        if reviewer_id == report.submitter_id:
            raise ReportError("maker-checker requires a different reviewer")
        updated = replace(report, status=ReportStatus.PUBLISHED, reviewer_id=reviewer_id)
        self._reports[report_id] = updated
        return updated

    def _get(self, report_id: str) -> Report:
        try:
            return self._reports[report_id]
        except KeyError as exc:
            raise ReportError("report not found") from exc
