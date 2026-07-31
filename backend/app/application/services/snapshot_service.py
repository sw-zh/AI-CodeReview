import hashlib
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.application.services.common import append_audit_event, require_project_role
from app.application.services.redaction import safe_excerpt
from app.domain.enums import ProjectRole, SourceProcessingStatus
from app.domain.errors import DomainError
from app.infrastructure.persistence.models import (
    DocumentChunk,
    EvidenceItem,
    InputSnapshot,
    InputSnapshotSource,
    InputSnapshotGit,
    InputSnapshotExternalEvidence,
    InputSnapshotManualEvidence,
    GitSnapshot,
    ExternalEvidence,
    ManualEvidence,
    VerificationCycle,
    VerificationTask,
    SourceRevision,
)


def freeze_preparation_snapshot(
    session: Session,
    *,
    cycle_id: UUID,
    source_revision_ids: list[UUID],
    actor_id: UUID,
    correlation_id: str,
) -> InputSnapshot:
    cycle = session.get(VerificationCycle, cycle_id)
    if cycle is None:
        raise DomainError("RESOURCE_NOT_FOUND", "核验轮次不存在")
    task = session.get(VerificationTask, cycle.task_id)
    if task is None:
        raise DomainError("RESOURCE_NOT_FOUND", "核验任务不存在")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    if cycle.business_status != "DRAFT":
        raise DomainError("STATE_CONFLICT", "只有草稿轮次可以冻结准备快照")
    if not source_revision_ids or len(set(source_revision_ids)) != len(source_revision_ids):
        raise DomainError("INPUT_INVALID", "至少选择一份且不重复的资料版本")

    sources = (
        session.query(SourceRevision)
        .filter(SourceRevision.id.in_(source_revision_ids), SourceRevision.project_id == task.project_id)
        .all()
    )
    if len(sources) != len(source_revision_ids):
        raise DomainError("INPUT_INVALID", "资料版本不存在或不属于当前项目")
    not_ready = [source.id for source in sources if source.processing_status != SourceProcessingStatus.READY]
    if not_ready:
        raise DomainError("SOURCE_NOT_READY", "所选资料尚未完成处理")

    normalized = {
        "cycleId": str(cycle.id),
        "purpose": "PREPARATION",
        "policyVersion": "v1",
        "workflowVersion": "v1",
        "sources": sorted(
            [
                {
                    "id": str(source.id),
                    "contentHash": source.content_hash,
                    "parserVersion": source.parser_version,
                }
                for source in sources
            ],
            key=lambda item: item["id"],
        ),
    }
    canonical = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    snapshot_hash = f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
    existing = session.query(InputSnapshot).filter_by(snapshot_hash=snapshot_hash).one_or_none()
    if existing is not None:
        return existing

    snapshot = InputSnapshot(
        cycle_id=cycle.id,
        snapshot_hash=snapshot_hash,
        policy_version="v1",
        workflow_version="v1",
        created_by=actor_id,
        purpose="PREPARATION",
    )
    session.add(snapshot)
    session.flush()
    for source in sources:
        session.add(
            InputSnapshotSource(
                snapshot_id=snapshot.id,
                source_revision_id=source.id,
                content_hash=source.content_hash,
                parser_version=source.parser_version or "unknown",
            )
        )
        chunks = (
            session.query(DocumentChunk)
            .filter_by(source_revision_id=source.id, index_version=source.parser_version)
            .order_by(DocumentChunk.chunk_index)
            .all()
        )
        for chunk in chunks:
            session.add(
                EvidenceItem(
                    project_id=task.project_id,
                    snapshot_id=snapshot.id,
                    source_type="DOCUMENT",
                    evidence_kind="RAW_FACT",
                    source_revision_id=source.id,
                    content_hash=chunk.text_hash,
                    excerpt_safe=safe_excerpt(chunk.content),
                    locator={
                        "sourceRevisionId": str(source.id),
                        "chunkId": str(chunk.id),
                        "chunkIndex": chunk.chunk_index,
                        **chunk.locator,
                    },
                    locator_precision="EXACT",
                    extractor_version=source.parser_version or "markdown-text-v1",
                )
            )
    append_audit_event(
        session,
        project_id=task.project_id,
        actor_id=actor_id,
        aggregate_type="InputSnapshot",
        aggregate_id=snapshot.id,
        action="PREPARATION_SNAPSHOT_FROZEN",
        correlation_id=correlation_id,
        payload={"snapshotHash": snapshot.snapshot_hash, "sourceRevisionIds": [str(x) for x in source_revision_ids]},
    )
    return snapshot


def freeze_formal_snapshot(
    session: Session,
    *,
    cycle_id: UUID,
    source_revision_ids: list[UUID],
    git_snapshot_id: UUID,
    external_evidence_ids: list[UUID],
    manual_evidence_ids: list[UUID],
    actor_id: UUID,
    correlation_id: str,
) -> InputSnapshot:
    cycle = session.get(VerificationCycle, cycle_id)
    task = session.get(VerificationTask, cycle.task_id) if cycle else None
    git = session.get(GitSnapshot, git_snapshot_id)
    if task is None or git is None or git.cycle_id != cycle_id:
        raise DomainError("GIT_RANGE_INVALID", "正式快照必须绑定当前轮次已冻结的 Git 范围")
    require_project_role(session, task.project_id, actor_id, {ProjectRole.SUBMITTER, ProjectRole.ADMIN})
    sources = session.query(SourceRevision).filter(SourceRevision.id.in_(source_revision_ids), SourceRevision.project_id == task.project_id).all()
    if len(sources) != len(set(source_revision_ids)) or any(x.processing_status != SourceProcessingStatus.READY for x in sources):
        raise DomainError("SOURCE_NOT_READY", "正式快照的全部资料必须存在且处于 READY")
    if len(external_evidence_ids) != len(set(external_evidence_ids)):
        raise DomainError("INPUT_INVALID", "external evidence cannot be selected twice")
    external_evidence = session.query(ExternalEvidence).filter(ExternalEvidence.id.in_(external_evidence_ids), ExternalEvidence.project_id == task.project_id, ExternalEvidence.cycle_id == cycle.id).all() if external_evidence_ids else []
    if len(external_evidence) != len(external_evidence_ids):
        raise DomainError("INPUT_INVALID", "external evidence does not belong to this verification cycle")
    if any(item.commit_sha != git.target_sha for item in external_evidence):
        raise DomainError("INPUT_STALE", "external evidence must bind the frozen target commit")
    if len(manual_evidence_ids) != len(set(manual_evidence_ids)):
        raise DomainError("INPUT_INVALID", "manual evidence cannot be selected twice")
    manual_evidence = session.query(ManualEvidence).filter(
        ManualEvidence.id.in_(manual_evidence_ids),
        ManualEvidence.project_id == task.project_id,
        ManualEvidence.cycle_id == cycle.id,
    ).all() if manual_evidence_ids else []
    if len(manual_evidence) != len(manual_evidence_ids):
        raise DomainError("INPUT_INVALID", "manual evidence does not belong to this verification cycle")
    normalized = {"purpose": "FORMAL", "cycleId": str(cycle.id), "policyVersion": "v1", "workflowVersion": "v1", "git": {"baseSha": git.base_sha, "targetSha": git.target_sha, "mergeBaseSha": git.merge_base_sha, "diffMode": git.diff_mode, "diffHash": git.diff_hash}, "sources": sorted([{"id": str(x.id), "hash": x.content_hash, "parser": x.parser_version} for x in sources], key=lambda x: x["id"]), "externalEvidence": sorted([{"id": str(x.id), "hash": x.content_hash, "commitSha": x.commit_sha, "type": x.evidence_type} for x in external_evidence], key=lambda x: x["id"]), "manualEvidence": sorted([{"id": str(x.id), "hash": x.content_hash, "submittedBy": str(x.submitted_by)} for x in manual_evidence], key=lambda x: x["id"])}
    snapshot_hash = f"sha256:{hashlib.sha256(json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}"
    existing = session.query(InputSnapshot).filter_by(snapshot_hash=snapshot_hash).one_or_none()
    if existing is not None: return existing
    snapshot = InputSnapshot(cycle_id=cycle.id, snapshot_hash=snapshot_hash, policy_version="v1", workflow_version="v1", created_by=actor_id, purpose="FORMAL")
    session.add(snapshot); session.flush()
    for source in sources:
        session.add(InputSnapshotSource(snapshot_id=snapshot.id, source_revision_id=source.id, content_hash=source.content_hash, parser_version=source.parser_version or "unknown"))
        chunks = session.query(DocumentChunk).filter_by(source_revision_id=source.id, index_version=source.parser_version).order_by(DocumentChunk.chunk_index).all()
        for chunk in chunks:
            session.add(EvidenceItem(project_id=task.project_id, snapshot_id=snapshot.id, source_type="DOCUMENT", evidence_kind="RAW_FACT", source_revision_id=source.id, content_hash=chunk.text_hash, excerpt_safe=safe_excerpt(chunk.content), locator={"sourceRevisionId": str(source.id), "chunkId": str(chunk.id), "chunkIndex": chunk.chunk_index, **chunk.locator}, locator_precision="EXACT", extractor_version=source.parser_version or "markdown-text-v1"))
    for item in external_evidence:
        session.add(InputSnapshotExternalEvidence(snapshot_id=snapshot.id, external_evidence_id=item.id, content_hash=item.content_hash, commit_sha=item.commit_sha))
        content = Path(item.artifact_uri).read_text(encoding="utf-8")
        session.add(EvidenceItem(project_id=task.project_id, snapshot_id=snapshot.id, source_type=item.evidence_type, evidence_kind="RAW_FACT", commit_sha=item.commit_sha, content_hash=item.content_hash, excerpt_safe=safe_excerpt(content), locator={"externalEvidenceId": str(item.id), "logicalName": item.logical_name, "commitSha": item.commit_sha, "exitCode": item.exit_code}, locator_precision="EXACT", extractor_version="external-evidence-v1"))
    for item in manual_evidence:
        session.add(InputSnapshotManualEvidence(snapshot_id=snapshot.id, manual_evidence_id=item.id, content_hash=item.content_hash))
        content = Path(item.artifact_uri).read_text(encoding="utf-8")
        session.add(EvidenceItem(
            project_id=task.project_id,
            snapshot_id=snapshot.id,
            source_type="MANUAL",
            evidence_kind="HUMAN_NOTE",
            content_hash=item.content_hash,
            excerpt_safe=safe_excerpt(content),
            locator={"manualEvidenceId": str(item.id), "logicalName": item.logical_name, "submittedBy": str(item.submitted_by)},
            locator_precision="EXACT",
            extractor_version="manual-evidence-v1",
            requires_human_confirmation=True,
        ))
    session.add(InputSnapshotGit(snapshot_id=snapshot.id, git_snapshot_id=git.id, diff_hash=git.diff_hash))
    append_audit_event(session, project_id=task.project_id, actor_id=actor_id, aggregate_type="InputSnapshot", aggregate_id=snapshot.id, action="FORMAL_SNAPSHOT_FROZEN", correlation_id=correlation_id, payload={"snapshotHash": snapshot.snapshot_hash, "gitSnapshotId": str(git.id)})
    return snapshot
