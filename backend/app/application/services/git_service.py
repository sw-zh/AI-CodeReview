import hashlib
from uuid import UUID

from sqlalchemy.orm import Session

from app.application.services.common import append_audit_event, require_project_role
from app.domain.enums import ProjectRole
from app.domain.errors import DomainError
from app.domain.ports import GitReaderPort
from app.infrastructure.persistence.models import GitRepository, GitSnapshot, VerificationCycle, VerificationTask


def register_repository(
    session: Session, *, project_id: UUID, display_url: str, actor_id: UUID, correlation_id: str
) -> GitRepository:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    canonical_hash = f"sha256:{hashlib.sha256(display_url.strip().encode('utf-8')).hexdigest()}"
    existing = session.query(GitRepository).filter_by(project_id=project_id, canonical_url_hash=canonical_hash).one_or_none()
    if existing is not None:
        return existing
    repository = GitRepository(project_id=project_id, canonical_url_hash=canonical_hash, display_url=display_url.strip())
    session.add(repository)
    session.flush()
    append_audit_event(session, project_id=project_id, actor_id=actor_id, aggregate_type="GitRepository", aggregate_id=repository.id, action="GIT_REPOSITORY_REGISTERED", correlation_id=correlation_id)
    return repository


def freeze_git_snapshot(
    session: Session, *, cycle_id: UUID, repository_id: UUID, base_ref: str, target_ref: str, diff_mode: str, include_paths: list[str], exclude_paths: list[str], actor_id: UUID, correlation_id: str, reader: GitReaderPort
) -> GitSnapshot:
    cycle = session.get(VerificationCycle, cycle_id)
    task = session.get(VerificationTask, cycle.task_id) if cycle else None
    repository = session.get(GitRepository, repository_id)
    if task is None or repository is None or repository.project_id != task.project_id:
        raise DomainError("GIT_RANGE_INVALID", "轮次或仓库不存在，或不属于同一项目")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    frozen = reader.freeze_range(repository.display_url, base_ref, target_ref, diff_mode, include_paths, exclude_paths)
    snapshot = GitSnapshot(cycle_id=cycle_id, repository_id=repository_id, selected_base_ref=base_ref, selected_target_ref=target_ref, base_sha=frozen.base_sha, target_sha=frozen.target_sha, merge_base_sha=frozen.merge_base_sha, diff_mode=diff_mode, include_paths=include_paths, exclude_paths=exclude_paths, diff_hash=frozen.diff_hash, coverage=frozen.coverage)
    session.add(snapshot)
    session.flush()
    append_audit_event(session, project_id=task.project_id, actor_id=actor_id, aggregate_type="GitSnapshot", aggregate_id=snapshot.id, action="GIT_SNAPSHOT_FROZEN", correlation_id=correlation_id, payload={"baseSha": frozen.base_sha, "targetSha": frozen.target_sha, "diffHash": frozen.diff_hash})
    return snapshot
