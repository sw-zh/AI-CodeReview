from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.api.dependencies import CurrentUserDep, SessionDep, correlation_id, idempotency_key
from app.api.schemas import ChunkItemResponse, KnowledgeFolderCreateRequest, KnowledgeFolderResponse, SourceContentResponse, SourceDetailResponse, SourceResponse
from app.application.services.source_service import create_knowledge_folder, create_source_revision, delete_knowledge_folder, delete_source, list_knowledge_folders, list_project_sources, list_source_chunks, read_source_content, read_source_download
from app.domain.errors import DomainError


def _failure(exc: DomainError) -> HTTPException:
    if exc.code == "AUTH_FORBIDDEN":
        code = status.HTTP_403_FORBIDDEN
    elif exc.code in {"INPUT_INVALID", "SOURCE_MEDIA_UNSUPPORTED", "SOURCE_TOO_LARGE"}:
        code = status.HTTP_422_UNPROCESSABLE_ENTITY
    elif exc.code in {"SOURCE_FROZEN_IN_SNAPSHOT", "SOURCE_NOT_READY"}:
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_404_NOT_FOUND
    return HTTPException(status_code=code, detail={"code": exc.code, "message": exc.message})


sources_router = APIRouter(prefix="/projects/{project_id}/sources")
folders_router = APIRouter(prefix="/projects/{project_id}/knowledge-folders")


@sources_router.get("", response_model=list[SourceDetailResponse])
def list_sources(project_id: UUID, session: SessionDep, user: CurrentUserDep) -> list[SourceDetailResponse]:
    try:
        return [SourceDetailResponse(**item) for item in list_project_sources(session, project_id=project_id, actor_id=user.id)]
    except DomainError as exc:
        raise _failure(exc)


@sources_router.get("/{source_id}", response_model=SourceContentResponse)
def read_content(project_id: UUID, source_id: UUID, session: SessionDep, user: CurrentUserDep) -> SourceContentResponse:
    try:
        return SourceContentResponse(**read_source_content(session, project_id=project_id, source_id=source_id, actor_id=user.id))
    except DomainError as exc:
        raise _failure(exc)


@sources_router.get("/{source_id}/download")
def download_source(project_id: UUID, source_id: UUID, session: SessionDep, user: CurrentUserDep) -> FileResponse:
    try:
        item = read_source_download(session, project_id=project_id, source_id=source_id, actor_id=user.id)
        return FileResponse(item["path"], media_type=item["media_type"], filename=item["filename"])
    except DomainError as exc:
        raise _failure(exc)


@sources_router.get("/{source_id}/chunks", response_model=list[ChunkItemResponse])
def list_chunks(project_id: UUID, source_id: UUID, session: SessionDep, user: CurrentUserDep) -> list[ChunkItemResponse]:
    try:
        return [ChunkItemResponse(**item) for item in list_source_chunks(session, project_id=project_id, source_id=source_id, actor_id=user.id)]
    except DomainError as exc:
        raise _failure(exc)


@sources_router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def upload(
    project_id: UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUserDep,
    file: UploadFile = File(...),
    source_role: str = Form(..., max_length=64),
    logical_name: str = Form(..., max_length=255),
    folder_id: UUID | None = Form(None),
    force_ocr: bool = Form(False),
    _: str = Depends(idempotency_key),
) -> SourceResponse:
    try:
        source, job = create_source_revision(
            session,
            project_id=project_id,
            source_role=source_role,
            logical_name=logical_name,
            original_filename=file.filename or logical_name,
            claimed_media_type=file.content_type,
            content=await file.read(),
            actor_id=user.id,
            correlation_id=correlation_id(request),
            folder_id=folder_id,
            force_ocr=force_ocr,
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
            ingestion_job_id=job.id,
            folder_id=source.folder_id,
            force_ocr=source.force_ocr,
        )
    except DomainError as exc:
        session.rollback()
        raise _failure(exc)


@sources_router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source_endpoint(project_id: UUID, source_id: UUID, session: SessionDep, user: CurrentUserDep) -> None:
    try:
        delete_source(session, project_id=project_id, source_id=source_id, actor_id=user.id)
        session.commit()
    except DomainError as exc:
        session.rollback()
        raise _failure(exc)


@folders_router.get("", response_model=list[KnowledgeFolderResponse])
def get_folders(project_id: UUID, session: SessionDep, user: CurrentUserDep) -> list[KnowledgeFolderResponse]:
    try:
        folders = list_knowledge_folders(session, project_id=project_id, actor_id=user.id)
        return [
            KnowledgeFolderResponse(
                id=folder.id, project_id=folder.project_id, name=folder.name,
                parent_folder_id=folder.parent_folder_id,
                created_at=folder.created_at, updated_at=folder.updated_at,
            )
            for folder in folders
        ]
    except DomainError as exc:
        raise _failure(exc)


@folders_router.post("", response_model=KnowledgeFolderResponse, status_code=status.HTTP_201_CREATED)
def create_folder(
    project_id: UUID,
    payload: KnowledgeFolderCreateRequest,
    request: Request,
    session: SessionDep,
    user: CurrentUserDep,
    _: str = Depends(idempotency_key),
) -> KnowledgeFolderResponse:
    try:
        folder = create_knowledge_folder(
            session,
            project_id=project_id,
            name=payload.name,
            parent_folder_id=payload.parent_folder_id,
            actor_id=user.id,
        )
        session.commit()
        return KnowledgeFolderResponse(
            id=folder.id, project_id=folder.project_id, name=folder.name,
            parent_folder_id=folder.parent_folder_id,
            created_at=folder.created_at, updated_at=folder.updated_at,
        )
    except DomainError as exc:
        session.rollback()
        raise _failure(exc)


@folders_router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(project_id: UUID, folder_id: UUID, session: SessionDep, user: CurrentUserDep) -> None:
    try:
        delete_knowledge_folder(session, project_id=project_id, folder_id=folder_id, actor_id=user.id)
        session.commit()
    except DomainError as exc:
        session.rollback()
        raise _failure(exc)
