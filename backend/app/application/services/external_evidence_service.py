import hashlib
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.application.services.common import append_audit_event, require_project_role
from app.core.config import get_settings
from app.domain.enums import ProjectRole
from app.domain.errors import DomainError
from app.infrastructure.persistence.models import ExternalEvidence, VerificationCycle, VerificationTask


def import_external_evidence(
    session: Session,
    *,
    cycle_id: UUID,
    evidence_type: str,
    logical_name: str,
    commit_sha: str,
    content: str,
    exit_code: int | None,
    actor_id: UUID,
    correlation_id: str,
) -> ExternalEvidence:
    cycle = session.get(VerificationCycle, cycle_id)
    task = session.get(VerificationTask, cycle.task_id) if cycle else None
    if task is None:
        raise DomainError("RESOURCE_NOT_FOUND", "核验轮次不存在")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    if cycle.business_status not in {"DRAFT", "NEEDS_EVIDENCE", "NEEDS_CONFIRMATION"}:
        raise DomainError("STATE_CONFLICT", "当前轮次不能再导入外部证据")
    encoded = content.encode("utf-8")
    evidence = ExternalEvidence(
        project_id=task.project_id,
        cycle_id=cycle.id,
        evidence_type=evidence_type,
        logical_name=logical_name,
        commit_sha=commit_sha.lower(),
        content_hash=f"sha256:{hashlib.sha256(encoded).hexdigest()}",
        artifact_uri="pending://artifact",
        exit_code=exit_code,
        submitted_by=actor_id,
    )
    session.add(evidence)
    session.flush()
    target_dir = Path(get_settings().artifact_root).resolve() / str(task.project_id) / "external-evidence" / str(evidence.id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "result.txt"
    target.write_bytes(encoded)
    evidence.artifact_uri = str(target)
    append_audit_event(session, project_id=task.project_id, actor_id=actor_id, aggregate_type="ExternalEvidence", aggregate_id=evidence.id, action="EXTERNAL_EVIDENCE_IMPORTED", correlation_id=correlation_id, payload={"type": evidence_type, "commitSha": evidence.commit_sha, "contentHash": evidence.content_hash})
    return evidence
