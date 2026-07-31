from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.infrastructure.persistence.models import AnalysisCoverage, Claim, EvidenceItem, InputSnapshot, VerificationResult


class VerificationGraphState(TypedDict, total=False):
    analysis_run_id: str
    input_snapshot_id: str
    evidence_ids: list[str]
    claim_ids: list[str]
    verification_result_ids: list[str]
    coverage_id: str
    node_errors: list[str]
    workflow_schema_version: str


def run_verification_graph(session: Session, run_id: UUID, snapshot_id: UUID) -> VerificationGraphState:
    """Small deterministic v1 graph; model enrichment is an adapter added after this safe baseline."""

    def load_snapshot(state: VerificationGraphState) -> VerificationGraphState:
        snapshot = session.get(InputSnapshot, UUID(state["input_snapshot_id"]))
        evidence = session.query(EvidenceItem).filter_by(snapshot_id=snapshot.id).all() if snapshot else []
        return {"evidence_ids": [str(item.id) for item in evidence]}

    def create_claims(state: VerificationGraphState) -> VerificationGraphState:
        claims: list[str] = []
        for index, evidence_id in enumerate(state.get("evidence_ids", []), start=1):
            evidence = session.get(EvidenceItem, UUID(evidence_id))
            if evidence is None:
                continue
            claim = Claim(analysis_run_id=run_id, claim_key=f"DOC-{index}", claim_type="ACCEPTANCE_CANDIDATE", text=evidence.excerpt_safe, authority_level=3, source_revision_id=evidence.source_revision_id)
            session.add(claim)
            session.flush()
            claims.append(str(claim.id))
        return {"claim_ids": claims}

    def reconcile(state: VerificationGraphState) -> VerificationGraphState:
        results: list[str] = []
        for claim_id in state.get("claim_ids", []):
            result = VerificationResult(analysis_run_id=run_id, claim_id=UUID(claim_id), protocol_version="v1", status="INSUFFICIENT_EVIDENCE", reason="当前运行仅有资料证据，尚无冻结代码范围的有效支持或反驳证据", evidence_ids=state.get("evidence_ids", []), requires_human_confirmation=False, produced_by="DETERMINISTIC")
            session.add(result)
            session.flush()
            results.append(str(result.id))
        coverage = AnalysisCoverage(analysis_run_id=run_id, scope_kind="GIT", scope_ref="formal-snapshot", state="NOT_ANALYZED", reason_code="GIT_ANALYZER_PENDING")
        session.add(coverage)
        session.flush()
        return {"verification_result_ids": results, "coverage_id": str(coverage.id)}

    graph = StateGraph(VerificationGraphState)
    graph.add_node("load_snapshot", load_snapshot)
    graph.add_node("create_claims", create_claims)
    graph.add_node("reconcile", reconcile)
    graph.add_edge(START, "load_snapshot")
    graph.add_edge("load_snapshot", "create_claims")
    graph.add_edge("create_claims", "reconcile")
    graph.add_edge("reconcile", END)
    return graph.compile().invoke({"analysis_run_id": str(run_id), "input_snapshot_id": str(snapshot_id), "workflow_schema_version": "v1", "node_errors": []})
