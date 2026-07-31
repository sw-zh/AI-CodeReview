import hashlib
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.application.services.common import append_audit_event, require_project_role
from app.core.config import get_settings
from app.domain.enums import ProjectRole
from app.domain.errors import DomainError
from app.infrastructure.persistence.models import ManualEvidence, VerificationCycle, VerificationTask


def submit_manual_evidence(
    session: Session,
    *,
    cycle_id: UUID,
    logical_name: str,
    content: str,
    actor_id: UUID,
    correlation_id: str,
) -> ManualEvidence:
    """Store a human supplement immutably; a later formal snapshot opts into it."""
    cycle = session.get(VerificationCycle, cycle_id)
    task = session.get(VerificationTask, cycle.task_id) if cycle else None
    if task is None:
        raise DomainError("RESOURCE_NOT_FOUND", "核验轮次不存在")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    if cycle.business_status not in {"DRAFT", "NEEDS_EVIDENCE", "NEEDS_CONFIRMATION"}:
        raise DomainError("STATE_CONFLICT", "当前轮次不能再提交人工补证")

    encoded = content.encode("utf-8")
    evidence = ManualEvidence(
        project_id=task.project_id,
        cycle_id=cycle.id,
        logical_name=logical_name,
        content_hash=f"sha256:{hashlib.sha256(encoded).hexdigest()}",
        artifact_uri="pending://artifact",
        submitted_by=actor_id,
    )
    session.add(evidence)
    session.flush()
    target_dir = Path(get_settings().artifact_root).resolve() / str(task.project_id) / "manual-evidence" / str(evidence.id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "note.txt"
    target.write_bytes(encoded)
    evidence.artifact_uri = str(target)
    append_audit_event(
        session,
        project_id=task.project_id,
        actor_id=actor_id,
        aggregate_type="ManualEvidence",
        aggregate_id=evidence.id,
        action="MANUAL_EVIDENCE_SUBMITTED",
        correlation_id=correlation_id,
        payload={"contentHash": evidence.content_hash, "logicalName": logical_name},
    )
    return evidence
