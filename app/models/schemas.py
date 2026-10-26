"""Request / response schemas for the BharatContract AI API."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.time import utcnow

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ContractType(str, Enum):
    MSA = "MSA"
    NDA = "NDA"
    SPA = "SPA"
    EMPLOYMENT = "Employment"
    VENDOR = "Vendor"
    LEASE = "Lease"
    SERVICE = "Service"
    OTHER = "Other"


class PartySide(str, Enum):
    PROVIDER = "Provider"
    CUSTOMER = "Customer"
    EMPLOYER = "Employer"
    EMPLOYEE = "Employee"
    VENDOR = "Vendor"
    BUYER = "Buyer"
    SELLER = "Seller"
    NEUTRAL = "Neutral"


class RiskSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ObligationType(str, Enum):
    OBLIGATION = "obligation"
    RIGHT = "right"
    PROHIBITION = "prohibition"
    CONDITION = "condition"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class UserRole(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class Entity(BaseModel):
    text: str
    label: str
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    confidence: float = 1.0
    source: str = "regex"  # 'ner' | 'regex' | 'rule'


class Clause(BaseModel):
    clause_id: str
    section_number: Optional[str] = None
    heading: Optional[str] = None
    text: str
    page_hint: Optional[int] = None
    char_start: int = 0
    char_end: int = 0
    clause_types: List[str] = Field(default_factory=list)
    risk_score: float = 0.0
    risk_level: RiskSeverity = RiskSeverity.LOW
    risk_reasons: List[str] = Field(default_factory=list)
    entities: List[Entity] = Field(default_factory=list)
    # P1: deterministic cross-reference / context bundle (additive, optional).
    context: Optional[Dict[str, Any]] = None


class Obligation(BaseModel):
    obligation_id: str
    clause_id: str
    text: str
    obligation_type: ObligationType = ObligationType.OBLIGATION
    subject: Optional[str] = None
    counterparty: Optional[str] = None
    action: Optional[str] = None
    object: Optional[str] = None
    condition: Optional[str] = None
    deadline_expression: Optional[str] = None
    deadline_date: Optional[str] = None
    risk_level: RiskSeverity = RiskSeverity.LOW
    confidence: float = 0.7
    source: str = "rule"


class CaseLawReference(BaseModel):
    """A non-authoritative pointer to the statute/case behind a risk rule."""

    citation: str
    summary: str
    jurisdiction: str = "India"


class EvidenceSpan(BaseModel):
    """A passage supporting a finding.

    ``locator="clause_text"`` means ``char_start``/``char_end`` are offsets into the
    *clause text as stored in ``Clause.text``* (cleaned/segmented text), NOT raw file
    bytes. Offsets are therefore only meaningful together with ``clause_id``.
    """

    text: str
    char_start: int
    char_end: int
    clause_id: Optional[str] = None
    role: str = "direct"  # "direct" | "contextual"
    locator: str = "clause_text"


class RiskFlag(BaseModel):
    risk_id: str
    clause_id: Optional[str] = None
    rule_id: str
    name: str
    severity: RiskSeverity
    explanation: str
    recommendation: Optional[str] = None
    score: float = 0.0
    case_law: List[CaseLawReference] = Field(default_factory=list)
    # P2: evidence binding (additive; defaults keep older payloads valid).
    source: str = "rule"  # "rule" | "model"
    evidence_status: str = "unavailable"  # direct | contextual | unverified | unavailable
    evidence_spans: List[EvidenceSpan] = Field(default_factory=list)
    search_scope: Optional[str] = None
    related_clause_ids: List[str] = Field(default_factory=list)


class ContractSummary(BaseModel):
    contract_id: str
    title: str
    file_name: str
    contract_type: ContractType = ContractType.OTHER
    jurisdiction: str = "India"
    parties: List[str] = Field(default_factory=list)
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    governing_law: Optional[str] = None
    arbitration_seat: Optional[str] = None
    stamp_duty_mentioned: bool = False
    tds_mentioned: bool = False
    gstin_mentioned: bool = False
    overall_risk_score: float = 0.0
    overall_risk_level: RiskSeverity = RiskSeverity.LOW
    high_risk_clauses: int = 0
    missing_clauses: List[str] = Field(default_factory=list)
    top_risks: List[RiskFlag] = Field(default_factory=list)
    clause_count: int = 0
    obligation_count: int = 0
    analyzed_at: datetime = Field(default_factory=utcnow)


class AnalysisResult(BaseModel):
    contract: ContractSummary
    clauses: List[Clause] = Field(default_factory=list)
    obligations: List[Obligation] = Field(default_factory=list)
    risks: List[RiskFlag] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class JobInfo(BaseModel):
    job_id: str
    contract_id: str
    owner: str = ""
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0
    message: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    finished_at: Optional[datetime] = None
    result: Optional[AnalysisResult] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Request payloads
# ---------------------------------------------------------------------------


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    username: str
    role: str


class UserInfo(BaseModel):
    username: str
    role: str
    authenticated: bool = False


class ContractMetadata(BaseModel):
    contract_type: ContractType = ContractType.OTHER
    user_role: PartySide = PartySide.CUSTOMER
    jurisdiction: str = "India"
    playbook_id: Optional[str] = None


class GraphNode(BaseModel):
    id: str
    label: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphSnapshot(BaseModel):
    contract_id: str
    nodes: List[GraphNode]
    edges: List[GraphEdge]
