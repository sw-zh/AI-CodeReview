import hashlib
from pathlib import Path
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.application.services.common import append_audit_event, require_project_role
from app.core.config import get_settings
from app.domain.enums import ProjectRole, SourceProcessingStatus
from app.domain.errors import DomainError
from app.domain.model_contracts import EmbeddingRequest
from app.infrastructure.embedding_model import create_embedding_model
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

    root = Path(get_settings().artifact_root).resolve()
    target_dir = root / str(project_id) / str(source.id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "source.txt"
    target.write_bytes(content)
    source.artifact_uri = str(target)

    # The first slice has deterministic UTF-8 parsing only, but records every state transition.
    source.processing_status = SourceProcessingStatus.PARSING
    source.parser_version = "markdown-text-v1"
    source.processing_status = SourceProcessingStatus.CHUNKING
    text = content.decode("utf-8")
    paragraphs = [part.strip() for part in text.replace("\r\n", "\n").split("\n\n") if part.strip()]
    embedding_model = create_embedding_model(get_settings())
    for index, paragraph in enumerate(paragraphs or [text.strip()]):
        start = text.find(paragraph)
        embedding = embedding_model.embed(EmbeddingRequest(text=paragraph, model=get_settings().embedding_model))
        session.add(
            DocumentChunk(
                source_revision_id=source.id,
                chunk_index=index,
                content=paragraph,
                text_hash=f"sha256:{hashlib.sha256(paragraph.encode('utf-8')).hexdigest()}",
                locator={"paragraph": index + 1, "charStart": max(start, 0), "charEnd": max(start, 0) + len(paragraph)},
                index_version="markdown-text-v1",
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
