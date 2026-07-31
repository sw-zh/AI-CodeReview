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


def create_draft(session: Session, *, cycle_id: UUID, run_id: UUID, actor_id: UUID, correlation_id: str) -> ReportVersion:
    cycle = session.get(VerificationCycle, cycle_id); run = session.get(AnalysisRun, run_id); task = session.get(VerificationTask, cycle.task_id) if cycle else None
    if task is None or run is None or run.run_status not in {"SUCCEEDED", "PARTIALLY_COMPLETED"}:
        raise DomainError("STATE_CONFLICT", "仅终态分析运行可生成报告草稿")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    snapshot = session.get(InputSnapshot, run.snapshot_id)
    results = session.query(VerificationResult).filter_by(analysis_run_id=run.id).all()
    canonical = [{"id": str(x.id), "status": x.status, "evidence": x.evidence_ids} for x in results]
    content_hash = f"sha256:{hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()}"
    next_no = session.query(func.coalesce(func.max(ReportVersion.sequence_no), 0)).filter_by(cycle_id=cycle.id).scalar() + 1
    report = ReportVersion(cycle_id=cycle.id, sequence_no=next_no, status="DRAFT", content_hash=content_hash, snapshot_hash=snapshot.snapshot_hash, run_id=run.id)
    session.add(report); session.flush()
    for order, result in enumerate(results, start=1):
        session.add(ReportItem(report_version_id=report.id, result_id=result.id, display_order=order, result_snapshot={"status": result.status, "reason": result.reason}, citation_snapshot={"evidenceIds": result.evidence_ids}))
    append_audit_event(session, project_id=task.project_id, actor_id=actor_id, aggregate_type="ReportVersion", aggregate_id=report.id, action="REPORT_DRAFT_CREATED", correlation_id=correlation_id)
    return report


def submit_for_review(session: Session, *, report_id: UUID, actor_id: UUID, correlation_id: str) -> ReportVersion:
    report = session.get(ReportVersion, report_id); cycle = session.get(VerificationCycle, report.cycle_id) if report else None; task = session.get(VerificationTask, cycle.task_id) if cycle else None
    if task is None or report.status != "DRAFT": raise DomainError("STATE_CONFLICT", "仅草稿可提交审核")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    report.status = "SUBMITTED"; report.submitted_by = actor_id; report.submitted_at = datetime.now(UTC)
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
    append_audit_event(session, project_id=task.project_id, actor_id=actor_id, aggregate_type="ReportVersion", aggregate_id=report.id, action="REPORT_CHANGES_REQUESTED", correlation_id=correlation_id)
    return report


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
