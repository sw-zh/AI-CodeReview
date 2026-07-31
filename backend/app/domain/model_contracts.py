from dataclasses import dataclass
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


@dataclass(frozen=True)
class GenerationResult:
    provider: str
    model: str
    attempts: int
    latency_ms: int
    proposals: ModelProposalBatch
