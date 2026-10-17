"""
Schemas for Feature 4: Hiring Intelligence Chat + RAG.

All fields are advisory-only.  The chat assistant NEVER makes or alters
hiring decisions, scores, or candidate status records.
"""
from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Inbound - what the client sends
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    """
    A single turn in the conversation history.
    
    Roles are strictly restricted to 'user' and 'assistant'.
    System, developer, tool, or arbitrary strings are rejected.
    """
    role: Literal["user", "assistant"] = Field(
        ...,
        description="Role must be strictly 'user' or 'assistant'.",
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Message text (non-empty)",
    )

    @field_validator("content")
    @classmethod
    def validate_content_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Message content cannot be empty or whitespace only.")
        return v

    model_config = ConfigDict(from_attributes=True)


class HiringChatRequest(BaseModel):
    """
    POST body for a hiring-intelligence chat turn.

    The caller may optionally supply an application_id or job_id to scope
    retrieval to a single candidate/job.  If omitted, retrieval spans the
    whole tenant (organisation).
    """
    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Latest HR message",
    )
    history: List[ChatMessage] = Field(
        default_factory=list,
        max_length=20,
        description="Prior conversation turns (newest last). Max 20 turns.",
    )
    application_id: Optional[UUID] = Field(
        None,
        description="Scope retrieval to a specific application (optional).",
    )
    job_id: Optional[UUID] = Field(
        None,
        description="Scope retrieval to a specific job (optional).",
    )

    @field_validator("message")
    @classmethod
    def validate_message_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Message cannot be empty or whitespace only.")
        return v

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Retrieved context chunks (internal + exposed to client for transparency)
# ---------------------------------------------------------------------------

class RetrievedChunk(BaseModel):
    """A piece of structured evidence surfaced by the RAG retriever."""
    chunk_id: str = Field(..., description="Stable identifier for this chunk")
    source_type: str = Field(
        ...,
        description=(
            "Source of the chunk: EVIDENCE | CANDIDATE_PROFILE | JOB_DESCRIPTION "
            "| INTERVIEW_REPORT | POST_HIRE_OUTCOME | HIRING_AUTOPSY_FINDING | "
            "HIRING_AUTOPSY_SUGGESTION"
        ),
    )
    application_id: Optional[UUID] = Field(None)
    job_id: Optional[UUID] = Field(None)
    candidate_name: Optional[str] = Field(None)
    job_title: Optional[str] = Field(None)
    capability_name: Optional[str] = Field(None)
    text: str = Field(..., description="Human-readable text excerpt used as context")
    relevance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Hybrid or primary relevance score (0-1)",
    )
    semantic_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Semantic similarity score (0-1)",
    )
    keyword_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Keyword relevance score (0-1)",
    )

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Outbound - what the service returns
# ---------------------------------------------------------------------------

class HiringChatCitation(BaseModel):
    """A provenance link inside the assistant's answer."""
    chunk_id: str
    source_type: str
    application_id: Optional[UUID] = None
    job_id: Optional[UUID] = None
    candidate_name: Optional[str] = None
    job_title: Optional[str] = None
    capability_name: Optional[str] = None
    excerpt: str = Field(..., description="Short snippet that supports the claim")

    model_config = ConfigDict(from_attributes=True)


class HiringChatResponse(BaseModel):
    """Full response returned by the hiring-intelligence chat endpoint."""
    answer: str = Field(..., description="AI-generated advisory answer")
    citations: List[HiringChatCitation] = Field(
        default_factory=list,
        description="Evidence chunks the answer is grounded in",
    )
    retrieved_chunks: List[RetrievedChunk] = Field(
        default_factory=list,
        description="All chunks passed to the model (for transparency / debugging)",
    )
    is_advisory_only: bool = Field(
        default=True,
        description=(
            "Always True. The assistant is purely advisory and never modifies "
            "any hiring record, score, or candidate status."
        ),
    )
    context_scope: str = Field(
        ...,
        description=(
            "Description of the retrieval scope used: TENANT, JOB, or APPLICATION."
        ),
    )
    limitations: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


class IndexSyncResponse(BaseModel):
    """Result of an explicit RAG index synchronization operation."""
    status: str = Field(default="ok", description="Synchronization status")
    organization_id: UUID = Field(..., description="Organization tenant ID")
    created: int = Field(default=0, description="Number of newly embedded chunks created")
    updated: int = Field(default=0, description="Number of modified chunks updated in place")
    unchanged: int = Field(default=0, description="Number of unchanged chunks skipped")
    total_processed: int = Field(default=0, description="Total authoritative chunks evaluated")
    synced_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of synchronization")

    model_config = ConfigDict(from_attributes=True)

