from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


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


class SnapshotCreateRequest(BaseModel):
    source_revision_ids: list[UUID] = Field(min_length=1)


class FormalSnapshotCreateRequest(SnapshotCreateRequest):
    git_snapshot_id: UUID


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


class ReportResponse(BaseModel):
    id: UUID
    cycle_id: UUID
    status: str
    content_hash: str


class ApprovalRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=4000)


class ProjectMemberCreateRequest(BaseModel):
    user_id: UUID
    role: str = Field(pattern="^(SUBMITTER|REVIEWER|ADMIN)$")


class EvidenceQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[UUID] = Field(min_length=1, max_length=20)


class EvidenceQuestionResponse(BaseModel):
    answer: str
    fact_status: str
    citations: list[dict]
