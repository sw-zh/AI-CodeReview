from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.application.services.common import require_project_role
from app.core.config import get_settings
from app.domain.enums import ProjectRole
from app.domain.errors import DomainError
from app.domain.model_contracts import EmbeddingRequest
from app.infrastructure.embedding_model import create_embedding_model
from app.infrastructure.persistence.models import DocumentChunk, EvidenceItem, InputSnapshot, InputSnapshotSource, VerificationCycle, VerificationTask


def search_snapshot(session: Session, *, snapshot_id: UUID, query: str, limit: int, actor_id: UUID) -> list[dict]:
    snapshot = session.get(InputSnapshot, snapshot_id)
    cycle = session.get(VerificationCycle, snapshot.cycle_id) if snapshot else None
    task = session.get(VerificationTask, cycle.task_id) if cycle else None
    if task is None:
        raise DomainError("RESOURCE_NOT_FOUND", "输入快照不存在")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.REVIEWER, ProjectRole.ADMIN})
    source_ids = [item.source_revision_id for item in session.query(InputSnapshotSource).filter_by(snapshot_id=snapshot.id).all()]
    if not source_ids:
        return []
    tsquery = func.websearch_to_tsquery("simple", query)
    tsvector = func.to_tsvector("simple", DocumentChunk.content)
    rank = func.ts_rank_cd(tsvector, tsquery).label("fts_rank")
    fts_rows = session.query(DocumentChunk, rank).filter(DocumentChunk.source_revision_id.in_(source_ids), tsvector.op("@@")(tsquery)).order_by(rank.desc()).limit(limit * 3).all()
    candidates: dict[UUID, dict] = {}
    for position, (chunk, score) in enumerate(fts_rows, start=1):
        candidates[chunk.id] = {"chunk": chunk, "ftsRank": position, "ftsScore": float(score or 0)}

    try:
        vector = create_embedding_model(get_settings()).embed(EmbeddingRequest(text=query, model=get_settings().embedding_model)).vector
        distance = DocumentChunk.embedding.cosine_distance(vector).label("distance")
        vector_rows = session.query(DocumentChunk, distance).filter(DocumentChunk.source_revision_id.in_(source_ids), DocumentChunk.embedding.is_not(None)).order_by(distance).limit(limit * 3).all()
        for position, (chunk, score) in enumerate(vector_rows, start=1):
            candidate = candidates.setdefault(chunk.id, {"chunk": chunk})
            candidate["vectorRank"] = position
            candidate["vectorScore"] = 1 - float(score or 1)
    except DomainError:
        # Retrieval still serves exact lexical evidence when a cloud embedding model is unavailable.
        pass

    if not candidates:
        needle = query.lower()
        for chunk in session.query(DocumentChunk).filter(DocumentChunk.source_revision_id.in_(source_ids)).all():
            if needle in chunk.content.lower():
                candidates[chunk.id] = {"chunk": chunk, "ftsRank": 1, "ftsScore": 0.0}

    evidence = session.query(EvidenceItem).filter_by(snapshot_id=snapshot.id, source_type="DOCUMENT").all()
    evidence_by_chunk = {str(item.locator.get("chunkId")): item for item in evidence}
    fused: list[dict] = []
    for candidate in candidates.values():
        chunk = candidate["chunk"]
        item = evidence_by_chunk.get(str(chunk.id))
        if item is None:
            continue
        score = sum(1 / (60 + candidate[key]) for key in ("ftsRank", "vectorRank") if key in candidate)
        fused.append({
            "evidenceId": str(item.id),
            "excerpt": item.excerpt_safe,
            "locator": item.locator,
            "precision": item.locator_precision,
            "score": round(score, 6),
            "retrieval": {key: candidate[key] for key in ("ftsRank", "ftsScore", "vectorRank", "vectorScore") if key in candidate},
        })
    return sorted(fused, key=lambda item: item["score"], reverse=True)[:limit]
