from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WSCandidateMessageEvent(BaseModel):
    type: Literal["candidate_message"]
    content: str = Field(min_length=1)

    model_config = ConfigDict(extra="ignore")


class WSAIMessageEvent(BaseModel):
    type: Literal["ai_message"] = "ai_message"
    content: str = Field(min_length=1)
    target_capability: str | None = None

    model_config = ConfigDict(extra="ignore")


class WSSystemEvent(BaseModel):
    type: Literal["system"] = "system"
    event: str = Field(min_length=1)
    content: str = Field(min_length=1)

    model_config = ConfigDict(extra="ignore")


from app.schemas.interview_avatar import (
    AvatarState,
    InterviewAvatarMetadata,
    WSAvatarStateEvent,
)
from app.schemas.interview_voice import (
    WSAIAudioEvent,
    WSCandidateAudioEvent,
    WSTranscriptEvent,
)


