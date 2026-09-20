from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WSCandidateAudioEvent(BaseModel):
    type: Literal["candidate_audio"] = "candidate_audio"
    audio: str = Field(min_length=1, description="Base64 encoded audio bytes")
    content_type: str = Field(default="audio/webm", description="MIME content type of the audio")

    model_config = ConfigDict(extra="ignore")


class WSTranscriptEvent(BaseModel):
    type: Literal["transcript"] = "transcript"
    role: Literal["candidate"] = "candidate"
    content: str = Field(min_length=1, description="Transcribed candidate speech")

    model_config = ConfigDict(extra="ignore")


class WSAIAudioEvent(BaseModel):
    type: Literal["ai_audio"] = "ai_audio"
    audio: str = Field(min_length=1, description="Base64 encoded speech audio")
    content_type: str = Field(default="audio/mpeg", description="MIME content type of the generated speech")

    model_config = ConfigDict(extra="ignore")
