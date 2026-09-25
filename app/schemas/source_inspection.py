from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class InspectionErrorCategory(str, Enum):
    INVALID_URL = "INVALID_URL"
    UNSUPPORTED_SCHEME = "UNSUPPORTED_SCHEME"
    BLOCKED_HOST = "BLOCKED_HOST"
    TIMEOUT = "TIMEOUT"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    HTTP_ERROR = "HTTP_ERROR"
    RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE"
    INVALID_CONTENT = "INVALID_CONTENT"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class InspectionResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_url: str
    final_url: Optional[str] = None
    http_status: Optional[int] = None
    content_type: Optional[str] = None
    title: Optional[str] = None
    extracted_text: Optional[str] = None
    content_length: Optional[int] = None
    is_success: bool = False
    error_category: Optional[InspectionErrorCategory] = None
    error_message: Optional[str] = None
    inspected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
