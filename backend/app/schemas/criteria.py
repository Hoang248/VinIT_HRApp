from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from enum import Enum
from .common import BaseSchema, TimestampMixin


class CriteriaCategory(str, Enum):
    MUST_HAVE = "MUST_HAVE"
    NICE_TO_HAVE = "NICE_TO_HAVE"


class CriterionRating(str, Enum):
    STRONG_MATCH = "STRONG_MATCH"
    MATCH = "MATCH"
    UNCLEAR = "UNCLEAR"
    NO_MATCH = "NO_MATCH"


class CriteriaStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_HR_REVIEW = "PENDING_HR_REVIEW"
    PENDING_HM_APPROVAL = "PENDING_HM_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class CriterionBase(BaseSchema):
    name: str
    description: str
    category: CriteriaCategory
    weight_in_group: float = Field(..., ge=0, le=100, description="Weight percentage within its category group")
    expected_evidence_keywords: List[str] = Field(default_factory=list)
    evidence_guidance: Optional[str] = None
    jd_reference_text: Optional[str] = None


class CriterionCreate(CriterionBase):
    pass


class CriterionUpdate(BaseSchema):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[CriteriaCategory] = None
    weight_in_group: Optional[float] = None
    expected_evidence_keywords: Optional[List[str]] = None


class Criterion(CriterionBase, TimestampMixin):
    criterion_id: UUID
    criteria_version_id: UUID
    display_order: int


class CriteriaVersionBase(BaseSchema):
    jd_version_id: UUID
    origin: str = Field(default="AI_DRAFT", description="AI_DRAFT or HR_CREATED")
    mandatory_weight_total: float = 70.0
    nice_to_have_weight_total: float = 30.0
    policy_version: Optional[str] = None


class CriteriaVersionCreate(CriteriaVersionBase):
    criteria: List[CriterionCreate]


class CriteriaVersion(CriteriaVersionBase, TimestampMixin):
    criteria_version_id: UUID
    position_id: UUID
    version_number: int
    status: CriteriaStatus
    approved_by_hr_at: Optional[datetime] = None
    approved_by_hm_at: Optional[datetime] = None
    approved_by_hr: Optional[UUID] = None
    approved_by_hm: Optional[UUID] = None
    criteria: List[Criterion] = Field(default_factory=list)


class GenerateCriteriaRequest(BaseSchema):
    position_id: UUID
    jd_content: str = Field(..., description="Job Description text for AI to extract criteria")


class ApprovalAction(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_CHANGES = "REQUEST_CHANGES"


class CriteriaApprovalRequest(BaseSchema):
    action: ApprovalAction
    comment: Optional[str] = None
