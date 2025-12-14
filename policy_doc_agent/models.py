"""Core data models for the policy document agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List


@dataclass
class DraftSegment:
    """Represents an individual segment in a draft document."""

    segment_id: str
    criterion: str
    text: str


@dataclass
class DraftDocument:
    """Represents a single document within the draft package."""

    doc_type: str
    segments: List[DraftSegment] = field(default_factory=list)


@dataclass
class DraftPackage:
    """Schema for the generated EB-1 draft package."""

    case_id: str
    documents: List[DraftDocument] = field(default_factory=list)


@dataclass
class PlannerPlan:
    """High-level generation plan produced by the planner agent."""

    case_id: str
    applicant_signature: str
    document_plan: Dict[str, List[str]]  # doc_type -> list of criteria
    retrieval_queries: List[str]


@dataclass
class ReviewEvent:
    """Records how an attorney edited a generated segment."""

    case_id: str
    segment_id: str
    criterion: str
    applicant_signature: str
    reason_codes: List[str]
    edit_distance: int
    severity: str
    timestamp: datetime


@dataclass
class FailurePattern:
    """Aggregated pattern describing repeated issues."""

    pattern_id: str
    criterion: str
    signature: str
    reason_code: str
    count: int
    confidence: float


@dataclass
class Policy:
    """Policy that constrains generation."""

    policy_id: str
    version: int
    scope: str
    constraints: Dict[str, str]
    verification: Dict[str, str]
    created_at: datetime
