from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import CurrentUserDep, SessionDep, correlation_id, idempotency_key
from app.api.schemas import TaskCreateRequest, TaskResponse
from app.application.services.task_service import create_next_cycle, create_task
from app.domain.errors import DomainError

router = APIRouter(prefix="/projects/{project_id}/verification-tasks")


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create(
    project_id: UUID,
    payload: TaskCreateRequest,
    request: Request,
    session: SessionDep,
    user: CurrentUserDep,
    _: str = Depends(idempotency_key),
) -> TaskResponse:
    try:
        task, cycle = create_task(
            session,
            project_id=project_id,
            title=payload.title,
            requirement_key=payload.requirement_key,
            actor_id=user.id,
            correlation_id=correlation_id(request),
            orchestration_template_id=payload.orchestration_template_id,
        )
        session.commit()
        return TaskResponse(
            id=task.id,
            project_id=task.project_id,
            title=task.title,
            requirement_key=task.requirement_key,
            cycle_id=cycle.id,
            cycle_status=cycle.business_status,
            version=task.version,
        )
    except DomainError as exc:
        session.rollback()
        http_status = status.HTTP_403_FORBIDDEN if exc.code == "AUTH_FORBIDDEN" else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=http_status, detail={"code": exc.code, "message": exc.message})


@router.post("/{task_id}/cycles", status_code=status.HTTP_201_CREATED)
def create_cycle(project_id: UUID, task_id: UUID, request: Request, session: SessionDep, user: CurrentUserDep, _: str = Depends(idempotency_key)) -> dict:
    try:
        cycle = create_next_cycle(session, task_id=task_id, actor_id=user.id, correlation_id=correlation_id(request)); session.commit()
        return {"id": str(cycle.id), "taskId": str(cycle.task_id), "sequenceNo": cycle.sequence_no, "status": cycle.business_status}
    except DomainError as exc:
        session.rollback(); raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": exc.code, "message": exc.message})
