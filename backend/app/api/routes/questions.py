from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.api.dependencies import CurrentUserDep, SessionDep
from app.api.schemas import EvidenceQuestionRequest, EvidenceQuestionResponse
from app.application.services.citation_resolver import resolve_citation
from app.domain.errors import DomainError

router = APIRouter(prefix="/input-snapshots/{snapshot_id}/questions")


@router.post("", response_model=EvidenceQuestionResponse)
def ask(snapshot_id: UUID, payload: EvidenceQuestionRequest, session: SessionDep, user: CurrentUserDep) -> EvidenceQuestionResponse:
    try:
        evidence = [resolve_citation(session, evidence_id=item, snapshot_id=snapshot_id, actor_id=user.id) for item in payload.evidence_ids]
        citations = [{"evidenceId": str(item.id), "locator": item.locator, "precision": item.locator_precision} for item in evidence]
        excerpts = "；".join(item.excerpt_safe[:240] for item in evidence)
        return EvidenceQuestionResponse(answer=f"基于已授权的 {len(evidence)} 项证据：{excerpts}", fact_status="INSUFFICIENT_EVIDENCE", citations=citations)
    except DomainError as exc:
        raise HTTPException(status_code=422 if exc.code == "CITATION_INVALID" else 403, detail={"code": exc.code, "message": exc.message})
