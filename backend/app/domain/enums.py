from enum import StrEnum


class ProjectRole(StrEnum):
    SUBMITTER = "SUBMITTER"
    REVIEWER = "REVIEWER"
    ADMIN = "ADMIN"


class AssessmentProfile(StrEnum):
    """The business boundary that defines a snapshot, run, template and formal record."""

    DELIVERY_VERIFICATION = "DELIVERY_VERIFICATION"
    PROJECT_STATUS_SUMMARY = "PROJECT_STATUS_SUMMARY"
    SECURITY_BASELINE = "SECURITY_BASELINE"
    QUALITY_TREND = "QUALITY_TREND"


class SourceProcessingStatus(StrEnum):
    UPLOADED = "UPLOADED"
    PARSING = "PARSING"
    CHUNKING = "CHUNKING"
    INDEXING = "INDEXING"
    READY = "READY"
    FAILED = "FAILED"


class CycleStatus(StrEnum):
    DRAFT = "DRAFT"
    ANALYZING = "ANALYZING"
    DRAFT_READY = "DRAFT_READY"
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
    PENDING_REVIEW = "PENDING_REVIEW"
    REJECTED = "REJECTED"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
