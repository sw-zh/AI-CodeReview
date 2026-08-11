from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ModelLinkProposal(BaseModel):
    claim_id: UUID
    evidence_id: UUID
    relation: Literal["SUPPORTS", "CONTRADICTS", "CONTEXT_ONLY"]
    rationale: str = Field(min_length=1, max_length=1000)


class ModelProposalBatch(BaseModel):
    proposals: list[ModelLinkProposal] = Field(default_factory=list, max_length=100)


@dataclass(frozen=True)
class GenerationRequest:
    run_id: UUID
    prompt_version: str
    schema_version: str
    claims: list[dict]
    evidence: list[dict]
    instruction: str = ""
    operation: str = "LINK_PROPOSAL"
    temporary_context: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class GenerationResult:
    provider: str
    model: str
    attempts: int
    latency_ms: int
    proposals: ModelProposalBatch


@dataclass(frozen=True)
class EmbeddingRequest:
    text: str
    model: str


@dataclass(frozen=True)
class EmbeddingResult:
    provider: str
    model: str
    vector: list[float]


class EvidenceAnswerPayload(BaseModel):
    answer: str = Field(min_length=1, max_length=4000)
    fact_status: Literal["CONFIRMED", "PARTIALLY_SUPPORTED", "CONFLICTING", "INSUFFICIENT_EVIDENCE", "INFERENCE_REQUIRES_CONFIRMATION"]


@dataclass(frozen=True)
class EvidenceAnswerRequest:
    question: str
    prompt_version: str
    schema_version: str
    evidence: list[dict]


@dataclass(frozen=True)
class EvidenceAnswerResult:
    provider: str
    model: str
    attempts: int
    latency_ms: int
    payload: EvidenceAnswerPayload
