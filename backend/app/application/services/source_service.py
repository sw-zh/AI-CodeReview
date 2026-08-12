import hashlib
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.application.services.common import append_audit_event, require_project_role
from app.core.config import get_settings
from app.domain.enums import ProjectRole, SourceProcessingStatus
from app.domain.errors import DomainError
from app.domain.model_contracts import EmbeddingRequest
from app.infrastructure.embedding_model import create_embedding_model, embedding_index_version
from app.infrastructure.artifact_storage import LocalArtifactStorage
from app.infrastructure.document_parser import MarkdownTextDocumentParser
from app.infrastructure.persistence.models import DocumentChunk, SourceRevision

ALLOWED_MEDIA_TYPES = {"text/plain", "text/markdown"}


def create_source_revision(
    session: Session,
    *,
    project_id: UUID,
    source_role: str,
    logical_name: str,
    media_type: str,
    content: bytes,
    actor_id: UUID,
    correlation_id: str,
) -> SourceRevision:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    if media_type not in ALLOWED_MEDIA_TYPES:
        raise DomainError("SOURCE_MEDIA_UNSUPPORTED", "v1 当前仅支持 Markdown 与纯文本资料")
    if not content:
        raise DomainError("SOURCE_EMPTY", "资料内容不能为空")
    if len(content) > 2 * 1024 * 1024:
        raise DomainError("SOURCE_TOO_LARGE", "v1 单份文本资料限制为 2 MiB")
    try:
        content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DomainError("SOURCE_ENCODING_INVALID", "资料必须为 UTF-8 编码") from exc

    revision_no = (
        session.query(func.coalesce(func.max(SourceRevision.revision_no), 0))
        .filter(SourceRevision.project_id == project_id, SourceRevision.logical_name == logical_name)
        .scalar()
        + 1
    )
    source = SourceRevision(
        project_id=project_id,
        source_role=source_role,
        logical_name=logical_name,
        revision_no=revision_no,
        content_hash=f"sha256:{hashlib.sha256(content).hexdigest()}",
        artifact_uri="pending://artifact",
        media_type=media_type,
        processing_status=SourceProcessingStatus.UPLOADED,
    )
    session.add(source)
    session.flush()

    storage = LocalArtifactStorage(get_settings().artifact_root)
    source.artifact_uri = storage.write_bytes([str(project_id), str(source.id)], "source.txt", content)

    # The first slice has deterministic UTF-8 parsing only, but records every state transition.
    source.processing_status = SourceProcessingStatus.PARSING
    parser = MarkdownTextDocumentParser()
    source.parser_version = parser.version
    source.processing_status = SourceProcessingStatus.CHUNKING
    text = content.decode("utf-8")
    embedding_model = create_embedding_model(get_settings())
    for index, chunk in enumerate(parser.parse(text)):
        embedding = embedding_model.embed(EmbeddingRequest(text=chunk.content, model=get_settings().embedding_model_name))
        session.add(
            DocumentChunk(
                source_revision_id=source.id,
                chunk_index=index,
                content=chunk.content,
                text_hash=f"sha256:{hashlib.sha256(chunk.content.encode('utf-8')).hexdigest()}",
                locator=chunk.locator,
                index_version=embedding_index_version(parser.version, embedding),
                embedding=embedding.vector,
            )
        )
    source.processing_status = SourceProcessingStatus.INDEXING
    source.processing_status = SourceProcessingStatus.READY
    append_audit_event(
        session,
        project_id=project_id,
        actor_id=actor_id,
        aggregate_type="SourceRevision",
        aggregate_id=source.id,
        action="SOURCE_REVISION_READY",
        correlation_id=correlation_id,
        payload={"contentHash": source.content_hash, "revisionNo": revision_no},
    )
    return source


def list_project_sources(
    session: Session, *, project_id: UUID, actor_id: UUID
) -> list[dict]:
    require_project_role(
        session, project_id, actor_id,
        {ProjectRole.SUBMITTER, ProjectRole.REVIEWER, ProjectRole.ADMIN},
    )
    from app.infrastructure.persistence.models import InputSnapshotSource
    sources = (
        session.query(SourceRevision)
        .filter_by(project_id=project_id)
        .order_by(SourceRevision.created_at.desc())
        .all()
    )
    frozen: set[UUID] = set()
    if sources:
        rows = (
            session.query(InputSnapshotSource.source_revision_id)
            .filter(InputSnapshotSource.source_revision_id.in_([s.id for s in sources]))
            .distinct()
            .all()
        )
        frozen = {row[0] for row in rows}
    return [
        {
            "id": s.id,
            "project_id": s.project_id,
            "logical_name": s.logical_name,
            "source_role": s.source_role,
            "revision_no": s.revision_no,
            "content_hash": s.content_hash,
            "media_type": s.media_type,
            "processing_status": s.processing_status,
            "parser_version": s.parser_version,
            "in_snapshot": s.id in frozen,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
        }
        for s in sources
    ]


def read_source_content(
    session: Session, *, project_id: UUID, source_id: UUID, actor_id: UUID
) -> dict:
    require_project_role(
        session, project_id, actor_id,
        {ProjectRole.SUBMITTER, ProjectRole.REVIEWER, ProjectRole.ADMIN},
    )
    source = session.get(SourceRevision, source_id)
    if source is None or source.project_id != project_id:
        raise DomainError("RESOURCE_NOT_FOUND", "资料版本不存在")
    storage = LocalArtifactStorage(get_settings().artifact_root)
    return {
        "content": storage.read_text(source.artifact_uri),
        "media_type": source.media_type,
        "logical_name": source.logical_name,
    }


def list_source_chunks(
    session: Session, *, project_id: UUID, source_id: UUID, actor_id: UUID
) -> list[dict]:
    require_project_role(
        session, project_id, actor_id,
        {ProjectRole.SUBMITTER, ProjectRole.REVIEWER, ProjectRole.ADMIN},
    )
    source = session.get(SourceRevision, source_id)
    if source is None or source.project_id != project_id:
        raise DomainError("RESOURCE_NOT_FOUND", "资料版本不存在")
    chunks = (
        session.query(DocumentChunk)
        .filter_by(source_revision_id=source_id)
        .order_by(DocumentChunk.chunk_index)
        .all()
    )
    return [
        {
            "id": c.id,
            "chunk_index": c.chunk_index,
            "content": c.content,
            "locator": c.locator,
            "index_version": c.index_version,
        }
        for c in chunks
    ]
