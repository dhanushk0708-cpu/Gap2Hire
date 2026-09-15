import json
import logging
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.jd_analysis import ExtractedCapabilitiesPayload, SuggestedCapability

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Raised when AI extraction fails due to network, API, or validation errors."""
    pass


SYSTEM_PROMPT = (
    "You are an expert HR capability architect.\n"
    "Analyze the provided Job Description and extract the key required capabilities.\n"
    "You MUST respond ONLY with a single valid JSON object following this exact schema:\n"
    "{\n"
    '  "capabilities": [\n'
    "    {\n"
    '      "name": "Capability Name",\n'
    '      "description": "Brief description of why this capability is required",\n'
    '      "importance": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "Do not include any extra text, explanations, or markdown fences outside the JSON object."
)


async def extract_capabilities_from_jd(
    title: str,
    description: str,
) -> list[SuggestedCapability]:
    if not settings.groq_api_key or settings.groq_api_key.startswith("your_"):
        raise AIServiceError("Groq API key is missing or unconfigured.")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Job Title: {title}\nJob Description:\n{description}",
            },
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        logger.error(f"Groq API connection error: {exc}")
        raise AIServiceError("Failed to connect to AI provider.") from exc

    if response.status_code != 200:
        logger.error(
            f"Groq API returned error status {response.status_code}: {response.text}"
        )
        raise AIServiceError(
            f"AI provider returned unexpected status code {response.status_code}."
        )

    try:
        data = response.json()
        raw_content = data["choices"][0]["message"]["content"]
        json_obj = json.loads(raw_content)
        validated = ExtractedCapabilitiesPayload.model_validate(json_obj)
        return validated.capabilities
    except (KeyError, json.JSONDecodeError, IndexError, ValidationError) as exc:
        logger.error(f"Failed to parse or validate AI output: {exc}")
        raise AIServiceError("Invalid or malformed output from AI provider.") from exc
