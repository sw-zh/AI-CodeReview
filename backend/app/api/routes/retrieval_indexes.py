from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import CurrentUserDep, SessionDep, correlation_id, idempotency_key
from app.api.schemas import RetrievalIndexRebuildResponse, RetrievalIndexResponse
from app.application.services.retrieval_index_service import (
    list_project_retrieval_indexes,
    rebuild_project_retrieval_index,
)
from app.domain.errors import DomainError


router = APIRouter(prefix="/projects/{project_id}/retrieval-indexes")


@router.get("", response_model=list[RetrievalIndexResponse])
def list_indexes(project_id: UUID, session: SessionDep, user: CurrentUserDep) -> list[RetrievalIndexResponse]:
    try:
        return [
            RetrievalIndexResponse(**item)
            for item in list_project_retrieval_indexes(session, project_id=project_id, actor_id=user.id)
        ]
    except DomainError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN if exc.code == "AUTH_FORBIDDEN" else status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": exc.code, "message": exc.message},
        )


@router.post("/rebuild", response_model=RetrievalIndexRebuildResponse)
def rebuild(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUserDep,
    _: str = Depends(idempotency_key),
) -> RetrievalIndexRebuildResponse:
    try:
        result = rebuild_project_retrieval_index(
            session,
            project_id=project_id,
            actor_id=user.id,
            correlation_id=correlation_id(request),
        )
        session.commit()
        return RetrievalIndexRebuildResponse(**result)
    except DomainError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN if exc.code == "AUTH_FORBIDDEN" else status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": exc.code, "message": exc.message},
        )
