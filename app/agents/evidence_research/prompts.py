import json
import logging
from typing import Any, Optional
from uuid import UUID

import httpx

from app.agents.evidence_research.schemas import EvidenceExtractionResult, ResearchDecision
from app.core.config import settings

logger = logging.getLogger(__name__)

RESEARCH_DECISION_SYSTEM_PROMPT = """You are the Gap2Hire Evidence Research Agent.
Your goal is to strategically select an unresolved job capability and an available candidate source URL (e.g. GitHub repo, portfolio, documentation) to inspect.

RULES:
1. You must ONLY select from the provided list of UNRESOLVED capabilities and AVAILABLE candidate sources.
2. Choose the source that has the highest likelihood of providing factual, concrete evidence for the chosen capability.
3. Be precise about the evidence target you expect to find.
4. Confidence reflects your reasoning confidence in the source choice, NOT a score of the candidate's skill.
5. Return ONLY a valid JSON object matching the requested schema. Do NOT return markdown or explanation outside the JSON.

JSON Schema:
{
  "capability_id": "<UUID string>",
  "source_id": "<UUID string>",
  "reason": "<explanation of source suitability>",
  "evidence_target": "<specific skill or artifact to find>",
  "confidence": <float between 0.0 and 1.0>
}
"""

EVIDENCE_EXTRACTION_SYSTEM_PROMPT = """You are the Gap2Hire Evidence Extraction Specialist.
Your task is to analyze the extracted visible text of an inspected candidate source and determine if it provides concrete, factual proof that the candidate possesses the specified capability.

CRITICAL SEMANTIC RULES:
1. Grounding: You must ONLY state supported=true if the source text contains factual, verifiable evidence of the capability.
2. Insufficient is NOT Lack of Skill: If the source does not mention or prove the skill, set supported=false with explanation="Source contains insufficient evidence for this capability."
3. Do NOT invent claims or extrapolate unsupported skills.
4. If supported=true: provide a concise factual claim and excerpt.
5. Return ONLY a valid JSON object matching the requested schema.

JSON Schema:
{
  "capability_id": "<UUID string>",
  "supported": <true or false>,
  "claim": "<factual statement if supported, or null>",
  "explanation": "<why the source proves or lacks evidence>",
  "source_excerpt": "<relevant snippet from source, or null>",
  "strength": "<STRONG, MODERATE, WEAK, or INSUFFICIENT>",
  "provenance": "<DEMONSTRATED, CORROBORATED, or VERIFIED>"
}
"""


async def call_groq_json(
    system_prompt: str,
    user_prompt: str,
    mock_response: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Calls Groq chat completion API with JSON response format.
    If mock_response is provided or API key is unconfigured, returns mock/fallback data.
    """
    if mock_response is not None:
        return mock_response

    if not settings.groq_api_key or settings.groq_api_key.startswith("your_"):
        logger.warning("Groq API key not configured. Using deterministic fallback.")
        raise ValueError("Groq API key is missing or unconfigured.")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)


async def generate_research_decision(
    job_title: str,
    job_description: str,
    unresolved_capabilities: list[dict[str, Any]],
    available_sources: list[dict[str, Any]],
    actions_taken: list[dict[str, Any]],
    mock_decision: Optional[dict[str, Any]] = None,
) -> Optional[ResearchDecision]:
    """
    Generates a structured ResearchDecision choosing the next capability and source to investigate.
    """
    if not unresolved_capabilities or not available_sources:
        return None

    user_prompt = f"""Job Title: {job_title}
Job Description: {job_description}

Unresolved Capabilities to Investigate:
{json.dumps(unresolved_capabilities, indent=2)}

Available Candidate Sources:
{json.dumps(available_sources, indent=2)}

Previous Actions Taken:
{json.dumps(actions_taken, indent=2)}

Choose the best (capability_id, source_id) pair to investigate next.
"""
    try:
        raw_json = await call_groq_json(
            system_prompt=RESEARCH_DECISION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            mock_response=mock_decision,
        )
        return ResearchDecision.model_validate(raw_json)
    except Exception as e:
        logger.warning(f"Failed to generate structured research decision from LLM: {e}")
        # Deterministic fallback: pick first unresolved capability and first available source
        cap = unresolved_capabilities[0]
        src = available_sources[0]
        return ResearchDecision(
            capability_id=UUID(str(cap["id"])),
            source_id=UUID(str(src["id"])),
            reason=f"Default heuristic investigation of {src.get('source_type', 'source')} for {cap.get('name', 'capability')}",
            evidence_target=f"Practical demonstration of {cap.get('name', 'skill')}",
            confidence=0.7,
        )


async def extract_evidence_from_source(
    capability: dict[str, Any],
    source: dict[str, Any],
    inspection_result: dict[str, Any],
    mock_extraction: Optional[dict[str, Any]] = None,
) -> EvidenceExtractionResult:
    """
    Evaluates inspected source content to determine if it contains concrete evidence for the capability.
    """
    cap_id = UUID(str(capability["id"]))
    cap_name = capability.get("name", "Unknown Capability")
    cap_desc = capability.get("description", "")
    source_url = source.get("url", "")
    source_type = source.get("source_type", "OTHER")
    extracted_text = (inspection_result.get("extracted_text") or "")[:4000]

    if not inspection_result.get("is_success") or not extracted_text.strip():
        return EvidenceExtractionResult(
            capability_id=cap_id,
            supported=False,
            claim=None,
            explanation=f"Source inspection failed or returned empty content: {inspection_result.get('error', 'No content')}",
            source_excerpt=None,
            strength="INSUFFICIENT",
            provenance="CLAIM",
        )

    user_prompt = f"""Target Capability: {cap_name}
Capability Description: {cap_desc}

Inspected Source: {source_url} ({source_type})
Page Title: {inspection_result.get('title', 'N/A')}

Source Content Text:
{extracted_text}

Does this source contain concrete factual proof of {cap_name}?
"""
    try:
        raw_json = await call_groq_json(
            system_prompt=EVIDENCE_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            mock_response=mock_extraction,
        )
        return EvidenceExtractionResult.model_validate(raw_json)
    except Exception as e:
        logger.warning(f"Failed to extract structured evidence from LLM: {e}")
        # Deterministic keyword heuristic fallback
        text_lower = extracted_text.lower()
        cap_name_lower = cap_name.lower()
        if cap_name_lower in text_lower:
            return EvidenceExtractionResult(
                capability_id=cap_id,
                supported=True,
                claim=f"Candidate demonstrates {cap_name} in {source_type} source at {source_url}",
                explanation=f"Found explicit reference and implementation of {cap_name} in source content.",
                source_excerpt=extracted_text[:200],
                strength="STRONG" if source_type in {"GITHUB", "GITLAB"} else "MODERATE",
                provenance="DEMONSTRATED",
            )
        else:
            return EvidenceExtractionResult(
                capability_id=cap_id,
                supported=False,
                claim=None,
                explanation=f"No concrete demonstration of {cap_name} identified in inspected source text.",
                source_excerpt=None,
                strength="INSUFFICIENT",
                provenance="CLAIM",
            )
