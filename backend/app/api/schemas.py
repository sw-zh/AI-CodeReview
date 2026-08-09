from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class LoginRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(min_length=8, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    version: int
    created_at: datetime


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    requirement_key: str = Field(min_length=1, max_length=100)


class TaskResponse(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    requirement_key: str
    cycle_id: UUID
    cycle_status: str
    version: int


class SourceResponse(BaseModel):
    id: UUID
    project_id: UUID
    logical_name: str
    revision_no: int
    content_hash: str
    processing_status: str
    parser_version: str | None


class SourceDetailResponse(BaseModel):
    id: UUID
    project_id: UUID
    logical_name: str
    source_role: str
    revision_no: int
    content_hash: str
    media_type: str
    processing_status: str
    parser_version: str | None
    in_snapshot: bool
    created_at: datetime
    updated_at: datetime


class SourceContentResponse(BaseModel):
    content: str
    media_type: str
    logical_name: str


class ChunkItemResponse(BaseModel):
    id: UUID
    chunk_index: int
    content: str
    locator: dict
    index_version: str


class SnapshotCreateRequest(BaseModel):
    source_revision_ids: list[UUID] = Field(min_length=1)


class FormalSnapshotCreateRequest(SnapshotCreateRequest):
    git_snapshot_id: UUID
    external_evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)
    manual_evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)


class SnapshotResponse(BaseModel):
    id: UUID
    cycle_id: UUID
    snapshot_hash: str
    purpose: str
    policy_version: str
    workflow_version: str
    created_at: datetime


class EvidenceResponse(BaseModel):
    id: UUID
    snapshot_id: UUID
    source_type: str
    evidence_kind: str
    excerpt_safe: str
    locator: dict
    locator_precision: str


class GitRepositoryCreateRequest(BaseModel):
    display_url: str = Field(min_length=8, max_length=2000)


class GitRepositoryResponse(BaseModel):
    id: UUID
    project_id: UUID
    display_url: str
    read_only: bool


class GitSnapshotCreateRequest(BaseModel):
    repository_id: UUID
    base_ref: str = Field(min_length=1, max_length=255)
    target_ref: str = Field(min_length=1, max_length=255)
    diff_mode: str = Field(pattern="^(TWO_DOT|THREE_DOT)$")
    include_paths: list[str] = Field(default_factory=list, max_length=100)
    exclude_paths: list[str] = Field(default_factory=list, max_length=100)


class GitSnapshotResponse(BaseModel):
    id: UUID
    base_sha: str
    target_sha: str
    merge_base_sha: str
    diff_mode: str
    diff_hash: str
    coverage: dict


class AnalysisRunResponse(BaseModel):
    id: UUID
    snapshot_id: UUID
    run_status: str
    poll_url: str


class AnalysisResultResponse(BaseModel):
    id: UUID
    claim_id: UUID
    claim_key: str
    claim_text: str
    status: str
    reason: str
    requires_human_confirmation: bool
    evidence: list[dict]
    risks: list[dict] = Field(default_factory=list)


class ReportResponse(BaseModel):
    id: UUID
    cycle_id: UUID
    sequence_no: int
    status: str
    content_hash: str
    editorial_note: str
    version: int


class ReportDraftUpdateRequest(BaseModel):
    editorial_note: str = Field(default="", max_length=8000)
    item_dispositions: dict[UUID, str | None] = Field(default_factory=dict, max_length=500)
    expected_version: int = Field(ge=1)


class ApprovalRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=4000)


class ProjectMemberCreateRequest(BaseModel):
    user_id: UUID | None = None
    user_email: str | None = Field(default=None, max_length=255)
    role: str = Field(pattern="^(SUBMITTER|REVIEWER|ADMIN)$")

    @model_validator(mode="after")
    def require_one_identity(self):
        if (self.user_id is None) == (self.user_email is None):
            raise ValueError("exactly one of user_id or user_email is required")
        return self


class EvidenceQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[UUID] = Field(min_length=1, max_length=20)


class EvidenceQuestionResponse(BaseModel):
    answer: str
    fact_status: str
    citations: list[dict]


class ExternalEvidenceCreateRequest(BaseModel):
    evidence_type: str = Field(pattern="^(TEST|BUILD)$")
    logical_name: str = Field(min_length=1, max_length=255)
    commit_sha: str = Field(pattern="^[0-9a-fA-F]{40}$")
    content: str = Field(min_length=1, max_length=2 * 1024 * 1024)
    exit_code: int | None = Field(default=None, ge=-255, le=255)


class ExternalEvidenceResponse(BaseModel):
    id: UUID
    project_id: UUID
    cycle_id: UUID
    evidence_type: str
    logical_name: str
    commit_sha: str
    content_hash: str
    exit_code: int | None


class ManualEvidenceCreateRequest(BaseModel):
    logical_name: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=2 * 1024 * 1024)


class ManualEvidenceResponse(BaseModel):
    id: UUID
    project_id: UUID
    cycle_id: UUID
    logical_name: str
    content_hash: str


class SnapshotSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


class SnapshotSearchResponse(BaseModel):
    items: list[dict]
