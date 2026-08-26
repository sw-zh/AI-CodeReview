"""Project knowledge source versions and durable multi-format ingestion."""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.application.services.common import append_audit_event, require_project_role
from app.application.services.retrieval_index_service import ensure_initial_retrieval_index
from app.core.config import get_settings
from app.domain.enums import ProjectRole, SourceProcessingStatus
from app.domain.errors import DomainError
from app.domain.model_contracts import EmbeddingRequest
from app.infrastructure.artifact_storage import LocalArtifactStorage
from app.infrastructure.document_parser import DocumentExtractionError, detect_media_type, extract_document, supported_extensions
from app.infrastructure.embedding_model import create_embedding_model, embedding_index_version
from app.infrastructure.persistence.models import DocumentChunk, InputSnapshotSource, SourceIngestionJob, SourceRevision


_CANONICAL_PARSER_VERSION = "knowledge-extraction-v1"


def _normalize_uploaded_filename(filename: str) -> str:
    """Repair the common UTF-8-as-Latin-1 multipart filename fallback.

    Browsers generally send UTF-8 directly, but some HTTP clients use the
    legacy filename parameter.  Keep valid Unicode untouched and only repair
    a reversible mojibake representation.
    """

    try:
        return filename.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return filename


def create_source_revision(
    session: Session,
    *,
    project_id: UUID,
    source_role: str,
    logical_name: str,
    original_filename: str,
    claimed_media_type: str | None,
    content: bytes,
    actor_id: UUID,
    correlation_id: str,
) -> tuple[SourceRevision, SourceIngestionJob]:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    original_filename = _normalize_uploaded_filename(original_filename)
    settings = get_settings()
    if len(content) > settings.source_max_bytes:
        raise DomainError("SOURCE_TOO_LARGE", f"单份资料不能超过 {settings.source_max_bytes // 1024 // 1024} MiB")
    try:
        media_type = detect_media_type(filename=original_filename, claimed_media_type=claimed_media_type, content=content)
    except DocumentExtractionError as exc:
        raise DomainError(exc.code, exc.message) from exc
    revision_no = (
        session.query(func.coalesce(func.max(SourceRevision.revision_no), 0))
        .filter(SourceRevision.project_id == project_id, SourceRevision.logical_name == logical_name)
        .scalar()
        + 1
    )
    safe_extension = Path(original_filename).suffix.lower()
    source = SourceRevision(
        project_id=project_id,
        source_role=source_role,
        logical_name=logical_name,
        revision_no=revision_no,
        content_hash=f"sha256:{hashlib.sha256(content).hexdigest()}",
        artifact_uri="pending://artifact",
        original_filename=Path(original_filename).name,
        media_type=media_type,
        processing_status=SourceProcessingStatus.UPLOADED,
    )
    session.add(source)
    session.flush()
    storage = LocalArtifactStorage(settings.artifact_root)
    source.artifact_uri = storage.write_bytes([str(project_id), str(source.id)], f"source{safe_extension}", content)
    job = SourceIngestionJob(source_revision_id=source.id, requested_by=actor_id, max_attempts=settings.job_max_attempts)
    session.add(job)
    append_audit_event(
        session,
        project_id=project_id,
        actor_id=actor_id,
        aggregate_type="SourceRevision",
        aggregate_id=source.id,
        action="SOURCE_INGESTION_QUEUED",
        correlation_id=correlation_id,
        payload={"contentHash": source.content_hash, "revisionNo": revision_no, "mediaType": media_type},
    )
    return source, job


def process_source_ingestion(session: Session, *, job: SourceIngestionJob, correlation_id: str) -> None:
    source = session.get(SourceRevision, job.source_revision_id)
    if source is None:
        raise DomainError("RESOURCE_NOT_FOUND", "资料版本不存在")
    settings = get_settings()
    source.processing_status = SourceProcessingStatus.PARSING
    source.failure_code = None
    source.extraction_metadata = {}
    try:
        storage = LocalArtifactStorage(settings.artifact_root)
        extraction = extract_document(
            content=storage.read_bytes(source.artifact_uri),
            filename=source.original_filename,
            media_type=source.media_type,
            pdf_max_pages=settings.source_pdf_max_pages,
            timeout_seconds=settings.source_ingestion_timeout_seconds,
        )
        ocr_confidence = extraction.metadata.get("ocrConfidence")
        if ocr_confidence is not None:
            source.processing_status = SourceProcessingStatus.OCR_CHECKING
            page_confidences = [item.get("confidence", 0.0) for item in extraction.metadata.get("ocrPages", [])]
            if ocr_confidence < settings.source_ocr_min_average_confidence or any(value < settings.source_ocr_min_page_confidence for value in page_confidences):
                raise DocumentExtractionError("SOURCE_OCR_LOW_CONFIDENCE", "OCR 置信度不足，请上传可编辑原件或补充人工证据")
        if not extraction.chunks:
            raise DocumentExtractionError("SOURCE_EMPTY", "资料未能解析出可索引内容")
        # Every extractor produces the same normalized-text chunk contract, so
        # a project can safely mix Word, PDF, spreadsheet and image sources.
        source.parser_version = _CANONICAL_PARSER_VERSION
        source.ocr_confidence = ocr_confidence
        source.extraction_metadata = {**extraction.metadata, "extractorVersion": extraction.parser_version}
        source.extracted_artifact_uri = storage.write_bytes([str(source.project_id), str(source.id)], "extracted.txt", extraction.normalized_text.encode("utf-8"))
        source.processing_status = SourceProcessingStatus.CHUNKING
        source.processing_status = SourceProcessingStatus.INDEXING
        chunk_rows = [
            {
                "chunk_index": index,
                "content": chunk.content,
                "text_hash": f"sha256:{hashlib.sha256(chunk.content.encode('utf-8')).hexdigest()}",
                "locator": chunk.locator,
            }
            for index, chunk in enumerate(extraction.chunks)
        ]
        try:
            embedding_model = create_embedding_model(settings)
            embedded_rows = [
                (item, embedding_model.embed(EmbeddingRequest(text=item["content"], model=settings.embedding_model_name)))
                for item in chunk_rows
            ]
            embedding = embedded_rows[-1][1]
            index_version = embedding_index_version(_CANONICAL_PARSER_VERSION, embedding)
            for item, result in embedded_rows:
                session.add(DocumentChunk(source_revision_id=source.id, index_version=index_version, embedding=result.vector, **item))
            ensure_initial_retrieval_index(
                session,
                project_id=source.project_id,
                index_version=index_version,
                parser_version=_CANONICAL_PARSER_VERSION,
                embedding=embedding,
                actor_id=job.requested_by,
                correlation_id=correlation_id,
            )
        except DomainError as exc:
            if exc.code not in {"MODEL_UNAVAILABLE", "MODEL_NOT_CONFIGURED"}:
                raise
            # A cloud embedding outage cannot make already extracted evidence
            # disappear.  Keep a real normalized record and use lexical search;
            # no fake vector or fabricated embedding is written.
            source.extraction_metadata = {
                **source.extraction_metadata,
                "indexing": {"status": "UNAVAILABLE", "code": exc.code, "message": exc.message},
            }
            index_version = f"{_CANONICAL_PARSER_VERSION}|embedding:unavailable"
            for item in chunk_rows:
                session.add(DocumentChunk(source_revision_id=source.id, index_version=index_version, embedding=None, **item))
        source.processing_status = SourceProcessingStatus.READY
        append_audit_event(
            session,
            project_id=source.project_id,
            actor_id=job.requested_by,
            aggregate_type="SourceRevision",
            aggregate_id=source.id,
            action="SOURCE_REVISION_READY",
            correlation_id=correlation_id,
            payload={"contentHash": source.content_hash, "parserVersion": source.parser_version, "ocrConfidence": source.ocr_confidence},
        )
    except DocumentExtractionError as exc:
        source.processing_status = SourceProcessingStatus.FAILED
        source.failure_code = exc.code
        raise DomainError(exc.code, exc.message) from exc
    except DomainError:
        source.processing_status = SourceProcessingStatus.FAILED
        raise
    except Exception as exc:
        source.processing_status = SourceProcessingStatus.FAILED
        source.failure_code = "SOURCE_INGESTION_FAILED"
        raise DomainError("SOURCE_INGESTION_FAILED", "资料解析、OCR 或索引失败") from exc


def list_project_sources(session: Session, *, project_id: UUID, actor_id: UUID) -> list[dict]:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.REVIEWER, ProjectRole.ADMIN})
    sources = session.query(SourceRevision).filter_by(project_id=project_id).order_by(SourceRevision.created_at.desc()).all()
    frozen = set()
    if sources:
        frozen = {row[0] for row in session.query(InputSnapshotSource.source_revision_id).filter(InputSnapshotSource.source_revision_id.in_([s.id for s in sources])).distinct().all()}
    jobs = {item.source_revision_id: item for item in session.query(SourceIngestionJob).filter(SourceIngestionJob.source_revision_id.in_([s.id for s in sources])).all()} if sources else {}
    return [_source_projection(source, in_snapshot=source.id in frozen, job=jobs.get(source.id)) for source in sources]


def _source_projection(source: SourceRevision, *, in_snapshot: bool, job: SourceIngestionJob | None) -> dict:
    return {
        "id": source.id, "project_id": source.project_id, "logical_name": source.logical_name, "source_role": source.source_role,
        "revision_no": source.revision_no, "content_hash": source.content_hash, "media_type": source.media_type,
        "original_filename": source.original_filename, "processing_status": source.processing_status, "parser_version": source.parser_version,
        "failure_code": source.failure_code, "ocr_confidence": source.ocr_confidence, "extraction_metadata": source.extraction_metadata or {},
        "ingestion_job_status": job.job_status if job else None, "in_snapshot": in_snapshot,
        "created_at": source.created_at, "updated_at": source.updated_at,
    }


def read_source_content(session: Session, *, project_id: UUID, source_id: UUID, actor_id: UUID) -> dict:
    source = _require_source(session, project_id=project_id, source_id=source_id, actor_id=actor_id)
    if source.extracted_artifact_uri is None:
        raise DomainError("SOURCE_NOT_READY", "资料尚未提取出可阅读的知识内容")
    return {"content": LocalArtifactStorage(get_settings().artifact_root).read_text(source.extracted_artifact_uri), "media_type": source.media_type, "logical_name": source.logical_name, "original_filename": source.original_filename, "locator_summary": source.extraction_metadata or {}}


def read_source_download(session: Session, *, project_id: UUID, source_id: UUID, actor_id: UUID) -> dict:
    source = _require_source(session, project_id=project_id, source_id=source_id, actor_id=actor_id)
    return {"path": LocalArtifactStorage(get_settings().artifact_root).resolve_path(source.artifact_uri), "media_type": source.media_type, "filename": source.original_filename}


def list_source_chunks(session: Session, *, project_id: UUID, source_id: UUID, actor_id: UUID) -> list[dict]:
    _require_source(session, project_id=project_id, source_id=source_id, actor_id=actor_id)
    chunks = session.query(DocumentChunk).filter_by(source_revision_id=source_id).order_by(DocumentChunk.chunk_index).all()
    return [{"id": chunk.id, "chunk_index": chunk.chunk_index, "content": chunk.content, "locator": chunk.locator, "index_version": chunk.index_version} for chunk in chunks]


def _require_source(session: Session, *, project_id: UUID, source_id: UUID, actor_id: UUID) -> SourceRevision:
    require_project_role(session, project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.REVIEWER, ProjectRole.ADMIN})
    source = session.get(SourceRevision, source_id)
    if source is None or source.project_id != project_id:
        raise DomainError("RESOURCE_NOT_FOUND", "资料版本不存在")
    return source


__all__ = ["create_source_revision", "list_project_sources", "list_source_chunks", "process_source_ingestion", "read_source_content", "read_source_download", "supported_extensions"]
