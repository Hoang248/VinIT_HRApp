import io

import pytest
from docx import Document

from app.core.exceptions import FileValidationError
from app.services.document_processor import document_processor
from app.services.matching import matching_engine


def test_matching_uses_weights_confidence_and_coverage():
    criteria = [
        {"criterion_id": "must", "category": "MUST_HAVE", "weight_in_group": 100},
        {"criterion_id": "nice", "category": "NICE_TO_HAVE", "weight_in_group": 100},
    ]
    findings = [
        {"criterion_id": "must", "outcome": "STRONG_MATCH", "confidence": .9, "confidence_band": "HIGH"},
        {"criterion_id": "nice", "outcome": "MATCH", "confidence": .8, "confidence_band": "HIGH"},
    ]
    score, coverage, status, _, review = matching_engine.calculate_assessment_scores(criteria, findings)
    assert (score, coverage, status, review) == (94.0, 1.0, "MEETS_MANDATORY", False)
    score, coverage, status, _, review = matching_engine.calculate_assessment_scores(criteria, findings[1:])
    assert (score, coverage, status, review) == (24.0, 0.3, "NEEDS_HR_VERIFICATION", True)
    findings[0]["outcome"] = "NO_MATCH"
    assert matching_engine.calculate_assessment_scores(criteria, findings)[2] == "POSSIBLE_MISMATCH"


def test_unverified_quotes_and_duplicates_are_not_authoritative():
    text = "Developed Python systems for five years."
    assert matching_engine.verify_verbatim_quote("Python systems for five years", text)
    assert not matching_engine.verify_verbatim_quote("Managed a completely imaginary team", text)
    pages = "--- Page 1 ---\nOther content\n--- Page 2 ---\nDeveloped Python systems for five years."
    assert matching_engine.quote_pages("Python systems for five years", pages) == [2]
    assert matching_engine.quote_pages("Python systems for five years", text) == []
    apps = [{"application_id": "a", "identity": {"email": "TEST@example.com"}},
            {"application_id": "b", "identity": {"email": "test@example.com"}},
            {"application_id": "c", "identity": {}}]
    assert matching_engine.detect_duplicates(apps) == [("a", "b", .98, "EMAIL_MATCH")]


@pytest.mark.asyncio
async def test_validates_file_signature_and_does_not_trust_filename():
    doc = Document(); doc.add_paragraph("Candidate experience with Python")
    out = io.BytesIO(); doc.save(out)
    mime = await document_processor.validate_file(out.getvalue(), "candidate.docx", "application/octet-stream")
    assert "wordprocessingml" in mime
    with pytest.raises(FileValidationError):
        await document_processor.validate_file(b"not a pdf", "candidate.pdf", "application/pdf")
    with pytest.raises(FileValidationError):
        await document_processor.validate_file(b"<html>bad</html>", "candidate.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")


def test_llm_external_endpoint_policy_fails_closed(monkeypatch):
    from app.core.config import settings
    from app.services.llm_client import LLMClient, LLMError
    instance = LLMClient()
    monkeypatch.setattr(settings, "ALLOW_EXTERNAL_API", False)
    instance.base_url = "http://127.0.0.1:11434/v1"
    instance._check_endpoint_policy()
    instance.base_url = "https://8.8.8.8/v1"
    with pytest.raises(LLMError, match="External"):
        instance._check_endpoint_policy()
    instance.base_url = None
    with pytest.raises(LLMError, match="not configured"):
        instance._check_endpoint_policy()
    instance.base_url = "https://8.8.8.8/v1"
    monkeypatch.setattr(settings, "ALLOW_EXTERNAL_API", True)
    instance._check_endpoint_policy()


@pytest.mark.asyncio
async def test_blank_scanned_pdf_page_markers_do_not_count_as_cv_text(monkeypatch):
    from app.services.document_processor import DocumentType
    async def validate(*args):
        return "application/pdf"
    async def detect(*args):
        return DocumentType.PDF_SCANNED
    async def extract(*args):
        return ("\n".join(f"--- Page {i} ---" for i in range(1, 10)),
                [{"page_number": i, "content": ""} for i in range(1, 10)])
    monkeypatch.setattr(document_processor, "validate_file", validate)
    monkeypatch.setattr(document_processor, "detect_document_type", detect)
    monkeypatch.setattr(document_processor, "extract_text_from_pdf_scan", extract)
    with pytest.raises(FileValidationError, match="sufficient text"):
        await document_processor.process_document(b"%PDF-", "blank.pdf", "application/pdf")


def test_versioned_group_weights_are_used_and_invalid_confidence_is_unclear():
    criteria = [
        {"criterion_id": "must", "category": "MUST_HAVE", "weight_in_group": 100},
        {"criterion_id": "nice", "category": "NICE_TO_HAVE", "weight_in_group": 100},
    ]
    findings = [
        {"criterion_id": "must", "outcome": "STRONG_MATCH", "confidence": .9, "confidence_band": "HIGH"},
        {"criterion_id": "nice", "outcome": "MATCH", "confidence": .8, "confidence_band": "MEDIUM"},
    ]
    result = matching_engine.calculate_assessment_scores(criteria, findings, {"MUST_HAVE": .5, "NICE_TO_HAVE": .5})
    assert result[:3] == (90.0, 1.0, "MEETS_MANDATORY")
    findings[0]["confidence_band"] = "not a real band"
    result = matching_engine.calculate_assessment_scores(criteria, findings, {"MUST_HAVE": .5, "NICE_TO_HAVE": .5})
    assert result[2] == "NEEDS_HR_VERIFICATION"
    assert result[3][0]["outcome"] == "UNCLEAR" and result[3][0]["requires_verification"]
    findings[0].update(confidence=5, confidence_band="HIGH")
    assert matching_engine.calculate_assessment_scores(criteria, findings)[3][0]["outcome"] == "UNCLEAR"


def test_integration_database_guard_rejects_libpq_overrides():
    import os
    import subprocess
    import sys
    from pathlib import Path
    conftest = Path(__file__).with_name("conftest.py")
    for url in (
        "postgresql://postgres@localhost/hra_test?hostaddr=8.8.8.8",
        "postgresql://postgres@localhost/hra_test?dbname=production",
        "postgresql://postgres@localhost/hra_test?host=evil.example",
        "postgresql://postgres@/hra_test",  # PGHOST may be remote
    ):
        result = subprocess.run([sys.executable, str(conftest)], env={**os.environ, "TEST_DATABASE_URL": url},
                                capture_output=True, text=True, timeout=5)
        assert result.returncode != 0
        assert "explicit local disposable" in result.stderr


@pytest.mark.asyncio
async def test_llm_client_does_not_route_cv_through_environment_proxy(monkeypatch):
    from app.services.llm_client import LLMClient
    from app.core.config import settings
    captured = {}
    class FakeResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": [{"message": {"content": '{"ok":true}'}}]}
    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, *args, **kwargs):
            return FakeResponse()
    monkeypatch.setattr("app.services.llm_client.httpx.AsyncClient", FakeClient)
    monkeypatch.setattr(settings, "ALLOW_EXTERNAL_API", False)
    llm = LLMClient(); llm.base_url = "http://127.0.0.1:11434/v1"
    assert await llm._call_llm("system", "test") == {"ok": True}
    assert captured["trust_env"] is False


def test_database_does_not_log_cv_parameters():
    from app.db.database import engine
    assert engine.hide_parameters is True
    assert engine.echo is False


def test_coverage_rounding_cannot_promote_a_below_threshold_candidate():
    criteria = [
        {"criterion_id": "covered", "category": "MUST_HAVE", "weight_in_group": 99.9},
        {"criterion_id": "missing", "category": "MUST_HAVE", "weight_in_group": .1},
        {"criterion_id": "optional", "category": "NICE_TO_HAVE", "weight_in_group": 100},
    ]
    findings = [{"criterion_id": "covered", "outcome": "MATCH", "confidence": .9, "confidence_band": "HIGH"}]
    _, coverage, status, _, _ = matching_engine.calculate_assessment_scores(criteria, findings)
    assert coverage == .69 and status == "NEEDS_HR_VERIFICATION"
    ranked = matching_engine.rank_applications([{"latest_assessment": {"matching_status": status, "evidence_coverage": coverage}}], criteria)
    assert ranked[0]["rank_number"] is None


def test_zero_score_sorts_above_missing_score():
    rows = [
        {"id": "missing", "latest_assessment": {"matching_status": "NEEDS_HR_VERIFICATION", "matching_score": None, "evidence_coverage": .9}},
        {"id": "zero", "latest_assessment": {"matching_status": "NEEDS_HR_VERIFICATION", "matching_score": 0, "evidence_coverage": .7}},
    ]
    assert [row["id"] for row in matching_engine.rank_applications(rows, [])] == ["zero", "missing"]


def test_login_distinguishes_invalid_credentials_from_unavailable_service(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.config import settings
    from app.api import auth
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://example.test")
    monkeypatch.setattr(settings, "SUPABASE_ANON_KEY", "example")
    class AuthFailure(Exception):
        status = 400
    class FakeAuth:
        failure = AuthFailure()
        def sign_in_with_password(self, *_):
            raise self.failure
    fake = FakeAuth()
    monkeypatch.setattr(auth, "create_client", lambda *_: type("Client", (), {"auth": fake})())
    with TestClient(app) as client:
        credentials = {"email": "demo@example.test", "password": "not-a-real-password"}
        assert client.post("/v1/auth/login", json=credentials).status_code == 401
        fake.failure = RuntimeError("network failure")
        response = client.post("/v1/auth/login", json=credentials)
        assert response.status_code == 503 and "không khả dụng" in response.json()["detail"]
