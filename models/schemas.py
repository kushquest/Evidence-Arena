from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Union, Any
from enum import Enum


def coerce_float(v: Any) -> float:
    if isinstance(v, str):
        v_lower = v.lower()
        if "high" in v_lower: return 8.5
        if "medium" in v_lower or "moderate" in v_lower: return 5.0
        if "low" in v_lower: return 2.5
        try:
            return float(v)
        except ValueError:
            return 5.0  # Default to neutral
    return float(v) if v is not None else 0.0


class AgentRole(str, Enum):
    PRO = "pro"
    CON = "con"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.value == value.lower():
                    return member
        return None


class EvidenceQuality(BaseModel):
    study_design: str
    sample_size: int
    peer_reviewed: bool
    quality_score: float  # 0-10
    level_of_evidence: int  # 1 (Meta-analysis) to 5 (Expert Opinion)

    @field_validator("quality_score", mode="before")
    @classmethod
    def validate_quality_score(cls, v): return coerce_float(v)


class Citation(BaseModel):
    pmid: str
    title: str
    abstract: str
    journal: str
    year: int
    authors: List[str]
    study_type: str  # RCT, Cohort, Case Report, etc.
    quality: EvidenceQuality
    affiliations: List[str] = []
    limitations: Optional[str] = None


class Argument(BaseModel):
    claim: str
    evidence_pmids: List[str]
    strength: float  # 0-10
    critique: Optional[str] = None
    rigor_attack: Optional[str] = None  # Attacks on opponent's methodology

    @field_validator("strength", mode="before")
    @classmethod
    def validate_strength(cls, v): return coerce_float(v)


class AgentTurn(BaseModel):
    round_num: int
    role: AgentRole
    opening_statement: str
    arguments: List[Argument]
    citations_used: List[str]
    fresh_queries: List[str]  # Joker queries executed
    thinking_log: List[str]  # Real-time thinking visibility
    glossary: Dict[str, str] = {}  # Technical term: Plain language definition


class DebateRound(BaseModel):
    round_num: int
    pro_turn: AgentTurn
    con_turn: AgentTurn
    human_intervention: Optional[str] = None


class ArgumentCollision(BaseModel):
    pmid: str
    pro_interpretation: str
    con_interpretation: str
    collision_point: str
    contradiction_severity: float  # 0-10

    @field_validator("contradiction_severity", mode="before")
    @classmethod
    def validate_severity(cls, v): return coerce_float(v)


class ConsensusItem(BaseModel):
    statement: str
    confidence: float
    supporting_agents: List[AgentRole]

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, v): return coerce_float(v)


class UnresolvedItem(BaseModel):
    issue: str
    pro_position: str
    con_position: str
    evidence_gap: str


class NewGap(BaseModel):
    gap_description: str
    identified_by: AgentRole
    suggested_search: str


class IronCladFact(BaseModel):
    fact: str
    supporting_evidence: List[str]  # PMIDs
    attack_count: int  # How many times it was challenged
    survival_score: float  # 0-10

    @field_validator("survival_score", mode="before")
    @classmethod
    def validate_survival_score(cls, v): return coerce_float(v)


class ImplementationGap(BaseModel):
    barrier: str
    severity: float
    mitigation_suggested: str

    @field_validator("severity", mode="before")
    @classmethod
    def validate_severity(cls, v): return coerce_float(v)


class Synthesis(BaseModel):
    consensus_items: List[ConsensusItem]
    unresolved_items: List[UnresolvedItem]
    new_gaps: List[NewGap]
    collisions: List[ArgumentCollision]
    iron_clad_facts: List[IronCladFact] = []
    implementation_gaps: List[ImplementationGap] = []
    echo_chamber_warning: Optional[str] = None
    glossary: Dict[str, str] = {}  # Term: Plain language definition


class DebateReport(BaseModel):
    vision: str
    rounds: List[DebateRound]
    synthesis: Synthesis
    burn_meter_pro: float  # 0-100
    burn_meter_con: float  # 0-100
    evidence_weight_pro: float  # Based on Level of Evidence
    evidence_weight_con: float
