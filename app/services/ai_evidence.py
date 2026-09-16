import json
import logging
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.evidence import AIEvidenceItem, AIEvidencePayload

logger = logging.getLogger(__name__)


class AIEvidenceServiceError(Exception):
    """Raised when AI evidence extraction fails due to network, API, or validation errors."""
    pass


SYSTEM_PROMPT = (
    "You are an expert HR evidence extraction architect.\n"
    "Your goal is to evaluate candidate resume text against a set of approved capabilities for a job and identify grounded evidence for each capability.\n"
    "Follow these strict principles:\n"
    "1. Only use information present in the supplied resume text.\n"
    "2. Do not invent skills, projects, employment history, or years of experience.\n"
    "3. Do not infer unsupported technologies or fabricate responsibilities.\n"
    "4. Do not create or evaluate capabilities that were not explicitly supplied.\n"
    "5. Evaluate ONLY the supplied approved capabilities.\n"
    "6. Allowed strength values: 'STRONG', 'MODERATE', 'WEAK', 'INSUFFICIENT'.\n"
    "7. If evidence is insufficient or absent in the resume, strength MUST be 'INSUFFICIENT' and evidence MUST be null.\n"
    "8. 'INSUFFICIENT' means no evidence was found in the text; it does NOT imply candidate rejection or lack of skill.\n"
    "9. Evidence text MUST be directly grounded in quotes or facts from the resume. Do not make claims beyond what is stated.\n"
    "10. Do NOT produce candidate scores, ranks, or hiring recommendations.\n"
    "11. You MUST respond ONLY with a single valid JSON object adhering to this exact schema:\n"
    "{\n"
    '  "evidence": [\n'
    "    {\n"
    '      "capability_name": "Capability Name",\n'
    '      "strength": "STRONG" | "MODERATE" | "WEAK" | "INSUFFICIENT",\n'
    '      "evidence": "Grounded text quote or detail from resume, or null if INSUFFICIENT"\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "Do not include any extra text, explanations, or markdown fences outside the JSON object."
)


async def extract_evidence_from_resume(
    job_title: str,
    job_description: str,
    capabilities: list[dict[str, Any]],
    resume_text: str,
) -> list[AIEvidenceItem]:
    if not settings.groq_api_key or settings.groq_api_key.startswith("your_"):
        raise AIEvidenceServiceError("Groq API key is missing or unconfigured.")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    cap_formatted = "\n".join(
        f"- {c['name']}: {c.get('description') or 'No description provided'}"
        for c in capabilities
    )

    user_prompt = (
        f"Job Title: {job_title}\n"
        f"Job Description: {job_description}\n\n"
        f"Approved Capabilities to Evaluate:\n{cap_formatted}\n\n"
        f"Candidate Resume Text:\n{resume_text}"
    )

    payload: dict[str, Any] = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        logger.error(f"Groq API connection error during evidence extraction: {exc}")
        raise AIEvidenceServiceError("Failed to connect to AI provider.") from exc

    if response.status_code != 200:
        logger.error(
            f"Groq API returned error status {response.status_code}: {response.text}"
        )
        raise AIEvidenceServiceError(
            f"AI provider returned unexpected status code {response.status_code}."
        )

    try:
        data = response.json()
        raw_content = data["choices"][0]["message"]["content"]
        json_obj = json.loads(raw_content)
        validated = AIEvidencePayload.model_validate(json_obj)
        return validated.evidence
    except (KeyError, json.JSONDecodeError, IndexError, ValidationError) as exc:
        logger.error(f"Failed to parse or validate AI evidence output: {exc}")
        raise AIEvidenceServiceError("Invalid or malformed output from AI provider.") from exc
