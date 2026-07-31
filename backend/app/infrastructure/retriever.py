from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.ports import RetrievedChunk, RetrieverPort
from app.infrastructure.persistence.models import DocumentChunk


class PostgresHybridRetriever(RetrieverPort):
    """PostgreSQL FTS plus pgvector adapter, constrained by source revision IDs."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def search(self, *, source_revision_ids, query: str, limit: int, query_embedding: list[float] | None) -> list[RetrievedChunk]:
        tsquery = func.websearch_to_tsquery("simple", query)
        tsvector = func.to_tsvector("simple", DocumentChunk.content)
        rank = func.ts_rank_cd(tsvector, tsquery).label("fts_rank")
        candidates: dict = {}
        fts_rows = self._session.query(DocumentChunk, rank).filter(
            DocumentChunk.source_revision_id.in_(source_revision_ids),
            tsvector.op("@@")(tsquery),
        ).order_by(rank.desc()).limit(limit * 3).all()
        for position, (chunk, score) in enumerate(fts_rows, start=1):
            candidates[chunk.id] = RetrievedChunk(chunk_id=chunk.id, fts_rank=position, fts_score=float(score or 0))

        if query_embedding is not None:
            distance = DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")
            vector_rows = self._session.query(DocumentChunk, distance).filter(
                DocumentChunk.source_revision_id.in_(source_revision_ids),
                DocumentChunk.embedding.is_not(None),
            ).order_by(distance).limit(limit * 3).all()
            for position, (chunk, score) in enumerate(vector_rows, start=1):
                prior = candidates.get(chunk.id)
                candidates[chunk.id] = RetrievedChunk(
                    chunk_id=chunk.id,
                    fts_rank=prior.fts_rank if prior else None,
                    fts_score=prior.fts_score if prior else None,
                    vector_rank=position,
                    vector_score=1 - float(score or 1),
                )

        if not candidates:
            needle = query.lower()
            for chunk in self._session.query(DocumentChunk).filter(DocumentChunk.source_revision_id.in_(source_revision_ids)).all():
                if needle in chunk.content.lower():
                    candidates[chunk.id] = RetrievedChunk(chunk_id=chunk.id, fts_rank=1, fts_score=0.0)
        return list(candidates.values())
