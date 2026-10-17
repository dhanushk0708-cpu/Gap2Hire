"""create rag embeddings table

Revision ID: a3f8c9d1e2b4
Revises: e1f2a3b4c5d6
Create Date: 2026-10-17 15:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'a3f8c9d1e2b4'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure pgvector extension is available (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        'rag_embeddings',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('chunk_id', sa.String(128), nullable=False, index=True),
        sa.Column('source_type', sa.String(64), nullable=False, index=True),
        sa.Column('source_id', sa.UUID(), nullable=True),
        sa.Column('application_id', sa.UUID(), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('job_id', sa.UUID(), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('embedding', Vector(384), nullable=False),
        sa.Column('embedding_model', sa.String(64), nullable=False, server_default='all-MiniLM-L6-v2'),
        sa.Column('metadata_json', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('organization_id', 'chunk_id', name='uq_rag_embeddings_org_chunk'),
    )

    op.create_index(
        'idx_rag_embeddings_org_scope',
        'rag_embeddings',
        ['organization_id', 'application_id', 'job_id'],
        unique=False,
    )

    # HNSW vector index using cosine distance
    op.execute(
        "CREATE INDEX idx_rag_embeddings_hnsw ON rag_embeddings USING hnsw (embedding vector_cosine_ops);"
    )


def downgrade() -> None:
    # Drop vector index
    op.execute("DROP INDEX IF EXISTS idx_rag_embeddings_hnsw;")
    # Drop scope index
    op.drop_index('idx_rag_embeddings_org_scope', table_name='rag_embeddings')
    # Drop table
    op.drop_table('rag_embeddings')
    # Note: pgvector extension is intentionally PRESERVED on downgrade to prevent
    # affecting any other potential vector users or database-level extensions.
