from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.api.dependencies import CurrentUserDep, SessionDep, correlation_id, idempotency_key
from app.api.schemas import ChunkItemResponse, SourceContentResponse, SourceDetailResponse, SourceResponse
from app.application.services.source_service import create_source_revision, list_project_sources, list_source_chunks, read_source_content
from app.domain.errors import DomainError

router = APIRouter(prefix="/projects/{project_id}/sources")


@router.get("", response_model=list[SourceDetailResponse])
def list_sources(project_id: UUID, session: SessionDep, user: CurrentUserDep) -> list[SourceDetailResponse]:
    try:
        return [SourceDetailResponse(**item) for item in list_project_sources(session, project_id=project_id, actor_id=user.id)]
    except DomainError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN if exc.code == "AUTH_FORBIDDEN" else status.HTTP_404_NOT_FOUND, detail={"code": exc.code, "message": exc.message})


@router.get("/{source_id}", response_model=SourceContentResponse)
def read_content(project_id: UUID, source_id: UUID, session: SessionDep, user: CurrentUserDep) -> SourceContentResponse:
    try:
        return SourceContentResponse(**read_source_content(session, project_id=project_id, source_id=source_id, actor_id=user.id))
    except DomainError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN if exc.code == "AUTH_FORBIDDEN" else status.HTTP_404_NOT_FOUND, detail={"code": exc.code, "message": exc.message})


@router.get("/{source_id}/chunks", response_model=list[ChunkItemResponse])
def list_chunks(project_id: UUID, source_id: UUID, session: SessionDep, user: CurrentUserDep) -> list[ChunkItemResponse]:
    try:
        return [ChunkItemResponse(**item) for item in list_source_chunks(session, project_id=project_id, source_id=source_id, actor_id=user.id)]
    except DomainError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN if exc.code == "AUTH_FORBIDDEN" else status.HTTP_404_NOT_FOUND, detail={"code": exc.code, "message": exc.message})


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def upload(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUserDep,
    file: UploadFile = File(...),
    source_role: str = Form(..., max_length=64),
    logical_name: str = Form(..., max_length=255),
    _: str = Depends(idempotency_key),
) -> SourceResponse:
    try:
        source = create_source_revision(
            session,
            project_id=project_id,
            source_role=source_role,
            logical_name=logical_name,
            media_type=file.content_type or "text/plain",
            content=await file.read(),
            actor_id=user.id,
            correlation_id=correlation_id(request),
        )
        session.commit()
        return SourceResponse(
            id=source.id,
            project_id=source.project_id,
            logical_name=source.logical_name,
            revision_no=source.revision_no,
            content_hash=source.content_hash,
            processing_status=source.processing_status,
            parser_version=source.parser_version,
        )
    except DomainError as exc:
        session.rollback()
        http_status = status.HTTP_403_FORBIDDEN if exc.code == "AUTH_FORBIDDEN" else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=http_status, detail={"code": exc.code, "message": exc.message})
