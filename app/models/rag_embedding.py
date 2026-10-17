"""
SQLAlchemy model for persistent vector embeddings in Feature 4 - Hiring Intelligence RAG.

Stores real 384-dimensional embeddings (all-MiniLM-L6-v2) for structured evidence chunks
with strict tenant isolation, scope tracking, content hashing for change detection,
and HNSW vector indexing.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base

EMBEDDING_DIMENSION = 384


class RagEmbedding(Base):
    __tablename__ = "rag_embeddings"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    chunk_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    source_id: Mapped[UUID | None] = mapped_column(
        nullable=True,
    )

    application_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    chunk_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIMENSION),
        nullable=False,
    )

    embedding_model: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="all-MiniLM-L6-v2",
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "chunk_id", name="uq_rag_embeddings_org_chunk"),
        Index("idx_rag_embeddings_org_scope", "organization_id", "application_id", "job_id"),
    )
