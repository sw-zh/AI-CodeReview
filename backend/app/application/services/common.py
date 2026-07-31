from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.enums import ProjectRole
from app.domain.errors import DomainError
from app.infrastructure.persistence.models import AuditEvent, ProjectMember


def require_project_role(
    session: Session, project_id: UUID, user_id: UUID, allowed: set[ProjectRole]
) -> ProjectMember:
    member = session.query(ProjectMember).filter_by(project_id=project_id, user_id=user_id).one_or_none()
    if member is None or ProjectRole(member.role) not in allowed:
        raise DomainError("AUTH_FORBIDDEN", "当前用户没有该项目资源权限")
    return member


def append_audit_event(
    session: Session,
    *,
    project_id: UUID,
    actor_id: UUID,
    aggregate_type: str,
    aggregate_id: UUID,
    action: str,
    correlation_id: str,
    payload: dict | None = None,
    before_version: int | None = None,
    after_version: int | None = None,
) -> None:
    session.add(
        AuditEvent(
            project_id=project_id,
            actor_id=actor_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            action=action,
            correlation_id=correlation_id,
            payload=payload or {},
            before_version=before_version,
            after_version=after_version,
        )
    )
