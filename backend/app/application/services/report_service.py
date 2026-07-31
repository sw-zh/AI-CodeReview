import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.application.services.common import append_audit_event, require_project_role
from app.domain.enums import ProjectRole
from app.domain.errors import DomainError
from app.infrastructure.persistence.models import ApprovalAction, AnalysisRun, InputSnapshot, PublishedRecord, ReportItem, ReportVersion, VerificationCycle, VerificationResult, VerificationTask


def _content_hash(*, results: list[VerificationResult], editorial_note: str, dispositions: dict[str, str | None]) -> str:
    canonical = {
        "results": [{"id": str(item.id), "status": item.status, "evidence": item.evidence_ids} for item in results],
        "editorialNote": editorial_note,
        "dispositions": dispositions,
    }
    return f"sha256:{hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()}"


def _draft_cycle_status(results: list[VerificationResult]) -> str:
    if not results or all(item.status == "INSUFFICIENT_EVIDENCE" for item in results):
        return "NEEDS_EVIDENCE"
    if any(item.requires_human_confirmation for item in results):
        return "NEEDS_CONFIRMATION"
    return "DRAFT_READY"


def create_draft(session: Session, *, cycle_id: UUID, run_id: UUID, actor_id: UUID, correlation_id: str) -> ReportVersion:
    cycle = session.get(VerificationCycle, cycle_id); run = session.get(AnalysisRun, run_id); task = session.get(VerificationTask, cycle.task_id) if cycle else None
    if task is None or run is None or run.run_status not in {"SUCCEEDED", "PARTIALLY_COMPLETED"}:
        raise DomainError("STATE_CONFLICT", "仅终态分析运行可生成报告草稿")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    snapshot = session.get(InputSnapshot, run.snapshot_id)
    results = session.query(VerificationResult).filter_by(analysis_run_id=run.id).all()
    content_hash = _content_hash(results=results, editorial_note="", dispositions={})
    next_no = session.query(func.coalesce(func.max(ReportVersion.sequence_no), 0)).filter_by(cycle_id=cycle.id).scalar() + 1
    report = ReportVersion(cycle_id=cycle.id, sequence_no=next_no, status="DRAFT", content_hash=content_hash, snapshot_hash=snapshot.snapshot_hash, run_id=run.id)
    session.add(report); session.flush()
    for order, result in enumerate(results, start=1):
        session.add(ReportItem(report_version_id=report.id, result_id=result.id, display_order=order, result_snapshot={"status": result.status, "reason": result.reason}, citation_snapshot={"evidenceIds": result.evidence_ids}))
    append_audit_event(session, project_id=task.project_id, actor_id=actor_id, aggregate_type="ReportVersion", aggregate_id=report.id, action="REPORT_DRAFT_CREATED", correlation_id=correlation_id)
    return report


def update_draft(
    session: Session,
    *,
    report_id: UUID,
    editorial_note: str,
    item_dispositions: dict[UUID, str | None],
    expected_version: int,
    actor_id: UUID,
    correlation_id: str,
) -> ReportVersion:
    report = session.get(ReportVersion, report_id)
    cycle = session.get(VerificationCycle, report.cycle_id) if report else None
    task = session.get(VerificationTask, cycle.task_id) if cycle else None
    if task is None or report.status != "DRAFT":
        raise DomainError("STATE_CONFLICT", "仅草稿报告可编辑")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    if report.version != expected_version:
        raise DomainError("VERSION_CONFLICT", "报告草稿已被其他操作更新，请重新读取后再保存")
    items = session.query(ReportItem).filter_by(report_version_id=report.id).all()
    item_by_id = {item.id: item for item in items}
    if not set(item_dispositions).issubset(item_by_id):
        raise DomainError("INPUT_INVALID", "处置项不属于当前报告版本")
    for item_id, disposition in item_dispositions.items():
        item_by_id[item_id].disposition = disposition
    results = session.query(VerificationResult).filter_by(analysis_run_id=report.run_id).all()
    report.editorial_note = editorial_note
    report.content_hash = _content_hash(
        results=results,
        editorial_note=editorial_note,
        dispositions={str(item.id): item.disposition for item in items},
    )
    report.version += 1
    append_audit_event(session, project_id=task.project_id, actor_id=actor_id, aggregate_type="ReportVersion", aggregate_id=report.id, action="REPORT_DRAFT_UPDATED", correlation_id=correlation_id, payload={"version": report.version})
    return report


def submit_for_review(session: Session, *, report_id: UUID, actor_id: UUID, correlation_id: str) -> ReportVersion:
    report = session.get(ReportVersion, report_id); cycle = session.get(VerificationCycle, report.cycle_id) if report else None; task = session.get(VerificationTask, cycle.task_id) if cycle else None
    if task is None or report.status != "DRAFT": raise DomainError("STATE_CONFLICT", "仅草稿可提交审核")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    report.status = "SUBMITTED"; report.submitted_by = actor_id; report.submitted_at = datetime.now(UTC)
    cycle.business_status = "PENDING_REVIEW"
    append_audit_event(session, project_id=task.project_id, actor_id=actor_id, aggregate_type="ReportVersion", aggregate_id=report.id, action="REPORT_SUBMITTED", correlation_id=correlation_id)
    return report


def approve(session: Session, *, report_id: UUID, actor_id: UUID, reason: str, correlation_id: str) -> ReportVersion:
    report = session.get(ReportVersion, report_id); cycle = session.get(VerificationCycle, report.cycle_id) if report else None; task = session.get(VerificationTask, cycle.task_id) if cycle else None
    if task is None or report.status != "SUBMITTED": raise DomainError("STATE_CONFLICT", "仅已提交报告可批准")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.REVIEWER, ProjectRole.ADMIN})
    if report.submitted_by == actor_id: raise DomainError("AUTH_FORBIDDEN", "提交者不能审批自己的报告")
    report.status = "APPROVED"; cycle.business_status = "APPROVED"
    session.add(ApprovalAction(report_version_id=report.id, action="APPROVED", actor_id=actor_id, reason=reason, report_hash=report.content_hash, snapshot_hash=report.snapshot_hash, run_id=report.run_id))
    append_audit_event(session, project_id=task.project_id, actor_id=actor_id, aggregate_type="ReportVersion", aggregate_id=report.id, action="REPORT_APPROVED", correlation_id=correlation_id)
    return report


def request_changes(session: Session, *, report_id: UUID, actor_id: UUID, reason: str, correlation_id: str) -> ReportVersion:
    report = session.get(ReportVersion, report_id); cycle = session.get(VerificationCycle, report.cycle_id) if report else None; task = session.get(VerificationTask, cycle.task_id) if cycle else None
    if task is None or report.status != "SUBMITTED": raise DomainError("STATE_CONFLICT", "仅已提交报告可要求补证")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.REVIEWER, ProjectRole.ADMIN})
    if report.submitted_by == actor_id: raise DomainError("AUTH_FORBIDDEN", "提交者不能审核自己的报告")
    report.status = "CHANGES_REQUESTED"
    session.add(ApprovalAction(report_version_id=report.id, action="CHANGES_REQUESTED", actor_id=actor_id, reason=reason, report_hash=report.content_hash, snapshot_hash=report.snapshot_hash, run_id=report.run_id))
    next_no = session.query(func.coalesce(func.max(ReportVersion.sequence_no), 0)).filter_by(cycle_id=cycle.id).scalar() + 1
    draft = ReportVersion(cycle_id=cycle.id, sequence_no=next_no, status="DRAFT", parent_report_version_id=report.id, content_hash=report.content_hash, snapshot_hash=report.snapshot_hash, run_id=report.run_id, editorial_note=report.editorial_note)
    session.add(draft); session.flush()
    for item in session.query(ReportItem).filter_by(report_version_id=report.id).all():
        session.add(ReportItem(report_version_id=draft.id, result_id=item.result_id, display_order=item.display_order, result_snapshot=item.result_snapshot, citation_snapshot=item.citation_snapshot, disposition=item.disposition))
    cycle.business_status = _draft_cycle_status(session.query(VerificationResult).filter_by(analysis_run_id=report.run_id).all())
    append_audit_event(session, project_id=task.project_id, actor_id=actor_id, aggregate_type="ReportVersion", aggregate_id=report.id, action="REPORT_CHANGES_REQUESTED", correlation_id=correlation_id, payload={"newDraftId": str(draft.id)})
    return draft


def reject(session: Session, *, report_id: UUID, actor_id: UUID, reason: str, correlation_id: str) -> ReportVersion:
    report = session.get(ReportVersion, report_id); cycle = session.get(VerificationCycle, report.cycle_id) if report else None; task = session.get(VerificationTask, cycle.task_id) if cycle else None
    if task is None or report.status != "SUBMITTED": raise DomainError("STATE_CONFLICT", "仅已提交报告可驳回")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.REVIEWER, ProjectRole.ADMIN})
    if report.submitted_by == actor_id: raise DomainError("AUTH_FORBIDDEN", "提交者不能审核自己的报告")
    report.status = "REJECTED"; cycle.business_status = "REJECTED"
    session.add(ApprovalAction(report_version_id=report.id, action="REJECTED", actor_id=actor_id, reason=reason, report_hash=report.content_hash, snapshot_hash=report.snapshot_hash, run_id=report.run_id))
    append_audit_event(session, project_id=task.project_id, actor_id=actor_id, aggregate_type="ReportVersion", aggregate_id=report.id, action="REPORT_REJECTED", correlation_id=correlation_id)
    return report


def publish(session: Session, *, report_id: UUID, actor_id: UUID, correlation_id: str) -> PublishedRecord:
    report = session.get(ReportVersion, report_id); cycle = session.get(VerificationCycle, report.cycle_id) if report else None; task = session.get(VerificationTask, cycle.task_id) if cycle else None
    if task is None or report.status != "APPROVED": raise DomainError("STATE_CONFLICT", "仅已批准报告可发布")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.REVIEWER, ProjectRole.ADMIN})
    existing = session.query(PublishedRecord).filter_by(report_version_id=report.id).one_or_none()
    if existing: return existing
    record_hash = f"sha256:{hashlib.sha256(f'{report.content_hash}:{report.snapshot_hash}'.encode()).hexdigest()}"
    record = PublishedRecord(task_id=task.id, cycle_id=cycle.id, report_version_id=report.id, record_no=f"{task.requirement_key}-{cycle.sequence_no}-{report.sequence_no}", record_hash=record_hash, published_by=actor_id)
    session.add(record); session.flush(); report.status = "PUBLISHED"; cycle.business_status = "PUBLISHED"
    append_audit_event(session, project_id=task.project_id, actor_id=actor_id, aggregate_type="PublishedRecord", aggregate_id=record.id, action="REPORT_PUBLISHED", correlation_id=correlation_id)
    return record
