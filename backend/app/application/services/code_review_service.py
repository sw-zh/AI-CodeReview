"""Evidence-bound planning and validation for the delivery code-review core."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.model_contracts import CodeReviewFindingChallengeProposal, CodeReviewFindingProposal
from app.infrastructure.persistence.models import Claim, CodeReviewFinding, CodeReviewFindingChallenge, EvidenceItem


def plan_code_review(*, bundle: dict, evidence_by_locator: dict[tuple[str, str], str], claims: list[Claim], char_budget: int) -> tuple[list[dict], dict]:
    """Create deterministic review inputs and an explicit unanalysed-range record."""
    claim_payload = [{"id": str(item.id), "text": item.text} for item in claims]
    selected: list[dict] = []
    skipped: list[dict] = []
    used = 0
    for file in bundle.get("files", []):
        path = str(file.get("path", ""))
        if file.get("binary") or file.get("context_state") == "SKIPPED":
            skipped.append({"path": path, "reasonCode": file.get("context_reason_code") or "NON_TEXT_CHANGE"})
            continue
        hunks: list[dict] = []
        for hunk in file.get("hunks", []):
            key = (path, str(hunk.get("header", "")))
            evidence_id = evidence_by_locator.get(key)
            if evidence_id is None:
                continue
            candidate = {"evidenceId": evidence_id, "header": hunk.get("header"), "oldStart": hunk.get("old_start"), "oldEnd": hunk.get("old_end"), "newStart": hunk.get("new_start"), "newEnd": hunk.get("new_end"), "payload": hunk.get("payload", "")}
            size = len(json.dumps(candidate, ensure_ascii=False))
            if used + size > char_budget:
                skipped.append({"path": path, "hunk": hunk.get("header"), "reasonCode": "CODE_REVIEW_BUDGET_EXHAUSTED"})
                continue
            hunks.append(candidate)
            used += size
        if hunks:
            context = {"base": file.get("base_context"), "target": file.get("target_context")}
            context_size = len(json.dumps(context, ensure_ascii=False))
            include_context = context_size <= max(char_budget - used, 0)
            if include_context:
                used += context_size
            elif context["base"] or context["target"]:
                skipped.append({"path": path, "reasonCode": "CODE_CONTEXT_BUDGET_EXHAUSTED"})
            selected.append({
                "path": path,
                "oldPath": file.get("old_path"),
                "editType": file.get("edit_type"),
                "hunks": hunks,
                "contextOnly": context if include_context else {"base": None, "target": None},
            })
    return selected, {"state": "ANALYZED" if selected else "PARTIAL", "details": {"inputCharBudget": char_budget, "inputCharsUsed": used, "analysedFiles": len(selected), "analysedHunks": sum(len(item["hunks"]) for item in selected), "unanalysed": skipped, "claims": claim_payload}}


def persist_validated_findings(
    session: Session,
    *,
    run_id: UUID,
    proposal_batch: list[CodeReviewFindingProposal],
    allowed_evidence_ids: set[UUID],
    allowed_claim_ids: set[UUID],
) -> tuple[list[CodeReviewFinding], int]:
    findings: list[CodeReviewFinding] = []
    rejected = 0
    for proposal in proposal_batch:
        if proposal.evidence_id not in allowed_evidence_ids or any(item not in allowed_claim_ids for item in proposal.related_claim_ids):
            rejected += 1
            continue
        evidence = session.get(EvidenceItem, proposal.evidence_id)
        if evidence is None or evidence.source_type != "CODE" or evidence.locator_precision != "EXACT":
            rejected += 1
            continue
        fingerprint_input = json.dumps({"evidence": str(proposal.evidence_id), "claims": sorted(str(item) for item in proposal.related_claim_ids), "kind": proposal.finding_kind, "title": proposal.title.strip().casefold(), "trigger": proposal.trigger_scenario.strip().casefold()}, sort_keys=True, ensure_ascii=False)
        fingerprint = f"sha256:{hashlib.sha256(fingerprint_input.encode('utf-8')).hexdigest()}"
        existing = session.query(CodeReviewFinding).filter_by(analysis_run_id=run_id, fingerprint=fingerprint).one_or_none()
        if existing is not None:
            findings.append(existing)
            continue
        finding = CodeReviewFinding(
            analysis_run_id=run_id,
            evidence_id=proposal.evidence_id,
            claim_id=proposal.related_claim_ids[0] if proposal.related_claim_ids else None,
            fingerprint=fingerprint,
            severity=proposal.severity,
            finding_kind=proposal.finding_kind,
            title=proposal.title,
            problem=proposal.problem,
            trigger_scenario=proposal.trigger_scenario,
            recommendation=proposal.recommendation,
            confidence=proposal.confidence,
            produced_by="MODEL",
            requires_human_confirmation=True,
            schema_version="code-review-finding-v1",
        )
        session.add(finding)
        findings.append(finding)
    session.flush()
    return findings, rejected


def plan_code_review_challenges(
    *,
    bundle: dict,
    findings: list[CodeReviewFinding],
    evidence_by_id: dict[UUID, EvidenceItem],
    claims_by_id: dict[UUID, Claim],
    char_budget: int,
    max_findings: int,
) -> tuple[list[dict], list[dict], list[dict], dict]:
    """Build only the frozen Hunk/context payload required to challenge persisted findings."""
    hunk_by_locator: dict[tuple[str, str], tuple[dict, dict]] = {}
    for file in bundle.get("files", []):
        path = str(file.get("path", ""))
        for hunk in file.get("hunks", []):
            hunk_by_locator[(path, str(hunk.get("header", "")))] = (file, hunk)

    selected_findings: list[dict] = []
    code_changes: list[dict] = []
    selected_claim_ids: set[UUID] = set()
    skipped: list[dict] = []
    used = 0
    for finding in findings[:max_findings]:
        evidence = evidence_by_id.get(finding.evidence_id)
        if evidence is None:
            skipped.append({"findingId": str(finding.id), "reasonCode": "FINDING_EVIDENCE_MISSING"})
            continue
        path = str(evidence.locator.get("path", ""))
        header = str(evidence.locator.get("hunk", ""))
        source = hunk_by_locator.get((path, header))
        if source is None:
            skipped.append({"findingId": str(finding.id), "reasonCode": "FINDING_HUNK_MISSING"})
            continue
        file, hunk = source
        hunk_payload = {
            "evidenceId": str(evidence.id),
            "header": header,
            "oldStart": hunk.get("old_start"),
            "oldEnd": hunk.get("old_end"),
            "newStart": hunk.get("new_start"),
            "newEnd": hunk.get("new_end"),
            "payload": hunk.get("payload", ""),
        }
        finding_payload = {
            "findingId": str(finding.id),
            "evidenceId": str(finding.evidence_id),
            "claimId": str(finding.claim_id) if finding.claim_id else None,
            "findingKind": finding.finding_kind,
            "severity": finding.severity,
            "title": finding.title,
            "problem": finding.problem,
            "triggerScenario": finding.trigger_scenario,
            "recommendation": finding.recommendation,
            "confidence": finding.confidence,
        }
        context = {"base": file.get("base_context"), "target": file.get("target_context")}
        code_change = {
            "path": path,
            "oldPath": file.get("old_path"),
            "editType": file.get("edit_type"),
            "hunks": [hunk_payload],
            "contextOnly": context,
        }
        candidate_size = len(json.dumps({"finding": finding_payload, "codeChange": code_change}, ensure_ascii=False))
        if used + candidate_size > char_budget:
            skipped.append({"findingId": str(finding.id), "path": path, "hunk": header, "reasonCode": "FINDING_CHALLENGE_BUDGET_EXHAUSTED"})
            continue
        used += candidate_size
        selected_findings.append(finding_payload)
        code_changes.append(code_change)
        if finding.claim_id is not None:
            selected_claim_ids.add(finding.claim_id)

    claims = [
        {"id": str(claim_id), "text": claims_by_id[claim_id].text}
        for claim_id in sorted(selected_claim_ids, key=str)
        if claim_id in claims_by_id
    ]
    return selected_findings, code_changes, claims, {
        "state": "ANALYZED" if selected_findings else "PARTIAL",
        "details": {
            "inputCharBudget": char_budget,
            "inputCharsUsed": used,
            "eligibleFindingCount": len(findings),
            "selectedFindingCount": len(selected_findings),
            "selectedFindingIds": [item["findingId"] for item in selected_findings],
            "unanalysed": skipped,
        },
    }


def persist_validated_challenges(
    session: Session,
    *,
    run_id: UUID,
    proposal_batch: list[CodeReviewFindingChallengeProposal],
    allowed_findings: dict[UUID, CodeReviewFinding],
    allowed_evidence_ids: set[UUID],
    model_call_id: UUID | None,
) -> tuple[list[CodeReviewFindingChallenge], int]:
    """Persist only challenge proposals tied to the original finding Hunk in this run."""
    challenges: list[CodeReviewFindingChallenge] = []
    rejected = 0
    seen: set[UUID] = set()
    for proposal in proposal_batch:
        finding = allowed_findings.get(proposal.finding_id)
        evidence_ids = list(dict.fromkeys(proposal.evidence_ids))
        if finding is None or proposal.finding_id in seen or finding.evidence_id not in evidence_ids or any(item not in allowed_evidence_ids for item in evidence_ids):
            rejected += 1
            continue
        evidence_items = [session.get(EvidenceItem, item) for item in evidence_ids]
        if any(item is None or item.source_type != "CODE" or item.locator_precision != "EXACT" for item in evidence_items):
            rejected += 1
            continue
        seen.add(proposal.finding_id)
        fingerprint_input = json.dumps(
            {
                "finding": str(finding.id),
                "verdict": proposal.verdict,
                "evidence": sorted(str(item) for item in evidence_ids),
                "reason": proposal.reason.strip().casefold(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        fingerprint = f"sha256:{hashlib.sha256(fingerprint_input.encode('utf-8')).hexdigest()}"
        existing = session.query(CodeReviewFindingChallenge).filter_by(analysis_run_id=run_id, finding_id=finding.id).one_or_none()
        if existing is not None:
            challenges.append(existing)
            continue
        challenge = CodeReviewFindingChallenge(
            analysis_run_id=run_id,
            finding_id=finding.id,
            fingerprint=fingerprint,
            verdict=proposal.verdict,
            reason=proposal.reason,
            evidence_ids=[str(item) for item in evidence_ids],
            model_call_id=model_call_id,
            schema_version="code-review-challenge-v1",
        )
        session.add(challenge)
        challenges.append(challenge)
    session.flush()
    return challenges, rejected
