from uuid import UUID

from sqlalchemy.orm import Session

from app.application.services.common import append_audit_event, require_project_role
from app.domain.enums import ProjectRole
from app.domain.errors import DomainError
from app.infrastructure.persistence.models import Project, ProjectMember, User
from app.application.services.orchestration_service import ensure_default_orchestration


def create_project(
    session: Session, *, name: str, description: str | None, actor_id: UUID, correlation_id: str
) -> Project:
    project = Project(name=name, description=description, owner_id=actor_id)
    session.add(project)
    session.flush()
    session.add(ProjectMember(project_id=project.id, user_id=actor_id, role=ProjectRole.ADMIN))
    ensure_default_orchestration(session, project_id=project.id, actor_id=actor_id)
    append_audit_event(
        session,
        project_id=project.id,
        actor_id=actor_id,
        aggregate_type="Project",
        aggregate_id=project.id,
        action="PROJECT_CREATED",
        correlation_id=correlation_id,
        after_version=project.version,
    )
    return project


def add_member(session: Session, *, project_id: UUID, user_id: UUID, role: str, actor_id: UUID, correlation_id: str) -> ProjectMember:
    require_project_role(session, project_id, actor_id, {ProjectRole.ADMIN})
    if session.get(User, user_id) is None:
        raise DomainError("RESOURCE_NOT_FOUND", "待添加用户不存在")
    member = session.query(ProjectMember).filter_by(project_id=project_id, user_id=user_id).one_or_none()
    if member is not None:
        raise DomainError("STATE_CONFLICT", "用户已是项目成员")
    member = ProjectMember(project_id=project_id, user_id=user_id, role=role)
    session.add(member); session.flush()
    append_audit_event(session, project_id=project_id, actor_id=actor_id, aggregate_type="ProjectMember", aggregate_id=member.id, action="PROJECT_MEMBER_ADDED", correlation_id=correlation_id, payload={"memberUserId": str(user_id), "role": role})
    return member


def add_member_by_email(session: Session, *, project_id: UUID, user_email: str, role: str, actor_id: UUID, correlation_id: str) -> ProjectMember:
    require_project_role(session, project_id, actor_id, {ProjectRole.ADMIN})
    target = session.query(User).filter_by(email=user_email.strip().lower()).one_or_none()
    if target is None:
        raise DomainError("RESOURCE_NOT_FOUND", "待添加用户不存在")
    return add_member(session, project_id=project_id, user_id=target.id, role=role, actor_id=actor_id, correlation_id=correlation_id)
