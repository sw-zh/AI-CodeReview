from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.services.common import append_audit_event, require_project_role
from app.domain.enums import CycleStatus, ProjectRole
from app.domain.errors import DomainError
from app.infrastructure.persistence.models import DeliveryItem, VerificationCycle, VerificationTask
from app.application.services.orchestration_service import bind_task_default_orchestration, bind_task_template


def create_task(
    session: Session,
    *,
    project_id: UUID,
    title: str,
    requirement_key: str,
    actor_id: UUID,
    correlation_id: str,
    delivery_item_id: UUID | None = None,
    orchestration_template_id: UUID | None = None,
) -> tuple[VerificationTask, VerificationCycle]:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    if delivery_item_id is not None:
        item = session.get(DeliveryItem, delivery_item_id)
        if item is None or item.project_id != project_id:
            raise DomainError("INPUT_INVALID", "研发事项不存在或不属于当前项目")
    task = VerificationTask(
        project_id=project_id, delivery_item_id=delivery_item_id, title=title, requirement_key=requirement_key, created_by=actor_id
    )
    session.add(task)
    try:
        session.flush()
    except IntegrityError as exc:
        raise DomainError("STATE_CONFLICT", "项目内需求标识已存在") from exc
    cycle = VerificationCycle(task_id=task.id, sequence_no=1, business_status=CycleStatus.DRAFT)
    session.add(cycle)
    session.flush()
    if orchestration_template_id is None:
        bind_task_default_orchestration(session, task_id=task.id, project_id=project_id, actor_id=actor_id)
    else:
        bind_task_template(session, task_id=task.id, template_id=orchestration_template_id, actor_id=actor_id, correlation_id=correlation_id)
    append_audit_event(
        session,
        project_id=project_id,
        actor_id=actor_id,
        aggregate_type="VerificationTask",
        aggregate_id=task.id,
        action="VERIFICATION_TASK_CREATED",
        correlation_id=correlation_id,
        after_version=task.version,
        payload={"cycleId": str(cycle.id), "deliveryItemId": str(delivery_item_id) if delivery_item_id else None},
    )
    return task, cycle


def create_next_cycle(session: Session, *, task_id: UUID, actor_id: UUID, correlation_id: str) -> VerificationCycle:
    task = session.get(VerificationTask, task_id)
    if task is None:
        raise DomainError("RESOURCE_NOT_FOUND", "核验任务不存在")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    previous = session.query(VerificationCycle).filter_by(task_id=task.id).order_by(VerificationCycle.sequence_no.desc()).first()
    if previous is None or previous.business_status != CycleStatus.PUBLISHED:
        raise DomainError("STATE_CONFLICT", "仅已发布核验轮次可以创建新版本")
    cycle = VerificationCycle(task_id=task.id, sequence_no=previous.sequence_no + 1, business_status=CycleStatus.DRAFT, created_from_cycle_id=previous.id)
    session.add(cycle); session.flush()
    append_audit_event(session, project_id=task.project_id, actor_id=actor_id, aggregate_type="VerificationCycle", aggregate_id=cycle.id, action="VERIFICATION_CYCLE_CREATED", correlation_id=correlation_id, payload={"previousCycleId": str(previous.id)})
    return cycle
