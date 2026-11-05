import json
import httpx
from typing import Dict, Any, List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.config import settings
from app.core.logging import get_logger
from pydantic import BaseModel, ValidationError

logger = get_logger(__name__)


class LLMError(Exception):
    """Base exception for LLM operations"""
    pass


class JD_Criteria_Schema(BaseModel):
    requisition_id: str
    job_title: str
    criteria: List[Dict[str, Any]]


class CandidateProfileSchema(BaseModel):
    candidate_identifier: str
    total_years_experience: float
    education: List[Dict[str, Any]]
    work_history: List[Dict[str, Any]]
    skills: List[str]
    certifications: List[Dict[str, Any]]


class CriterionFindingsSchema(BaseModel):
    candidate_identifier: str
    rubric_version: str
    findings: List[Dict[str, Any]]


class LLMClient:
    """Client for calling local/remote LLM with structured output enforcement"""

    def __init__(self):
        self.base_url = settings.LLM_API_BASE or "http://localhost:8000/v1"
        self.model = settings.LLM_MODEL_NAME
        self.default_temp = settings.LLM_TEMPERATURE_DEFAULT
        self.allowed_external = settings.ALLOW_EXTERNAL_API

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, LLMError))
    )
    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        json_schema: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make LLM API call with retry logic"""
        temp = temperature if temperature is not None else self.default_temp

        # Add schema enforcement to prompt for guided JSON output
        if json_schema:
            system_prompt += f"\n\nYou MUST respond with valid JSON that strictly adheres to this schema:\n{json.dumps(json_schema, indent=2)}\nDo not include any explanations, markdown, or text outside the JSON object."

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temp,
            "response_format": {"type": "json_object"}
        }

        headers = {
            "Content-Type": "application/json"
        }
        if settings.LLM_API_KEY:
            headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()

                content = data["choices"][0]["message"]["content"]
                # Parse and validate JSON
                parsed = json.loads(content)
                return parsed

        except json.JSONDecodeError as e:
            logger.error("LLM returned invalid JSON", error=str(e), content_sample=content[:500])
            raise LLMError("Failed to parse LLM response as JSON")
        except httpx.HTTPStatusError as e:
            logger.error("LLM API error", status_code=e.response.status_code, error=str(e))
            raise LLMError(f"LLM API error: {e.response.status_code}")
        except Exception as e:
            logger.error("Unexpected error calling LLM", error=str(e))
            raise LLMError(f"LLM call failed: {str(e)}")

    async def extract_criteria_from_jd(self, jd_text: str, requisition_id: str, job_title: str) -> Dict[str, Any]:
        """Task AIC-01: Extract structured MUST_HAVE/NICE_TO_HAVE criteria from JD"""
        system_prompt = """You are an expert HR Recruitment Assistant specialized in job description decomposition.
Your task is to analyze the provided English Job Description (JD) and extract explicit, verifiable evaluation criteria.

RULES:
1. Divide criteria into two strict categories:
   - "MUST_HAVE": Non-negotiable baseline requirements (e.g. minimum years of specific experience, core programming languages, mandatory degrees).
   - "NICE_TO_HAVE": Preferred qualifications, secondary skills, or optional certifications.
2. Assign default weights: Total of all MUST_HAVE criteria = 70.0. Total of all NICE_TO_HAVE criteria = 30.0. Sum must equal 100.0.
3. For each criterion, identify 3-5 explicit evidence keywords expected in candidate resumes.
4. DO NOT invent requirements not mentioned in the JD.
5. STRICTLY FORBIDDEN: Do not generate criteria related to age, gender, marital status, nationality, appearance, or personality traits.
"""

        user_prompt = f"""Requisition ID: {requisition_id}
Job Title: {job_title}

JOB DESCRIPTION:
{jd_text}
"""

        result = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1
        )

        # Validate against schema
        try:
            JD_Criteria_Schema.model_validate(result)
        except ValidationError as e:
            logger.error("LLM criteria output failed schema validation", error=str(e))
            raise LLMError("Generated criteria failed validation")

        return result

    async def extract_candidate_profile(self, cv_text: str, candidate_identifier: str) -> Dict[str, Any]:
        """Task AIC-02: Extract structured candidate profile from CV text, removing PII"""
        system_prompt = """You are a precise Resume Information Extraction Engine.
Your task is to parse unstructured CV text into a structured, verifiable profile.

STRICT PRIVACY & ANTI-BIAS RULES:
- COMPLETELY OMIT AND STRIP: Candidate photo, age, date of birth, gender, marital status, religion, ethnicity, residential address.
- Retain ONLY: Professional experience, education history, technical/soft skills, languages, and verifiable certifications.
- Record the exact page number where each block of information is located.
"""

        user_prompt = f"""Candidate Identifier: {candidate_identifier}

CV TEXT (with page markers):
{cv_text}
"""

        result = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0  # Deterministic parsing
        )

        try:
            CandidateProfileSchema.model_validate(result)
        except ValidationError as e:
            logger.error("LLM profile extraction failed schema validation", error=str(e))
            raise LLMError("Extracted candidate profile failed validation")

        return result

    async def match_criterion_evidence(
        self,
        cv_text: str,
        candidate_profile: Dict[str, Any],
        rubric: List[Dict[str, Any]],
        candidate_identifier: str,
        rubric_version: str
    ) -> Dict[str, Any]:
        """Task AIC-03: Match each criterion with verbatim evidence quotes from CV"""
        system_prompt = """You are a rigorous, evidence-based Candidate Verification Agent.

EVALUATION RULES:
1. For each criterion, assign exactly ONE of the following 4 levels:
   - "STRONG_MATCH": Candidate substantially exceeds the requirement with verifiable metrics.
   - "MATCH": Candidate explicitly satisfies the full requirement.
   - "UNCLEAR": The CV does not mention the requirement, or mentions it ambiguously without verifiable context.
   - "NO_MATCH": The CV provides explicit evidence contradicting the requirement.
2. CRITICAL PRINCIPLE: "UNCLEAR" MUST NEVER BE TREATED AS "NO_MATCH". If evidence is absent, you MUST output "UNCLEAR".
3. EVIDENCE REQUIREMENT:
   - For "STRONG_MATCH" and "MATCH", you MUST provide an exact, verbatim text quote copied directly from the CV and its page number.
   - If no verbatim quote exists in the text, you CANNOT assign "MATCH" or "STRONG_MATCH".
4. Reasoning must be concise, objective, and neutral. Do not assume or extrapolate.
"""

        user_prompt = f"""Candidate Identifier: {candidate_identifier}
Rubric Version: {rubric_version}

=== APPROVED RUBRIC ===
{json.dumps(rubric, indent=2)}

=== STRUCTURED CANDIDATE PROFILE ===
{json.dumps(candidate_profile, indent=2)}

=== RAW CV TEXT (with page markers) ===
{cv_text}
"""

        result = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0  # Fully deterministic matching
        )

        try:
            CriterionFindingsSchema.model_validate(result)
        except ValidationError as e:
            logger.error("LLM criterion matching failed schema validation", error=str(e))
            raise LLMError("Matching results failed validation")

        return result


# Singleton instance
llm_client = LLMClient()
