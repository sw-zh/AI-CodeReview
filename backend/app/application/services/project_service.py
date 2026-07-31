from uuid import UUID

from sqlalchemy.orm import Session

from app.application.services.common import append_audit_event
from app.domain.enums import ProjectRole
from app.infrastructure.persistence.models import Project, ProjectMember


def create_project(
    session: Session, *, name: str, description: str | None, actor_id: UUID, correlation_id: str
) -> Project:
    project = Project(name=name, description=description, owner_id=actor_id)
    session.add(project)
    session.flush()
    session.add(ProjectMember(project_id=project.id, user_id=actor_id, role=ProjectRole.ADMIN))
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
