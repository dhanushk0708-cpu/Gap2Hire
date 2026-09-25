from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class DiscoveredLink(BaseModel):
    """
    Structured representation of a link discovered within an inspected HTML document.
    """
    model_config = ConfigDict(from_attributes=True)

    url: str = Field(min_length=1, description="Normalized absolute URL of the discovered link")
    anchor_text: Optional[str] = Field(default=None, description="Visible anchor text from the <a> element")
    source_url: str = Field(min_length=1, description="The URL of the page where the link was found")
    discovery_depth: int = Field(default=1, ge=0, description="Discovery depth relative to original candidate source")
    discovered_from: str = Field(min_length=1, description="Origin URL that led to this link")
    source_type: str = Field(default="OTHER", max_length=50, description="Deterministic source classification")
