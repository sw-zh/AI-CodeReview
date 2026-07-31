from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.services.common import append_audit_event, require_project_role
from app.domain.enums import CycleStatus, ProjectRole
from app.domain.errors import DomainError
from app.infrastructure.persistence.models import VerificationCycle, VerificationTask


def create_task(
    session: Session,
    *,
    project_id: UUID,
    title: str,
    requirement_key: str,
    actor_id: UUID,
    correlation_id: str,
) -> tuple[VerificationTask, VerificationCycle]:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    task = VerificationTask(
        project_id=project_id, title=title, requirement_key=requirement_key, created_by=actor_id
    )
    session.add(task)
    try:
        session.flush()
    except IntegrityError as exc:
        raise DomainError("STATE_CONFLICT", "项目内需求标识已存在") from exc
    cycle = VerificationCycle(task_id=task.id, sequence_no=1, business_status=CycleStatus.DRAFT)
    session.add(cycle)
    session.flush()
    append_audit_event(
        session,
        project_id=project_id,
        actor_id=actor_id,
        aggregate_type="VerificationTask",
        aggregate_id=task.id,
        action="VERIFICATION_TASK_CREATED",
        correlation_id=correlation_id,
        after_version=task.version,
        payload={"cycleId": str(cycle.id)},
    )
    return task, cycle
