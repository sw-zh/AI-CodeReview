import hashlib
import re
from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.errors import DomainError
from app.domain.model_contracts import GenerationRequest
from app.infrastructure.generation_model import create_generation_model
from app.infrastructure.git_reader import ReadOnlyGitReader
from app.infrastructure.persistence.models import (
    AnalysisCoverage,
    Claim,
    ClaimEvidenceLink,
    EvidenceItem,
    GitRepository,
    GitSnapshot,
    InputSnapshot,
    InputSnapshotGit,
    ModelCall,
    SourceRevision,
    VerificationCycle,
    VerificationResult,
    VerificationTask,
)


class VerificationGraphState(TypedDict, total=False):
    analysis_run_id: str
    input_snapshot_id: str
    evidence_ids: list[str]
    git_evidence_ids: list[str]
    external_evidence_ids: list[str]
    claim_ids: list[str]
    verification_result_ids: list[str]
    coverage_id: str
    node_errors: list[str]
    workflow_schema_version: str


_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|password|passwd|secret|token)\b(\s*[:=]\s*)([^\s,;]+)"
)
_ASCII_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
_KEY_TOKEN = re.compile(r"[A-Za-z]{2,}-\d+")
_CJK_TOKEN = re.compile(r"[\u4e00-\u9fff]{2,}")
_STOP_WORDS = {"this", "that", "with", "from", "true", "false", "none", "null", "return", "class", "function", "const", "import", "async", "await"}


def _safe_excerpt(text: str, limit: int = 1600) -> str:
    return _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", text)[:limit]


def _tokens(text: str) -> set[str]:
    ascii_tokens = {item.lower() for item in _ASCII_TOKEN.findall(text)}
    key_tokens = {item.lower() for item in _KEY_TOKEN.findall(text)}
    cjk_tokens = set(_CJK_TOKEN.findall(text))
    return (ascii_tokens | key_tokens | cjk_tokens) - _STOP_WORDS


def _claim_authority(source_role: str) -> int:
    return {"ACCEPTANCE": 4, "REQUIREMENT": 4, "DESIGN": 3, "MEETING": 2}.get(source_role.upper(), 1)


def _parse_hunks(diff: str) -> list[tuple[str, str, int | None, int | None, str]]:
    """Return path, header, new start/end and the immutable hunk payload."""
    hunks: list[tuple[str, str, int | None, int | None, str]] = []
    path: str | None = None
    header: str | None = None
    new_start: int | None = None
    new_line: int | None = None
    lines: list[str] = []

    def flush() -> None:
        nonlocal lines
        if path and header and lines:
            added = [line[1:] for line in lines if line.startswith("+") and not line.startswith("+++")]
            payload = "\n".join(added or lines)
            end = (new_line - 1) if new_line is not None else None
            hunks.append((path, header, new_start, end, payload))
        lines = []

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            flush()
            path = None
            header = None
            new_start = None
            new_line = None
        elif line.startswith("+++ "):
            candidate = line[4:].strip()
            path = candidate[2:] if candidate.startswith("b/") else (None if candidate == "/dev/null" else candidate)
        elif line.startswith("@@ "):
            flush()
            header = line
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            new_start = int(match.group(1)) if match else None
            new_line = new_start
        elif header is not None:
            lines.append(line)
            if new_line is not None and (line.startswith("+") or line.startswith(" ")) and not line.startswith("+++"):
                new_line += 1
    flush()
    return hunks


def run_verification_graph(session: Session, run_id: UUID, snapshot_id: UUID) -> VerificationGraphState:
    """Persist deterministic evidence first; heuristic matches never become CONFIRMED."""

    def load_snapshot(state: VerificationGraphState) -> VerificationGraphState:
        document_evidence = session.query(EvidenceItem).filter_by(snapshot_id=UUID(state["input_snapshot_id"]), source_type="DOCUMENT").all()
        external_evidence = session.query(EvidenceItem).filter(EvidenceItem.snapshot_id == UUID(state["input_snapshot_id"]), EvidenceItem.source_type.in_(("TEST", "BUILD"))).all()
        return {"evidence_ids": [str(item.id) for item in document_evidence], "external_evidence_ids": [str(item.id) for item in external_evidence]}

    def collect_git_evidence(state: VerificationGraphState) -> VerificationGraphState:
        snapshot = session.get(InputSnapshot, UUID(state["input_snapshot_id"]))
        binding = session.query(InputSnapshotGit).filter_by(snapshot_id=snapshot.id).one_or_none() if snapshot else None
        git_snapshot = session.get(GitSnapshot, binding.git_snapshot_id) if binding else None
        cycle = session.get(VerificationCycle, snapshot.cycle_id) if snapshot else None
        task = session.get(VerificationTask, cycle.task_id) if cycle else None
        repository = session.get(GitRepository, git_snapshot.repository_id) if git_snapshot else None
        if not all((snapshot, binding, git_snapshot, task, repository)):
            return {"node_errors": [*state.get("node_errors", []), "GIT_SNAPSHOT_MISSING"]}

        try:
            frozen = ReadOnlyGitReader().read_frozen_diff(
                repository.display_url,
                base_sha=git_snapshot.base_sha,
                target_sha=git_snapshot.target_sha,
                merge_base_sha=git_snapshot.merge_base_sha,
                diff_mode=git_snapshot.diff_mode,
                include_paths=git_snapshot.include_paths,
                exclude_paths=git_snapshot.exclude_paths,
                expected_diff_hash=binding.diff_hash,
            )
        except DomainError as exc:
            coverage = AnalysisCoverage(
                analysis_run_id=run_id,
                scope_kind="GIT",
                scope_ref="formal-snapshot",
                state="UNAVAILABLE",
                reason_code=exc.code,
            )
            session.add(coverage)
            session.flush()
            return {"coverage_id": str(coverage.id), "node_errors": [*state.get("node_errors", []), exc.code]}

        evidence_ids: list[str] = []
        for path, header, line_start, line_end, payload in _parse_hunks(frozen.diff):
            identity = f"{git_snapshot.target_sha}|{path}|{header}|{payload}"
            content_hash = f"sha256:{hashlib.sha256(identity.encode('utf-8')).hexdigest()}"
            evidence = session.query(EvidenceItem).filter_by(
                snapshot_id=snapshot.id,
                source_type="CODE",
                commit_sha=git_snapshot.target_sha,
                content_hash=content_hash,
            ).one_or_none()
            if evidence is None:
                evidence = EvidenceItem(
                    project_id=task.project_id,
                    snapshot_id=snapshot.id,
                    source_type="CODE",
                    evidence_kind="TOOL_FINDING",
                    commit_sha=git_snapshot.target_sha,
                    content_hash=content_hash,
                    excerpt_safe=_safe_excerpt(payload),
                    locator={
                        "commitSha": git_snapshot.target_sha,
                        "path": path,
                        "hunk": header,
                        "side": "NEW",
                        "lineStart": line_start,
                        "lineEnd": line_end,
                    },
                    locator_precision="EXACT" if line_start is not None else "APPROXIMATE",
                    extractor_version="git-diff-v1",
                )
                session.add(evidence)
                session.flush()
            evidence_ids.append(str(evidence.id))

        coverage = AnalysisCoverage(
            analysis_run_id=run_id,
            scope_kind="GIT",
            scope_ref="formal-snapshot",
            state="ANALYZED" if evidence_ids else "PARTIAL",
            reason_code=None if evidence_ids else "NO_TEXT_HUNKS",
        )
        session.add(coverage)
        session.flush()
        return {"git_evidence_ids": evidence_ids, "coverage_id": str(coverage.id)}

    def create_claims(state: VerificationGraphState) -> VerificationGraphState:
        claims: list[str] = []
        for index, evidence_id in enumerate(state.get("evidence_ids", []), start=1):
            evidence = session.get(EvidenceItem, UUID(evidence_id))
            source = session.get(SourceRevision, evidence.source_revision_id) if evidence and evidence.source_revision_id else None
            if evidence is None:
                continue
            claim = session.query(Claim).filter_by(analysis_run_id=run_id, claim_key=f"DOC-{index}").one_or_none()
            if claim is None:
                claim = Claim(
                    analysis_run_id=run_id,
                    claim_key=f"DOC-{index}",
                    claim_type="ACCEPTANCE_CANDIDATE",
                    text=evidence.excerpt_safe,
                    authority_level=_claim_authority(source.source_role) if source else 1,
                    source_revision_id=evidence.source_revision_id,
                )
                session.add(claim)
                session.flush()
            link = session.query(ClaimEvidenceLink).filter_by(claim_id=claim.id, evidence_id=evidence.id, relation="CONTEXT_ONLY").one_or_none()
            if link is None:
                session.add(ClaimEvidenceLink(claim_id=claim.id, evidence_id=evidence.id, relation="CONTEXT_ONLY", reason="资料原文定义待核验目标", confidence=1.0, produced_by="DETERMINISTIC"))
            claims.append(str(claim.id))
        return {"claim_ids": claims}

    def link_deterministic(state: VerificationGraphState) -> VerificationGraphState:
        actual_evidence = [session.get(EvidenceItem, UUID(item)) for item in [*state.get("git_evidence_ids", []), *state.get("external_evidence_ids", [])]]
        actual_evidence = [item for item in actual_evidence if item is not None]
        for claim_id in state.get("claim_ids", []):
            claim = session.get(Claim, UUID(claim_id))
            if claim is None:
                continue
            claim_tokens = _tokens(claim.text)
            supporting: list[EvidenceItem] = []
            for evidence in actual_evidence:
                overlap = claim_tokens & _tokens(evidence.excerpt_safe)
                if not overlap:
                    continue
                supporting.append(evidence)
                link = session.query(ClaimEvidenceLink).filter_by(claim_id=claim.id, evidence_id=evidence.id, relation="SUPPORTS").one_or_none()
                if link is None:
                    session.add(ClaimEvidenceLink(
                        claim_id=claim.id,
                        evidence_id=evidence.id,
                        relation="SUPPORTS",
                        reason=f"确定性标识符命中：{', '.join(sorted(overlap)[:5])}",
                        confidence=0.75,
                        produced_by="DETERMINISTIC",
                        requires_human_confirmation=True,
                    ))
        # The next node validates uniqueness against persisted links, including these ones.
        session.flush()
        return {}

    def propose_model_links(state: VerificationGraphState) -> VerificationGraphState:
        actual_evidence = [session.get(EvidenceItem, UUID(item)) for item in [*state.get("git_evidence_ids", []), *state.get("external_evidence_ids", [])]]
        actual_evidence = [item for item in actual_evidence if item is not None]
        claims = [session.get(Claim, UUID(item)) for item in state.get("claim_ids", [])]
        claims = [item for item in claims if item is not None]
        allowed_ids = {str(item.id) for item in actual_evidence}
        request = GenerationRequest(
            run_id=run_id,
            prompt_version="v1",
            schema_version="v1",
            claims=[
                {
                    "id": str(claim.id),
                    "text": claim.text,
                    "candidateEvidenceIds": [
                        str(evidence.id) for evidence in actual_evidence if _tokens(claim.text) & _tokens(evidence.excerpt_safe)
                    ],
                }
                for claim in claims
            ],
            evidence=[{"id": str(item.id), "excerpt": item.excerpt_safe, "locator": item.locator} for item in actual_evidence],
        )
        settings = get_settings()
        try:
            model = create_generation_model(settings)
            generated = model.generate(request)
            session.add(ModelCall(
                run_id=run_id,
                provider=generated.provider,
                model=generated.model,
                operation="LINK_PROPOSAL",
                prompt_version=request.prompt_version,
                schema_version=request.schema_version,
                allowed_evidence_ids=sorted(allowed_ids),
                status="SUCCEEDED",
                latency_ms=generated.latency_ms,
                attempts=generated.attempts,
            ))
            claim_ids = {str(item.id) for item in claims}
            for proposal in generated.proposals.proposals:
                if str(proposal.claim_id) not in claim_ids or str(proposal.evidence_id) not in allowed_ids:
                    continue
                existing = session.query(ClaimEvidenceLink).filter_by(
                    claim_id=proposal.claim_id,
                    evidence_id=proposal.evidence_id,
                    relation=proposal.relation,
                ).one_or_none()
                if existing is None:
                    session.add(ClaimEvidenceLink(
                        claim_id=proposal.claim_id,
                        evidence_id=proposal.evidence_id,
                        relation=proposal.relation,
                        reason=proposal.rationale,
                        confidence=0.5,
                        produced_by="MODEL",
                        requires_human_confirmation=True,
                    ))
            session.add(AnalysisCoverage(analysis_run_id=run_id, scope_kind="MODEL", scope_ref="link-proposal", state="ANALYZED"))
            session.flush()
            return {}
        except DomainError as exc:
            session.add(ModelCall(
                run_id=run_id,
                provider=settings.generation_provider,
                model=settings.gemini_generation_model if settings.generation_provider == "gemini" else "fake-model-v1",
                operation="LINK_PROPOSAL",
                prompt_version=request.prompt_version,
                schema_version=request.schema_version,
                allowed_evidence_ids=sorted(allowed_ids),
                status="FAILED",
                attempts=2 if exc.code == "MODEL_SCHEMA_INVALID" else 1,
                error_code=exc.code,
                error_summary=exc.message[:500],
            ))
            session.add(AnalysisCoverage(analysis_run_id=run_id, scope_kind="MODEL", scope_ref="link-proposal", state="UNAVAILABLE", reason_code=exc.code))
            return {"node_errors": [*state.get("node_errors", []), exc.code]}

    def reconcile(state: VerificationGraphState) -> VerificationGraphState:
        results: list[str] = []
        for claim_id in state.get("claim_ids", []):
            claim = session.get(Claim, UUID(claim_id))
            if claim is None:
                continue
            links = session.query(ClaimEvidenceLink).filter_by(claim_id=claim.id).all()
            deterministic_supports = [item for item in links if item.relation == "SUPPORTS" and item.produced_by == "DETERMINISTIC"]
            model_supports = [item for item in links if item.relation == "SUPPORTS" and item.produced_by == "MODEL"]
            deterministic_conflicts = [item for item in links if item.relation == "CONTRADICTS" and item.produced_by == "DETERMINISTIC"]
            evidence_ids = [str(item.evidence_id) for item in [*deterministic_supports, *model_supports]]
            if deterministic_conflicts:
                status = "CONFLICTING"
                reason = "存在可追溯的确定性反驳证据，不能由模型自行裁决"
                needs_confirmation = True
            elif deterministic_supports:
                status = "PARTIALLY_SUPPORTED"
                reason = "已发现冻结 Git 范围内的确定性标识符命中；语义满足度仍需人工确认"
                needs_confirmation = True
            elif model_supports:
                status = "INFERENCE_REQUIRES_CONFIRMATION"
                reason = "仅有模型提出的证据关联，尚未形成确定性支持结论"
                needs_confirmation = True
            else:
                status = "INSUFFICIENT_EVIDENCE"
                reason = "冻结 Git 范围内没有可验证的确定性代码支持证据"
                needs_confirmation = False
            result = session.query(VerificationResult).filter_by(analysis_run_id=run_id, claim_id=claim.id).one_or_none()
            if result is None:
                result = VerificationResult(
                    analysis_run_id=run_id,
                    claim_id=claim.id,
                    protocol_version="v1",
                    status=status,
                    reason=reason,
                    evidence_ids=evidence_ids,
                    requires_human_confirmation=needs_confirmation,
                    produced_by="DETERMINISTIC",
                )
                session.add(result)
                session.flush()
            results.append(str(result.id))
        return {"verification_result_ids": results}

    graph = StateGraph(VerificationGraphState)
    graph.add_node("load_snapshot", load_snapshot)
    graph.add_node("collect_git_evidence", collect_git_evidence)
    graph.add_node("create_claims", create_claims)
    graph.add_node("link_deterministic", link_deterministic)
    graph.add_node("propose_model_links", propose_model_links)
    graph.add_node("reconcile", reconcile)
    graph.add_edge(START, "load_snapshot")
    graph.add_edge("load_snapshot", "collect_git_evidence")
    graph.add_edge("collect_git_evidence", "create_claims")
    graph.add_edge("create_claims", "link_deterministic")
    graph.add_edge("link_deterministic", "propose_model_links")
    graph.add_edge("propose_model_links", "reconcile")
    graph.add_edge("reconcile", END)
    return graph.compile().invoke({
        "analysis_run_id": str(run_id),
        "input_snapshot_id": str(snapshot_id),
        "workflow_schema_version": "v1",
        "node_errors": [],
    })
