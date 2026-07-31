import hashlib
import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.application.services.common import append_audit_event, require_project_role
from app.domain.enums import ProjectRole, SourceProcessingStatus
from app.domain.errors import DomainError
from app.infrastructure.persistence.models import (
    DocumentChunk,
    EvidenceItem,
    InputSnapshot,
    InputSnapshotSource,
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
        chunk = (
            session.query(DocumentChunk)
            .filter_by(source_revision_id=source.id, index_version=source.parser_version)
            .order_by(DocumentChunk.chunk_index)
            .first()
        )
        if chunk is not None:
            session.add(
                EvidenceItem(
                    project_id=task.project_id,
                    snapshot_id=snapshot.id,
                    source_type="DOCUMENT",
                    evidence_kind="RAW_FACT",
                    source_revision_id=source.id,
                    content_hash=chunk.text_hash,
                    excerpt_safe=chunk.content[:1000],
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
