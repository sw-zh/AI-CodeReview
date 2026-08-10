import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.application.services.common import append_audit_event, require_project_role
from app.core.config import get_settings
from app.domain.enums import AssessmentProfile, ProjectRole
from app.domain.errors import DomainError
from app.infrastructure.persistence.models import (
    AnalysisJob,
    AnalysisRun,
    AnalysisRunManifest,
    InputSnapshot,
    InputSnapshotGit,
    Claim,
    EvidenceItem,
    RiskFinding,
    VerificationResult,
    VerificationCycle,
    VerificationTask,
)
from app.application.services.orchestration_service import freeze_run_orchestration, orchestration_fingerprint


_DELIVERY_PROFILE = AssessmentProfile.DELIVERY_VERIFICATION.value


def start_analysis_run(
    session: Session, *, snapshot_id: UUID, actor_id: UUID, idempotency_key: str, correlation_id: str
) -> AnalysisRun:
    snapshot = session.get(InputSnapshot, snapshot_id)
    cycle = session.get(VerificationCycle, snapshot.cycle_id) if snapshot else None
    task = session.get(VerificationTask, cycle.task_id) if cycle else None
    if snapshot is None or task is None:
        raise DomainError("RESOURCE_NOT_FOUND", "输入快照不存在")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    if snapshot.purpose != "FORMAL":
        raise DomainError("INPUT_STALE", "只有正式输入快照可以启动分析")
    if snapshot.assessment_profile != _DELIVERY_PROFILE:
        raise DomainError("ASSESSMENT_PROFILE_NOT_ENABLED", f"运行配置 {snapshot.assessment_profile} 尚未开放执行")
    if session.query(InputSnapshotGit).filter_by(snapshot_id=snapshot.id).one_or_none() is None:
        raise DomainError("INPUT_STALE", "交付核验必须包含冻结 Git 范围")
    if cycle.business_status not in {"DRAFT", "NEEDS_EVIDENCE", "NEEDS_CONFIRMATION"}:
        raise DomainError("STATE_CONFLICT", "当前轮次状态不允许启动新的分析运行")
    existing_job = session.query(AnalysisJob).filter_by(idempotency_key=idempotency_key).one_or_none()
    if existing_job is not None:
        return session.get(AnalysisRun, existing_job.run_id)
    settings = get_settings()
    config = {
        "assessmentProfile": snapshot.assessment_profile,
        "workflow": "dual-core-v1",
        "rules": "v1",
        "prompt": "v1",
        "schema": "v1",
        "generationProvider": settings.generation_provider,
        "generationModel": settings.generation_model_name,
        "orchestrationHash": orchestration_fingerprint(session, task=task, actor_id=actor_id),
    }
    config_hash = f"sha256:{hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()}"
    existing_run = session.query(AnalysisRun).filter(AnalysisRun.snapshot_id == snapshot.id, AnalysisRun.analysis_config_hash == config_hash, AnalysisRun.run_status.in_(("QUEUED", "RUNNING"))).one_or_none()
    if existing_run is not None:
        return existing_run
    manifest_hash = f"sha256:{hashlib.sha256(json.dumps({**config, 'snapshot': snapshot.snapshot_hash}, sort_keys=True).encode()).hexdigest()}"
    run = AnalysisRun(snapshot_id=snapshot.id, assessment_profile=snapshot.assessment_profile, analysis_config_hash=config_hash, manifest_hash=manifest_hash, checkpoint_ns=f"run-{uuid4()}")
    session.add(run)
    session.flush()
    orchestration_snapshot = freeze_run_orchestration(session, run=run, task=task, actor_id=actor_id)
    if config["orchestrationHash"] != orchestration_snapshot.content_hash:
        raise DomainError("ORCHESTRATION_CHANGED", "启动过程中编排模板发生变化，请重新发起分析")
    session.add(orchestration_snapshot)
    session.add(AnalysisRunManifest(run_id=run.id, workflow_version="dual-core-v1", rule_set_version="v1", prompt_set_version="v1", generation_model=config["generationModel"], embedding_model=settings.embedding_model, schema_version="v1"))
    session.add(AnalysisJob(run_id=run.id, idempotency_key=idempotency_key, max_attempts=settings.job_max_attempts))
    cycle.business_status = "ANALYZING"
    cycle.active_run_id = run.id
    append_audit_event(session, project_id=task.project_id, actor_id=actor_id, aggregate_type="AnalysisRun", aggregate_id=run.id, action="ANALYSIS_RUN_QUEUED", correlation_id=correlation_id, payload={"snapshotHash": snapshot.snapshot_hash, "orchestrationHash": orchestration_snapshot.content_hash, "assessmentProfile": snapshot.assessment_profile})
    return run


def request_cancel(session: Session, *, run_id: UUID, actor_id: UUID, correlation_id: str) -> AnalysisRun:
    run = session.get(AnalysisRun, run_id)
    snapshot = session.get(InputSnapshot, run.snapshot_id) if run else None
    cycle = session.get(VerificationCycle, snapshot.cycle_id) if snapshot else None
    task = session.get(VerificationTask, cycle.task_id) if cycle else None
    if task is None:
        raise DomainError("RESOURCE_NOT_FOUND", "分析运行不存在")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    if run.run_status not in {"QUEUED", "RUNNING"}:
        raise DomainError("STATE_CONFLICT", "当前运行不可取消")
    run.cancel_requested_at = datetime.now(UTC)
    append_audit_event(session, project_id=task.project_id, actor_id=actor_id, aggregate_type="AnalysisRun", aggregate_id=run.id, action="ANALYSIS_CANCEL_REQUESTED", correlation_id=correlation_id)
    return run


def get_analysis_run(session: Session, *, run_id: UUID, actor_id: UUID) -> AnalysisRun:
    run = session.get(AnalysisRun, run_id)
    snapshot = session.get(InputSnapshot, run.snapshot_id) if run else None
    cycle = session.get(VerificationCycle, snapshot.cycle_id) if snapshot else None
    task = session.get(VerificationTask, cycle.task_id) if cycle else None
    if task is None:
        raise DomainError("RESOURCE_NOT_FOUND", "分析运行不存在")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.REVIEWER, ProjectRole.ADMIN})
    return run


def get_latest_task_analysis_run(session: Session, *, task_id: UUID, actor_id: UUID) -> AnalysisRun:
    task = session.get(VerificationTask, task_id)
    if task is None:
        raise DomainError("RESOURCE_NOT_FOUND", "核验任务不存在")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.REVIEWER, ProjectRole.ADMIN})
    run = (
        session.query(AnalysisRun)
        .join(InputSnapshot, InputSnapshot.id == AnalysisRun.snapshot_id)
        .join(VerificationCycle, VerificationCycle.id == InputSnapshot.cycle_id)
        .filter(VerificationCycle.task_id == task.id)
        .order_by(AnalysisRun.created_at.desc())
        .first()
    )
    if run is None:
        raise DomainError("RESOURCE_NOT_FOUND", "该核验任务尚未创建分析运行")
    return run


def get_analysis_results(session: Session, *, run_id: UUID, actor_id: UUID) -> list[dict]:
    """Read model for the workbench; every returned citation stays in the run snapshot."""
    run = get_analysis_run(session, run_id=run_id, actor_id=actor_id)
    snapshot = session.get(InputSnapshot, run.snapshot_id)
    results = (
        session.query(VerificationResult, Claim)
        .join(Claim, Claim.id == VerificationResult.claim_id)
        .filter(VerificationResult.analysis_run_id == run.id)
        .order_by(Claim.claim_key)
        .all()
    )
    items: list[dict] = []
    for result, claim in results:
        evidence_ids = [UUID(item) for item in result.evidence_ids]
        evidence = (
            session.query(EvidenceItem)
            .filter(EvidenceItem.id.in_(evidence_ids), EvidenceItem.snapshot_id == snapshot.id)
            .all()
            if evidence_ids
            else []
        )
        risks = session.query(RiskFinding).filter_by(analysis_run_id=run.id, claim_id=claim.id).all()
        items.append({
            "id": result.id,
            "claim_id": claim.id,
            "claim_key": claim.claim_key,
            "claim_text": claim.text,
            "status": result.status,
            "reason": result.reason,
            "requires_human_confirmation": result.requires_human_confirmation,
            "evidence": [
                {
                    "id": str(item.id),
                    "sourceType": item.source_type,
                    "excerpt": item.excerpt_safe,
                    "locator": item.locator,
                    "precision": item.locator_precision,
                }
                for item in evidence
            ],
            "risks": [
                {
                    "id": str(item.id),
                    "severity": item.severity,
                    "category": item.category,
                    "findingKind": item.finding_kind,
                    "recommendation": item.recommendation,
                }
                for item in risks
            ],
        })
    return items
