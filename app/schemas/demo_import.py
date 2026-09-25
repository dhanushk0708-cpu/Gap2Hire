from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DemoImportResult(BaseModel):
    total_found: int = 0
    created: int = 0
    skipped_duplicates: int = 0
    failed: int = 0
    job_id: UUID
    candidate_names: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    message: str = ""

    model_config = ConfigDict(from_attributes=True)
