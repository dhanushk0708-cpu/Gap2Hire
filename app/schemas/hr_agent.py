from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.verification import VerificationType


class HRAgentRequest(BaseModel):
    message: str = Field(min_length=1)


class CitationType(str, Enum):
    CAPABILITY = "CAPABILITY"
    EVIDENCE = "EVIDENCE"
    VERIFICATION = "VERIFICATION"


class Citation(BaseModel):
    type: CitationType
    id: UUID
    name: str


class VerificationRecommendation(BaseModel):
    type: VerificationType
    capability_id: UUID
    title: str
    instructions: str
    reason: str


class AIAgentPayload(BaseModel):
    message: str
    citations: list[dict] = Field(default_factory=list)
    recommendation: dict | None = None


class HRAgentResponse(BaseModel):
    message: str
    citations: list[Citation] = Field(default_factory=list)
    recommendation: VerificationRecommendation | None = None

    model_config = ConfigDict(from_attributes=True)
