from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TimestampedEntity:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(TimestampedEntity, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")


class Project(TimestampedEntity, Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ProjectMember(TimestampedEntity, Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),
        CheckConstraint("role IN ('SUBMITTER', 'REVIEWER', 'ADMIN')", name="ck_project_members_role"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)


class VerificationTask(TimestampedEntity, Base):
    __tablename__ = "verification_tasks"
    __table_args__ = (UniqueConstraint("project_id", "requirement_key", name="uq_task_project_requirement"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    requirement_key: Mapped[str] = mapped_column(String(100), nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class VerificationCycle(TimestampedEntity, Base):
    __tablename__ = "verification_cycles"
    __table_args__ = (
        UniqueConstraint("task_id", "sequence_no", name="uq_cycle_task_sequence"),
        CheckConstraint(
            "business_status IN ('DRAFT', 'ANALYZING', 'DRAFT_READY', 'NEEDS_EVIDENCE', "
            "'NEEDS_CONFIRMATION', 'PENDING_REVIEW', 'REJECTED', 'APPROVED', 'PUBLISHED')",
            name="ck_cycle_business_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("verification_tasks.id", ondelete="CASCADE"), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    business_status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    created_from_cycle_id: Mapped[UUID | None] = mapped_column(ForeignKey("verification_cycles.id"))
    active_run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class SourceRevision(TimestampedEntity, Base):
    __tablename__ = "source_revisions"
    __table_args__ = (
        UniqueConstraint("project_id", "logical_name", "revision_no", name="uq_source_revision"),
        CheckConstraint(
            "processing_status IN ('UPLOADED', 'PARSING', 'CHUNKING', 'INDEXING', 'READY', 'FAILED')",
            name="ck_source_processing_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    source_role: Mapped[str] = mapped_column(String(64), nullable=False)
    logical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    artifact_uri: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UPLOADED")
    parser_version: Mapped[str | None] = mapped_column(String(64))
    failure_code: Mapped[str | None] = mapped_column(String(64))


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("source_revision_id", "chunk_index", "index_version", name="uq_document_chunk_version"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_revision_id: Mapped[UUID] = mapped_column(ForeignKey("source_revisions.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    locator: Mapped[dict] = mapped_column(JSONB, nullable=False)
    index_version: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768))


class GitRepository(TimestampedEntity, Base):
    __tablename__ = "git_repositories"
    __table_args__ = (UniqueConstraint("project_id", "canonical_url_hash", name="uq_project_git_repository"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    canonical_url_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    display_url: Mapped[str] = mapped_column(Text, nullable=False)
    credential_ref: Mapped[str | None] = mapped_column(String(255))
    read_only: Mapped[bool] = mapped_column(nullable=False, default=True)


class GitSnapshot(TimestampedEntity, Base):
    __tablename__ = "git_snapshots"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    cycle_id: Mapped[UUID] = mapped_column(ForeignKey("verification_cycles.id", ondelete="CASCADE"), nullable=False)
    repository_id: Mapped[UUID] = mapped_column(ForeignKey("git_repositories.id"), nullable=False)
    selected_base_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    selected_target_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    base_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    target_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    merge_base_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    diff_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    include_paths: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    exclude_paths: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    diff_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    coverage: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class Claim(TimestampedEntity, Base):
    __tablename__ = "claims"
    __table_args__ = (UniqueConstraint("analysis_run_id", "claim_key", name="uq_claim_run_key"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    analysis_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    claim_key: Mapped[str] = mapped_column(String(128), nullable=False)
    claim_type: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    authority_level: Mapped[int] = mapped_column(Integer, nullable=False)
    source_revision_id: Mapped[UUID | None] = mapped_column(ForeignKey("source_revisions.id"))
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (
        CheckConstraint("locator_precision IN ('EXACT', 'APPROXIMATE', 'UNAVAILABLE')", name="ck_evidence_locator_precision"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("input_snapshots.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_revision_id: Mapped[UUID | None] = mapped_column(ForeignKey("source_revisions.id"))
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    excerpt_safe: Mapped[str] = mapped_column(Text, nullable=False)
    locator: Mapped[dict] = mapped_column(JSONB, nullable=False)
    locator_precision: Mapped[str] = mapped_column(String(16), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    extractor_version: Mapped[str] = mapped_column(String(64), nullable=False)
    requires_human_confirmation: Mapped[bool] = mapped_column(nullable=False, default=False)


class ClaimEvidenceLink(Base):
    __tablename__ = "claim_evidence_links"
    __table_args__ = (
        UniqueConstraint("claim_id", "evidence_id", "relation", name="uq_claim_evidence_relation"),
        CheckConstraint("relation IN ('SUPPORTS', 'CONTRADICTS', 'CONTEXT_ONLY')", name="ck_claim_evidence_relation"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    claim_id: Mapped[UUID] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False)
    evidence_id: Mapped[UUID] = mapped_column(ForeignKey("evidence_items.id", ondelete="CASCADE"), nullable=False)
    relation: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    produced_by: Mapped[str] = mapped_column(String(32), nullable=False)
    requires_human_confirmation: Mapped[bool] = mapped_column(nullable=False, default=False)


class VerificationResult(Base):
    __tablename__ = "verification_results"
    __table_args__ = (UniqueConstraint("analysis_run_id", "claim_id", name="uq_result_run_claim"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    analysis_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    claim_id: Mapped[UUID] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False)
    protocol_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    requires_human_confirmation: Mapped[bool] = mapped_column(nullable=False, default=False)
    produced_by: Mapped[str] = mapped_column(String(32), nullable=False)


class AnalysisCoverage(Base):
    __tablename__ = "analysis_coverages"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    analysis_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    scope_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_ref: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64))


class ReportVersion(TimestampedEntity, Base):
    __tablename__ = "report_versions"
    __table_args__ = (UniqueConstraint("cycle_id", "sequence_no", name="uq_report_cycle_sequence"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    cycle_id: Mapped[UUID] = mapped_column(ForeignKey("verification_cycles.id", ondelete="CASCADE"), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    parent_report_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("report_versions.id"))
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False)
    submitted_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    editorial_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ReportItem(Base):
    __tablename__ = "report_items"
    __table_args__ = (UniqueConstraint("report_version_id", "display_order", name="uq_report_item_order"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    report_version_id: Mapped[UUID] = mapped_column(ForeignKey("report_versions.id", ondelete="CASCADE"), nullable=False)
    result_id: Mapped[UUID] = mapped_column(ForeignKey("verification_results.id"), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    result_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    citation_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    disposition: Mapped[str | None] = mapped_column(Text)


class ApprovalAction(Base):
    __tablename__ = "approval_actions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    report_version_id: Mapped[UUID] = mapped_column(ForeignKey("report_versions.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    report_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PublishedRecord(Base):
    __tablename__ = "published_records"
    __table_args__ = (UniqueConstraint("report_version_id", name="uq_published_report"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("verification_tasks.id"), nullable=False)
    cycle_id: Mapped[UUID] = mapped_column(ForeignKey("verification_cycles.id"), nullable=False)
    report_version_id: Mapped[UUID] = mapped_column(ForeignKey("report_versions.id"), nullable=False)
    record_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    record_hash: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    published_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InputSnapshot(TimestampedEntity, Base):
    __tablename__ = "input_snapshots"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    cycle_id: Mapped[UUID] = mapped_column(ForeignKey("verification_cycles.id", ondelete="CASCADE"), nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False, default="PREPARATION")


class InputSnapshotSource(Base):
    __tablename__ = "input_snapshot_sources"
    __table_args__ = (UniqueConstraint("snapshot_id", "source_revision_id", name="uq_snapshot_source"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("input_snapshots.id", ondelete="CASCADE"), nullable=False)
    source_revision_id: Mapped[UUID] = mapped_column(ForeignKey("source_revisions.id"), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)


class InputSnapshotGit(Base):
    __tablename__ = "input_snapshot_git"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("input_snapshots.id", ondelete="CASCADE"), unique=True, nullable=False)
    git_snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("git_snapshots.id"), nullable=False)
    diff_hash: Mapped[str] = mapped_column(String(80), nullable=False)


class ExternalEvidence(TimestampedEntity, Base):
    __tablename__ = "external_evidence"
    __table_args__ = (CheckConstraint("evidence_type IN ('TEST', 'BUILD')", name="ck_external_evidence_type"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    cycle_id: Mapped[UUID] = mapped_column(ForeignKey("verification_cycles.id", ondelete="CASCADE"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(16), nullable=False)
    logical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    artifact_uri: Mapped[str] = mapped_column(Text, nullable=False)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    submitted_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class InputSnapshotExternalEvidence(Base):
    __tablename__ = "input_snapshot_external_evidence"
    __table_args__ = (UniqueConstraint("snapshot_id", "external_evidence_id", name="uq_snapshot_external_evidence"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("input_snapshots.id", ondelete="CASCADE"), nullable=False)
    external_evidence_id: Mapped[UUID] = mapped_column(ForeignKey("external_evidence.id"), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)


class AnalysisRun(TimestampedEntity, Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        Index(
            "uq_active_run_config",
            "snapshot_id",
            "analysis_config_hash",
            unique=True,
            postgresql_where=text("run_status IN ('QUEUED', 'RUNNING')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("input_snapshots.id", ondelete="CASCADE"), nullable=False)
    analysis_config_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    run_status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    manifest_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    checkpoint_ns: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnalysisRunManifest(Base):
    __tablename__ = "analysis_run_manifests"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), unique=True, nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_set_version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_set_version: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_model: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    degradation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class ModelCall(Base):
    __tablename__ = "model_calls"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    allowed_evidence_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_summary: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("principal_hash", "request_method", "request_path", "idempotency_key", name="uq_idempotency_request"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    principal_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    request_method: Mapped[str] = mapped_column(String(10), nullable=False)
    request_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="IN_PROGRESS")
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnalysisJob(TimestampedEntity, Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), unique=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    job_status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_error_code: Mapped[str | None] = mapped_column(String(64))


class RunEvent(Base):
    __tablename__ = "run_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    node_id: Mapped[str | None] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_redacted: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    before_version: Mapped[int | None] = mapped_column(Integer)
    after_version: Mapped[int | None] = mapped_column(Integer)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
