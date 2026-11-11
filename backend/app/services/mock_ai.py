"""Synthetic AI for development (LLM_PROVIDER=mock) until AI Core exposes its API.

It answers the three tasks llm_client sends to the model, from the same
redacted JSON prompt a real model would receive, and returns JSON in exactly the
shape the real model must return (the caller validates it with the same
schemas). Results come from keyword heuristics: they are deterministic and good
enough to exercise the whole workflow, NOT to judge real candidates. Config
refuses this provider outside APP_ENV=development/testing.
"""
from __future__ import annotations

import json
import re
from typing import Any

MOCK_MARK = "[MOCK AI]"

_NICE_HINTS = ("nice to have", "nice-to-have", "preferred", "is a plus", "a plus", "bonus", "desirable",
               "ưu tiên", "là lợi thế", "điểm cộng")
_REQUIREMENT_HINTS = ("require", "must", "experience", "years", "skill", "degree", "knowledge", "proficien",
                      "familiar", "ability", "strong", "solid", "background", "certif",
                      "yêu cầu", "kinh nghiệm", "kỹ năng", "bằng", "thành thạo", "hiểu biết")
_STOPWORDS = {"and", "or", "the", "with", "for", "of", "in", "to", "a", "an", "on", "at", "is", "are", "be", "as",
              "years", "year", "experience", "strong", "solid", "skills", "skill", "knowledge", "ability",
              "must", "have", "required", "requirements", "nice", "plus", "preferred", "least", "minimum",
              "good", "excellent", "working", "using", "building", "we", "you", "our", "will", "etc"}


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?;])\s+|\n+|•|•", text or "")
    return [re.sub(r"\s+", " ", p).strip(" -*\t") for p in parts if p and len(p.strip()) > 3]


def _keywords(text: str, limit: int = 5) -> list[str]:
    found: list[str] = []
    for token in re.findall(r"[A-Za-z][A-Za-z0-9+#./-]{1,30}", text):
        clean = token.strip("./-")
        if len(clean) < 2 or clean.lower() in _STOPWORDS:
            continue
        # Prefer technical-looking tokens (capitalised, acronyms, symbols).
        if clean[0].isupper() or any(c in clean for c in "+#./") or clean.isupper():
            if clean.lower() not in {k.lower() for k in found}:
                found.append(clean)
        if len(found) >= limit:
            break
    return found


def _title(sentence: str) -> str:
    words = sentence.split()
    title = " ".join(words[:8])
    return (title[:120] + "…") if len(title) > 120 else title


def _criteria_from_jd(payload: dict) -> dict:
    sentences = _sentences(payload.get("untrusted_job_description", ""))
    must, nice = [], []
    for sentence in sentences:
        low = sentence.lower()
        if any(h in low for h in _NICE_HINTS):
            nice.append(sentence)
        elif any(h in low for h in _REQUIREMENT_HINTS):
            must.append(sentence)
    if not must and sentences:
        must = sentences[:1]
    must, nice = must[:8], nice[:5]
    criteria = []
    for group, items, total in (("MUST_HAVE", must, 70.0 if nice else 100.0), ("NICE_TO_HAVE", nice, 30.0)):
        for sentence in items:
            criteria.append({
                "name": _title(sentence),
                "description": sentence[:4000],
                "category": group,
                "weight": round(total / len(items), 2),
                "expected_evidence_keywords": _keywords(sentence) or _keywords(_title(sentence)),
                "jd_reference_text": sentence[:4000],
                "evidence_guidance": f"{MOCK_MARK} Tìm trong CV các dự án/kinh nghiệm nhắc tới: {', '.join(_keywords(sentence)) or 'nội dung tiêu chí'}.",
            })
    return {"requisition_id": payload.get("requisition_id", ""), "job_title": payload.get("job_title", ""), "criteria": criteria}


_EDU_HINTS = ("university", "bachelor", "master", "phd", "college", "đại học", "cử nhân", "thạc sĩ", "tiến sĩ", "kỹ sư")


def _profile_from_cv(payload: dict) -> dict:
    cv = payload.get("untrusted_redacted_cv", "")
    years = [float(m) for m in re.findall(r"(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|năm)", cv, flags=re.IGNORECASE)]
    lines = _sentences(cv)
    education = [{"description": line[:300]} for line in lines if any(h in line.lower() for h in _EDU_HINTS)][:5]
    work = [{"description": line[:300]} for line in lines
            if re.search(r"(19|20)\d{2}", line) and not any(h in line.lower() for h in _EDU_HINTS)][:10]
    return {
        "candidate_identifier": payload.get("candidate_identifier", ""),
        "total_years_experience": max(years) if years else 0.0,
        "education": education,
        "work_history": work,
        "skills": _keywords(cv, limit=25),
        "certifications": [],
        "languages": [],
        "projects": [],
    }


def _candidate_passages(payload: dict, criterion_id: str) -> list[dict]:
    """Either the whole redacted CV or, when the backend pre-selected them, the
    CV chunks retrieved for this criterion (with chunk_id/page_number)."""
    chunk_map = payload.get("untrusted_candidate_chunks_by_criterion")
    if isinstance(chunk_map, dict):
        return [{"text": c.get("text") or "", "chunk_id": c.get("chunk_id"), "page_number": c.get("page_number")}
                for c in chunk_map.get(criterion_id, []) if isinstance(c, dict)]
    return [{"text": payload.get("untrusted_redacted_cv", ""), "chunk_id": None, "page_number": None}]


def _match_criteria(payload: dict) -> dict:
    findings = []
    for criterion in payload.get("untrusted_rubric", []):
        criterion_id = str(criterion.get("criterion_id") or "")
        keywords = [k for k in (criterion.get("expected_evidence_keywords") or []) if isinstance(k, str) and k.strip()]
        if not keywords:
            keywords = _keywords(f"{criterion.get('name', '')} {criterion.get('description', '')}")
        best, hits, source = None, 0, None
        for passage in _candidate_passages(payload, criterion_id):
            flat = re.sub(r"\s+", " ", passage["text"])  # quote verification also normalises whitespace
            for sentence in _sentences(passage["text"]):
                count = sum(1 for k in keywords if k.lower() in sentence.lower())
                if count > hits and sentence in flat:  # the quote must be verbatim CV text
                    best, hits, source = sentence, count, passage
        if best:
            strong = hits >= 2
            evidence = {"verbatim_quote": best, "page_number": source["page_number"]}
            if source["chunk_id"] is not None:
                evidence["chunk_id"] = source["chunk_id"]
            findings.append({
                "criterion_id": criterion.get("criterion_id"),
                "outcome": "STRONG_MATCH" if strong else "MATCH",
                "confidence": 0.8 if strong else 0.65,
                "confidence_band": "HIGH" if strong else "MEDIUM",
                "reasoning": f"{MOCK_MARK} CV nhắc tới {hits} từ khóa của tiêu chí.",
                "evidence": evidence,
            })
        else:
            findings.append({
                "criterion_id": criterion.get("criterion_id"),
                "outcome": "UNCLEAR",
                "confidence": 0.5,
                "confidence_band": "LOW",
                "reasoning": f"{MOCK_MARK} Không tìm thấy từ khóa của tiêu chí trong CV.",
                "evidence": {"verbatim_quote": "", "page_number": None},
            })
    return {"candidate_identifier": payload.get("candidate_identifier", ""),
            "rubric_version": payload.get("rubric_version", ""), "findings": findings}


def respond(user_prompt: str) -> dict[str, Any]:
    """Route a prompt to the task it belongs to, by the keys llm_client sends."""
    payload = json.loads(user_prompt)
    if "untrusted_job_description" in payload:
        return _criteria_from_jd(payload)
    if "untrusted_rubric" in payload:
        return _match_criteria(payload)
    if "untrusted_redacted_cv" in payload:
        return _profile_from_cv(payload)
    raise ValueError("Unknown mock AI task")
