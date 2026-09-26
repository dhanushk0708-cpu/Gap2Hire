from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DatasetQuestionItem(BaseModel):
    id: UUID
    dataset_id: UUID
    question_text: str
    concept: str
    difficulty: str = "MEDIUM"
    question_type: str = "CONCEPTUAL"
    expected_topics: list[str] | None = None
    metadata_: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class QuestionDatasetItem(BaseModel):
    id: UUID
    name: str
    concept: str
    description: str | None = None
    question_count: int = 0
    questions: list[DatasetQuestionItem] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class InterviewDatasetFileResponse(BaseModel):
    id: UUID
    filename: str
    job_id: UUID | None = None
    total_questions: int = 0
    dataset_count: int = 0
    datasets: list[QuestionDatasetItem] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetUploadResponse(BaseModel):
    file_id: UUID
    filename: str
    total_questions: int
    datasets: list[QuestionDatasetItem]
    warnings: list[str] = Field(default_factory=list)
