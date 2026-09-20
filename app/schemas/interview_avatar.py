from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AvatarState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"


class WSAvatarStateEvent(BaseModel):
    type: Literal["avatar_state"] = "avatar_state"
    state: AvatarState = Field(..., description="Current visual/interactive state of the AI avatar")

    model_config = ConfigDict(extra="ignore")


class InterviewAvatarMetadata(BaseModel):
    avatar_id: str = "default-interviewer"
    name: str = "Gap2Hire AI Interviewer"
    display_name: str = "AI Interviewer"
    voice_enabled: bool = True
    avatar_enabled: bool = True

    model_config = ConfigDict(extra="ignore")
