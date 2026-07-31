import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.application.services.common import append_audit_event, require_project_role
from app.core.config import get_settings
from app.domain.enums import ProjectRole
from app.domain.errors import DomainError
from app.infrastructure.persistence.models import (
    AnalysisJob,
    AnalysisRun,
    AnalysisRunManifest,
    InputSnapshot,
    InputSnapshotGit,
    Claim,
    EvidenceItem,
    VerificationResult,
    VerificationCycle,
    VerificationTask,
)


def start_analysis_run(
    session: Session, *, snapshot_id: UUID, actor_id: UUID, idempotency_key: str, correlation_id: str
) -> AnalysisRun:
    snapshot = session.get(InputSnapshot, snapshot_id)
    cycle = session.get(VerificationCycle, snapshot.cycle_id) if snapshot else None
    task = session.get(VerificationTask, cycle.task_id) if cycle else None
    if snapshot is None or task is None:
        raise DomainError("RESOURCE_NOT_FOUND", "输入快照不存在")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    if snapshot.purpose != "FORMAL" or session.query(InputSnapshotGit).filter_by(snapshot_id=snapshot.id).one_or_none() is None:
        raise DomainError("INPUT_STALE", "只有包含冻结 Git 范围的正式快照可以启动分析")
    existing_job = session.query(AnalysisJob).filter_by(idempotency_key=idempotency_key).one_or_none()
    if existing_job is not None:
        return session.get(AnalysisRun, existing_job.run_id)
    settings = get_settings()
    config = {
        "workflow": "v1",
        "rules": "v1",
        "prompt": "v1",
        "schema": "v1",
        "generationProvider": settings.generation_provider,
        "generationModel": settings.gemini_generation_model if settings.generation_provider == "gemini" else "fake-model-v1",
    }
    config_hash = f"sha256:{hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()}"
    existing_run = session.query(AnalysisRun).filter_by(snapshot_id=snapshot.id, analysis_config_hash=config_hash).one_or_none()
    if existing_run is not None and existing_run.run_status in {"QUEUED", "RUNNING"}:
        return existing_run
    manifest_hash = f"sha256:{hashlib.sha256(json.dumps({**config, 'snapshot': snapshot.snapshot_hash}, sort_keys=True).encode()).hexdigest()}"
    run = AnalysisRun(snapshot_id=snapshot.id, analysis_config_hash=config_hash, manifest_hash=manifest_hash, checkpoint_ns=f"run-{uuid4()}")
    session.add(run)
    session.flush()
    session.add(AnalysisRunManifest(run_id=run.id, workflow_version="v1", rule_set_version="v1", prompt_set_version="v1", generation_model=config["generationModel"], embedding_model=settings.embedding_model, schema_version="v1"))
    session.add(AnalysisJob(run_id=run.id, idempotency_key=idempotency_key, max_attempts=settings.job_max_attempts))
    cycle.business_status = "ANALYZING"
    cycle.active_run_id = run.id
    append_audit_event(session, project_id=task.project_id, actor_id=actor_id, aggregate_type="AnalysisRun", aggregate_id=run.id, action="ANALYSIS_RUN_QUEUED", correlation_id=correlation_id, payload={"snapshotHash": snapshot.snapshot_hash})
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
        })
    return items
