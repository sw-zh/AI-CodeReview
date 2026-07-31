from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import CurrentUserDep, SessionDep, correlation_id, idempotency_key
from app.api.schemas import ProjectCreateRequest, ProjectResponse
from app.application.services.project_service import create_project
from app.domain.errors import DomainError
from app.infrastructure.persistence.models import Project, ProjectMember

router = APIRouter(prefix="/projects")


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create(
    payload: ProjectCreateRequest,
    request: Request,
    session: SessionDep,
    user: CurrentUserDep,
    _: str = Depends(idempotency_key),
) -> Project:
    try:
        project = create_project(
            session,
            name=payload.name,
            description=payload.description,
            actor_id=user.id,
            correlation_id=correlation_id(request),
        )
        session.commit()
        session.refresh(project)
        return project
    except DomainError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": exc.code, "message": exc.message})


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: UUID, session: SessionDep, user: CurrentUserDep) -> Project:
    project = session.get(Project, project_id)
    member = session.query(ProjectMember).filter_by(project_id=project_id, user_id=user.id).one_or_none()
    if project is None or member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    return project
