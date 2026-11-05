"""Integration tests against real PostgreSQL with mocked external AI only."""
import io
import os
from uuid import uuid4

import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import get_current_user
from app.db.database import engine
from app.main import app

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database")


def uid():
    return str(uuid4())


@pytest.fixture
def seed():
    ids = {key: uid() for key in ("hr", "hm", "other", "hr2", "pos", "pos2", "jd", "cv", "criterion", "app", "app2")}
    with engine.begin() as conn:
        # Only positions (and dependent data) are truncated; the default scoring policy remains intact.
        conn.execute(text("TRUNCATE app_private.positions CASCADE"))
        for key in ("hr", "hm", "other", "hr2"):
            conn.execute(text("INSERT INTO auth.users(id) VALUES (:id)"), {"id": ids[key]})
            conn.execute(text("INSERT INTO app_private.user_profiles(user_id, display_name) VALUES (:id, :name)"), {"id": ids[key], "name": key.upper()})
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id, role_code) VALUES (:id, 'HR_RECRUITER')"), {"id": ids["hr"]})
        for key in ("pos", "pos2"):
            creator = ids["hr"] if key == "pos" else ids["hr2"]
            conn.execute(text("INSERT INTO app_private.positions(position_id, position_code, title, created_by) VALUES (:id, :code, :title, :creator)"),
                         {"id": ids[key], "code": ids[key], "title": key, "creator": creator})
        for pos, user, role in (("pos", "hr", "HR_RECRUITER"), ("pos", "hm", "HIRING_MANAGER"), ("pos2", "hr2", "HR_RECRUITER")):
            conn.execute(text("INSERT INTO app_private.position_assignments(position_id,user_id,position_role) VALUES (:pos,:user,:role)"),
                         {"pos": ids[pos], "user": ids[user], "role": role})
        conn.execute(text("INSERT INTO app_private.jd_versions(jd_version_id,position_id,version_number,content_text,created_by) VALUES (:id,:pos,1,'JD',:hr)"),
                     {"id": ids["jd"], "pos": ids["pos"], "hr": ids["hr"]})
        conn.execute(text("INSERT INTO app_private.criteria_versions(criteria_version_id,position_id,jd_version_id,version_number,status) VALUES (:id,:pos,:jd,1,'DRAFT')"),
                     {"id": ids["cv"], "pos": ids["pos"], "jd": ids["jd"], "hr": ids["hr"]})
        conn.execute(text("INSERT INTO app_private.criteria_items(criterion_id,criteria_version_id,name,description,category,weight_in_group,display_order) VALUES (:id,:cv,'Python','Python experience','MUST_HAVE',100,1)"),
                     {"id": ids["criterion"], "cv": ids["cv"]})
        for pos, user, a in (("pos", "hr", "app"), ("pos2", "hr2", "app2")):
            conn.execute(text("INSERT INTO app_private.applications(application_id,position_id,created_by) VALUES (:id,:pos,:user)"),
                         {"id": ids[a], "pos": ids[pos], "user": ids[user]})
            conn.execute(text("INSERT INTO app_private.application_identities(application_id,display_name) VALUES (:id,:name)"),
                         {"id": ids[a], "name": "Candidate " + a})
    return ids


@pytest.fixture
def client():
    async def identity(request):
        return {"user_id": request.headers["x-test-user"], "email": "test@example.org"}
    # FastAPI inspects the annotation to inject the request, not a query parameter.
    from starlette.requests import Request
    identity.__annotations__["request"] = Request
    app.dependency_overrides[get_current_user] = identity
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    client.close()


def headers(user):
    return {"x-test-user": user}


def test_position_scope_and_dashboard_counts(client, seed):
    r = client.get("/v1/positions", headers=headers(seed["hr"]))
    assert r.status_code == 200, r.text
    assert [p["position_id"] for p in r.json()] == [seed["pos"]]
    assert client.get(f"/v1/positions/{seed['pos']}", headers=headers(seed["hr"])).status_code == 200
    assert client.patch(f"/v1/positions/{seed['pos']}", headers=headers(seed["hm"]), json={"status": "PAUSED"}).status_code == 403
    r = client.get("/v1/positions", headers=headers(seed["other"]))
    assert r.status_code == 200 and r.json() == []
    r = client.get("/v1/dashboard/summary", headers=headers(seed["hr"]))
    assert r.status_code == 200, r.text
    assert r.json()["total_applications"] == 1
    assert r.json()["applications_by_status"]["NEW"] == 1
    r = client.get("/v1/dashboard/summary", headers=headers(seed["hm"]))
    assert r.status_code == 200 and r.json()["total_applications"] == 0
    r = client.get(f"/v1/dashboard/position/{seed['pos2']}", headers=headers(seed["hr"]))
    assert r.status_code == 403


def test_dual_approval_changes_and_immutable_approved_rubric(client, seed):
    base = f"/v1/criteria/{seed['cv']}"
    decision = lambda user, action, comment=None: client.post(base + "/approve", headers=headers(seed[user]), json={"action": action, "comment": comment})
    assert decision("hm", "APPROVE").status_code == 403
    assert decision("other", "APPROVE").status_code == 403
    assert decision("hr", "APPROVE").json()["status"] == "PENDING_HM_APPROVAL"
    assert decision("hr", "APPROVE").status_code == 403
    assert decision("hm", "REQUEST_CHANGES").status_code == 400
    assert decision("hm", "REQUEST_CHANGES", "Thêm yêu cầu dự án").json()["status"] == "DRAFT"
    item = f"{base}/items/{seed['criterion']}"
    assert client.patch(item, headers=headers(seed["hm"]), json={"description": "changed"}).status_code == 403
    assert client.patch(item, headers=headers(seed["hr"]), json={"description": "Dự án Python thực tế"}).status_code == 200
    assert decision("hr", "APPROVE").status_code == 200
    assert decision("hm", "APPROVE").json()["status"] == "APPROVED"
    assert client.patch(item, headers=headers(seed["hr"]), json={"name": "Changed"}).status_code == 400
    history = client.get(base + "/approval-events", headers=headers(seed["hr"]))
    assert history.status_code == 200 and len(history.json()) == 4
    assert history.json()[1]["comment"] == "Thêm yêu cầu dự án"


def test_status_shortlist_permissions_feedback_and_revocation(client, seed):
    base = f"/v1/applications/{seed['app']}"
    change = lambda user, status, reason=None: client.patch(base + "/status", headers=headers(seed[user]), json={"new_status": status, "reason": reason})
    assert change("hm", "IN_REVIEW").status_code == 403
    assert change("hr", "SHORTLIST").status_code == 400
    assert change("hr", "REJECTED_SCREENING").status_code == 400
    assert change("hr", "IN_REVIEW").status_code == 200
    assert change("hr", "SHORTLIST").status_code == 200
    assert client.get(base, headers=headers(seed["hm"])).status_code == 403
    payload = {"position_id": seed["pos"], "shared_with_user_id": seed["hm"], "application_ids": [seed["app"]], "allow_cv_view": False}
    assert client.post("/v1/shortlist/share", headers=headers(seed["other"]), json=payload).status_code == 403
    invalid = dict(payload, application_ids=[seed["app2"]])
    assert client.post("/v1/shortlist/share", headers=headers(seed["hr"]), json=invalid).status_code == 400
    response = client.post("/v1/shortlist/share", headers=headers(seed["hr"]), json=payload)
    assert response.status_code == 201, response.text
    share = response.json()["share_id"]
    for user, direction in (("hr", "sent"), ("hm", "received")):
        inbox = client.get("/v1/shortlist/shared-with-me", headers=headers(seed[user]))
        assert inbox.status_code == 200 and inbox.json()[0]["direction"] == direction
    detail = client.get(base, headers=headers(seed["hm"]))
    assert detail.status_code == 200 and detail.json()["can_view_cv"] is False
    assert client.get(base + "/cv-download-url", headers=headers(seed["hm"])).status_code == 403
    feedback = client.post(f"/v1/shortlist/{share}/feedback", headers=headers(seed["hm"]), json={"content": "Phù hợp", "application_id": seed["app"]})
    assert feedback.status_code == 201, feedback.text
    detail = client.get(f"/v1/shortlist/{share}", headers=headers(seed["hr"]))
    assert detail.status_code == 200 and detail.json()["feedback"][0]["author_name"] == "HM"
    assert client.post(f"/v1/shortlist/{share}/revoke", headers=headers(seed["hm"])).status_code == 403
    assert client.post(f"/v1/shortlist/{share}/revoke", headers=headers(seed["hr"])).status_code == 200
    assert client.get(base, headers=headers(seed["hm"])).status_code == 403
    assert client.get(f"/v1/shortlist/{share}", headers=headers(seed["hm"])).status_code == 403
    assert change("hr", "INTERVIEW").status_code == 200
    assert change("hr", "REJECTED_INTERVIEW", "Không phù hợp chuyên môn").status_code == 200
    with engine.connect() as conn:
        events = conn.execute(text("SELECT new_status, reason_code FROM app_private.application_status_events WHERE application_id=:a ORDER BY changed_at"), {"a": seed["app"]}).mappings().all()
    assert [x["new_status"] for x in events] == ["IN_REVIEW", "SHORTLIST", "INTERVIEW", "REJECTED_INTERVIEW"]
    assert events[-1]["reason_code"] == "Không phù hợp chuyên môn"
    history = client.get(base + "/status-events", headers=headers(seed["hr"]))
    assert history.status_code == 200 and history.json()[0]["reason"] == "Không phù hợp chuyên môn"
    assert client.get(base + "/status-events", headers=headers(seed["hm"])).status_code == 403


def test_operation_access_and_progress(client, seed):
    op, batch = uid(), uid()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.operations(operation_id,position_id,capability,requested_by,status) VALUES (:id,:pos,'CV_PROCESSING',:hr,'PROCESSING')"), {"id": op, "pos": seed["pos"], "hr": seed["hr"]})
        conn.execute(text("INSERT INTO app_private.cv_batches(batch_id,position_id,uploaded_by,operation_id,status,total_files,total_size_bytes,processed_files,failed_files) VALUES (:id,:pos,:hr,:op,'PROCESSING',4,100,2,1)"), {"id": batch, "pos": seed["pos"], "hr": seed["hr"], "op": op})
    response = client.get(f"/v1/operations/{op}", headers=headers(seed["hr"]))
    assert response.status_code == 200 and response.json()["progress"]["percent_complete"] == 75
    assert client.get(f"/v1/operations/{op}", headers=headers(seed["hm"])).status_code == 403
    assert client.get(f"/v1/operations/position/{seed['pos']}/active", headers=headers(seed["hr"])).json()["operation_id"] == op
    assert client.get(f"/v1/operations/position/{seed['pos']}/active", headers=headers(seed["other"])).status_code == 403


@pytest.mark.parametrize("valid_quote", [True, False])
def test_upload_worker_runs_scoped_pipeline_with_stubbed_ai(client, seed, tmp_path, monkeypatch, valid_quote):
    from app.core.config import settings
    from app.workers.processor import worker, llm_client
    from app.schemas.criteria import CriterionRating
    from app.services.matching import matching_engine
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    monkeypatch.setitem(matching_engine.SCORE_MAP, CriterionRating.STRONG_MATCH, 95)
    async def extract(**kwargs):
        return {"education": [], "work_history": [], "skills": ["Python"], "certifications": []}
    async def match(**kwargs):
        quote = "Developed Python systems for five years" if valid_quote else "Completely fabricated work experience"
        return {"findings": [{"criterion_id": kwargs["rubric"][0]["criterion_id"], "outcome": "STRONG_MATCH", "confidence": .9, "confidence_band": "HIGH", "evidence": {"verbatim_quote": quote, "page_number": 1}}]}
    monkeypatch.setattr(llm_client, "extract_candidate_profile", extract)
    monkeypatch.setattr(llm_client, "match_criterion_evidence", match)
    document = Document(); document.add_paragraph("Developed Python systems for five years. test@example.com")
    content = io.BytesIO(); document.save(content)
    files = [("files", ("candidate.docx", content.getvalue(), "application/octet-stream")),
             ("files", ("bad.pdf", b"not-a-pdf", "application/pdf"))]
    route = f"/v1/applications/upload-batch/{seed['pos']}"
    assert client.post(route, headers=headers(seed["hm"]), files=files).status_code == 403
    assert client.post(route, headers=headers(seed["hr"]), files=files).status_code == 400  # approvals required
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status='APPROVED' WHERE criteria_version_id=:id"), {"id": seed["cv"]})
    response = client.post(route, headers=headers(seed["hr"]), files=files)
    assert response.status_code == 202, response.text
    op = response.json()["operation_id"]
    progress = client.get(f"/v1/operations/{op}", headers=headers(seed["hr"])).json()["progress"]
    assert progress["total"] == 2 and progress["processed"] == 0 and progress["failed"] == 1
    assert progress["invalid_files"][0]["original_filename"] == "bad.pdf"
    assert client.post(route, headers=headers(seed["hr"]), files=files).status_code == 409
    queued = client.post(f"/v1/assessments/run/{seed['pos']}", headers=headers(seed["hr"]))
    assert queued.status_code == 202 and queued.json()["operation_id"] == op
    worker._process_pending_operations()
    with engine.connect() as conn:
        operation = conn.execute(text("SELECT status,error_message FROM app_private.operations WHERE operation_id=:id"), {"id": op}).mappings().one()
        assert operation["status"] == "COMPLETED", operation["error_message"]
        uploaded_app = str(conn.execute(text("SELECT application_id FROM app_private.cv_batch_items WHERE batch_id=(SELECT batch_id FROM app_private.cv_batches WHERE operation_id=:op) AND application_id IS NOT NULL"), {"op": op}).scalar_one())
        result = conn.execute(text("SELECT matching_status,matching_score,evidence_coverage FROM app_private.assessment_runs WHERE application_id=:app AND status='COMPLETED'"), {"app": uploaded_app}).mappings().one()
        assert result["matching_status"] == ("MEETS_MANDATORY" if valid_quote else "NEEDS_HR_VERIFICATION")
        assert float(result["matching_score"]) == 95 if valid_quote else result["matching_score"] is None
        criterion_score = conn.execute(text("SELECT score FROM app_private.criterion_assessment_results")).scalar_one()
        assert float(criterion_score) == 95 if valid_quote else criterion_score is None
        assert conn.execute(text("SELECT verification_status FROM app_private.evidence_items")).scalar_one() == ("VERIFIED" if valid_quote else "FAILED")
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.ranking_items WHERE position_id=:pos"), {"pos": seed["pos"]}).scalar_one() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.assessment_runs WHERE application_id=:app"), {"app": seed["app2"]}).scalar_one() == 0
        assert conn.execute(text("SELECT application_status FROM app_private.applications WHERE application_id=:app"), {"app": uploaded_app}).scalar_one() == "NEW"
    assert client.get(f"/v1/applications/{uploaded_app}/cv-file", headers=headers(seed["hr"])).content == content.getvalue()
    assert client.get(f"/v1/applications/{uploaded_app}/cv-file", headers=headers(seed["hm"])).status_code == 403
    detail = client.get(f"/v1/applications/{uploaded_app}", headers=headers(seed["hr"]))
    assert detail.status_code == 200 and len(detail.json()["latest_assessment"]["criterion_results"]) == 1
    listed = client.get(f"/v1/applications?position_id={seed['pos']}", headers=headers(seed["hr"]))
    assert listed.status_code == 200 and len(listed.json()) == 2
    progress = client.get(f"/v1/operations/{op}", headers=headers(seed["hr"])).json()
    assert progress["status"] == "COMPLETED" and progress["progress"]["processed"] == 1
    ranking = client.get(f"/v1/assessments/ranking/latest/{seed['pos']}", headers=headers(seed["hr"]))
    assert ranking.status_code == 200 and ranking.json()[0]["application_id"] == uploaded_app
    assessment_id = detail.json()["latest_assessment"]["assessment_id"]
    assert client.get(f"/v1/assessments/{assessment_id}", headers=headers(seed["hr"])).status_code == 200
    for state in ("IN_REVIEW", "SHORTLIST"):
        assert client.patch(f"/v1/applications/{uploaded_app}/status", headers=headers(seed["hr"]), json={"new_status": state}).status_code == 200
    share_payload = {"position_id": seed["pos"], "shared_with_user_id": seed["hm"], "application_ids": [uploaded_app], "allow_cv_view": False}
    shared = client.post("/v1/shortlist/share", headers=headers(seed["hr"]), json=share_payload).json()["share_id"]
    summary = client.get(f"/v1/applications/{uploaded_app}", headers=headers(seed["hm"]))
    assert summary.status_code == 200 and summary.json()["latest_assessment"]["criterion_results"] == []
    assert client.get(f"/v1/assessments/{assessment_id}", headers=headers(seed["hm"])).status_code == 403
    assert client.get(f"/v1/applications/{uploaded_app}/cv-file", headers=headers(seed["hm"])).status_code == 403
    assert client.post(f"/v1/shortlist/{shared}/revoke", headers=headers(seed["hr"])).status_code == 200
    shared = client.post("/v1/shortlist/share", headers=headers(seed["hr"]), json={**share_payload, "allow_cv_view": True}).json()["share_id"]
    assert client.get(f"/v1/applications/{uploaded_app}/cv-file", headers=headers(seed["hm"])).content == content.getvalue()
    assert client.get(f"/v1/assessments/{assessment_id}", headers=headers(seed["hm"])).status_code == 200
    assert client.post(f"/v1/shortlist/{shared}/revoke", headers=headers(seed["hr"])).status_code == 200
    assert client.get(f"/v1/applications/{uploaded_app}/cv-file", headers=headers(seed["hm"])).status_code == 403


def test_create_position_requires_hr_and_assigned_hm(client, seed):
    payload = {"position_code": "NEW-001", "title": "Engineer", "jd_content": "Job description", "hiring_manager_user_id": seed["hm"]}
    assert client.post("/v1/positions", headers=headers(seed["hm"]), json=payload).status_code == 403
    assert client.post("/v1/positions", headers=headers(seed["hr"]), json={**payload, "hiring_manager_user_id": None}).status_code == 400
    result = client.post("/v1/positions", headers=headers(seed["hr"]), json=payload)
    assert result.status_code == 201, result.text
    created = result.json()["position_id"]
    with engine.connect() as conn:
        roles = conn.execute(text("SELECT position_role FROM app_private.position_assignments WHERE position_id=:id ORDER BY position_role"), {"id": created}).scalars().all()
        assert roles == ["HIRING_MANAGER", "HR_RECRUITER"]
        assert conn.execute(text("SELECT content_text FROM app_private.jd_versions WHERE position_id=:id"), {"id": created}).scalar_one() == "Job description"


def test_status_to_acceptance_is_explicit_and_audited(client, seed):
    route = f"/v1/applications/{seed['app']}/status"
    for step in ("IN_REVIEW", "SHORTLIST", "INTERVIEW", "OFFERED", "ACCEPTED"):
        assert client.patch(route, headers=headers(seed["hr"]), json={"new_status": step}).status_code == 200
    assert client.patch(route, headers=headers(seed["hr"]), json={"new_status": "IN_REVIEW"}).status_code == 400
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.application_status_events WHERE application_id=:id"), {"id": seed["app"]}).scalar_one() == 5


def test_simultaneous_hr_approval_records_one_decision(client, seed):
    from concurrent.futures import ThreadPoolExecutor
    route = f"/v1/criteria/{seed['cv']}/approve"
    def approve():
        return client.post(route, headers=headers(seed["hr"]), json={"action": "APPROVE"}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(lambda _: approve(), range(2)))
    assert statuses == [200, 403]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.criteria_approval_events WHERE criteria_version_id=:id"), {"id": seed["cv"]}).scalar_one() == 1


def test_generate_criteria_requires_hr_and_rejects_invalid_ai(client, seed, monkeypatch):
    from app.api.criteria import llm_client
    async def invalid(**kwargs):
        return {"criteria": []}
    monkeypatch.setattr(llm_client, "extract_criteria_from_jd", invalid)
    route = f"/v1/criteria/generate/{seed['pos']}"
    assert client.post(route, headers=headers(seed["hm"])).status_code == 403
    assert client.post(route, headers=headers(seed["hr"])).status_code == 502
    async def valid(**kwargs):
        return {"criteria": [{"name": "Python", "description": "Real projects", "category": "MUST_HAVE", "weight": 100, "expected_evidence_keywords": ["Python"]}]}
    monkeypatch.setattr(llm_client, "extract_criteria_from_jd", valid)
    response = client.post(route, headers=headers(seed["hr"]))
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "DRAFT" and response.json()["version_number"] == 2
    versions = client.get(f"/v1/criteria/position/{seed['pos']}/versions", headers=headers(seed["hm"]))
    assert versions.status_code == 200 and len(versions.json()) == 2


def test_batch_level_failure_marks_unfinished_documents_for_review(client, seed, tmp_path, monkeypatch):
    from app.core.config import settings
    from app.workers.processor import worker
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    document = Document(); document.add_paragraph("Candidate experience")
    content = io.BytesIO(); document.save(content)
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status='APPROVED' WHERE criteria_version_id=:id"), {"id": seed["cv"]})
    response = client.post(f"/v1/applications/upload-batch/{seed['pos']}", headers=headers(seed["hr"]), files={"files": ("candidate.docx", content.getvalue())})
    assert response.status_code == 202
    op = response.json()["operation_id"]
    def fail(*args):
        raise RuntimeError("Simulated batch failure")
    monkeypatch.setattr(worker, "_process_cv_batch", fail)
    worker._process_pending_operations()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM app_private.operations WHERE operation_id=:id"), {"id": op}).scalar_one() == "FAILED"
        assert conn.execute(text("SELECT file_processing_status FROM app_private.application_documents")).scalar_one() == "NEEDS_HR_REVIEW"


def test_revoked_roles_and_grants_do_not_bypass_application_permissions(client, seed):
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.position_assignments SET revoked_at=NOW() WHERE user_id=:id AND position_id=:pos"), {"id": seed["hr"], "pos": seed["pos"]})
        conn.execute(text("INSERT INTO app_private.position_access_grants(position_id,user_id,permission_code) VALUES (:pos,:id,'VIEW_CV')"), {"id": seed["hr"], "pos": seed["pos"]})
    assert client.get(f"/v1/applications/{seed['app']}", headers=headers(seed["hr"])).status_code == 403
    assert client.patch(f"/v1/applications/{seed['app']}/status", headers=headers(seed["hr"]), json={"new_status": "IN_REVIEW"}).status_code == 403


def test_admin_endpoints_require_active_admin_and_do_not_pretend_to_apply_config(client, seed):
    assert client.get("/v1/admin/ai/active-config", headers=headers(seed["hr"])).status_code == 403
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id,role_code) VALUES (:id,'ADMIN')"), {"id": seed["other"]})
    response = client.get("/v1/admin/ai/active-config", headers=headers(seed["other"]))
    assert response.status_code == 200 and response.json()["source"] == "environment"
    assert "api_key" not in response.json()["config"]
    assert client.post("/v1/admin/ai/config", headers=headers(seed["other"]), json={"provider": "local", "model_name": "x"}).status_code == 501
    assert client.post(f"/v1/admin/ai/config/{uid()}/enable", headers=headers(seed["other"])).status_code == 501
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.user_role_assignments SET revoked_at=NOW() WHERE user_id=:id AND role_code='ADMIN'"), {"id": seed["other"]})
    assert client.get("/v1/admin/ai/active-config", headers=headers(seed["other"])).status_code == 403


def test_jwt_and_account_status_are_enforced(seed, monkeypatch):
    import jwt
    import time
    from app.core.config import settings
    secret = "test-secret-not-used-in-production-" + "x" * 32
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", secret)
    claims = {"sub": seed["hr"], "aud": "authenticated", "email": "test@example.org", "exp": int(time.time()) + 3600}
    token = jwt.encode(claims, secret, algorithm="HS256")
    with TestClient(app) as real_client:
        assert real_client.get("/v1/auth/me").status_code == 401
        for invalid in (
            jwt.encode({k: v for k, v in claims.items() if k != "exp"}, secret, algorithm="HS256"),
            jwt.encode({**claims, "exp": int(time.time()) - 1}, secret, algorithm="HS256"),
            jwt.encode({**claims, "aud": "other"}, secret, algorithm="HS256"),
            jwt.encode(claims, secret, algorithm="HS384"),
        ):
            assert real_client.get("/v1/auth/me", headers={"Authorization": "Bearer " + invalid}).status_code == 401
        assert real_client.get("/v1/auth/me", headers={"Authorization": "Bearer " + token + " extra"}).status_code == 401
        response = real_client.get("/v1/auth/me", headers={"Authorization": "Bearer " + token})
        assert response.status_code == 200 and response.json()["display_name"] == "HR"
        with engine.begin() as conn:
            conn.execute(text("UPDATE app_private.user_profiles SET account_status='SUSPENDED' WHERE user_id=:id"), {"id": seed["hr"]})
        assert real_client.get("/v1/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 403
        monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "")
        assert real_client.get("/v1/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 503


def test_revoking_assignment_also_removes_shortlist_access(client, seed):
    route = f"/v1/applications/{seed['app']}/status"
    for state in ("IN_REVIEW", "SHORTLIST"):
        assert client.patch(route, headers=headers(seed["hr"]), json={"new_status": state}).status_code == 200
    payload = {"position_id": seed["pos"], "shared_with_user_id": seed["hm"], "application_ids": [seed["app"]], "allow_cv_view": True}
    share = client.post("/v1/shortlist/share", headers=headers(seed["hr"]), json=payload).json()["share_id"]
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.position_assignments SET revoked_at=NOW() WHERE user_id=:id AND position_id=:pos"), {"id": seed["hm"], "pos": seed["pos"]})
    assert client.get(f"/v1/shortlist/{share}", headers=headers(seed["hm"])).status_code == 403
    assert client.get(f"/v1/applications/{seed['app']}", headers=headers(seed["hm"])).status_code == 403
    assert client.get("/v1/shortlist/shared-with-me", headers=headers(seed["hm"])).json() == []
    assert client.get("/v1/dashboard/summary", headers=headers(seed["hm"])).json()["total_applications"] == 0
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.position_assignments SET revoked_at=NOW() WHERE user_id=:id AND position_id=:pos"), {"id": seed["hr"], "pos": seed["pos"]})
    assert client.get(f"/v1/shortlist/{share}", headers=headers(seed["hr"])).status_code == 403


def test_position_metrics_and_latest_criteria_follow_application_scope(client, seed):
    route = f"/v1/positions/{seed['pos']}"
    recruiter = client.get(route, headers=headers(seed["hr"]))
    assert recruiter.status_code == 200, recruiter.text
    assert recruiter.json()["total_applications"] == 1
    assert recruiter.json()["new_applications"] == 1
    assert recruiter.json()["criteria_status"] == "DRAFT"
    assert recruiter.json()["criteria_approved"] is False
    manager = client.get(route, headers=headers(seed["hm"]))
    assert manager.status_code == 200 and manager.json()["total_applications"] == 0
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status='APPROVED' WHERE criteria_version_id=:id"), {"id": seed["cv"]})
        conn.execute(text("INSERT INTO app_private.criteria_versions (position_id,jd_version_id,version_number,status) VALUES (:pos,:jd,2,'DRAFT')"), {"pos": seed["pos"], "jd": seed["jd"]})
    recruiter = client.get(route, headers=headers(seed["hr"])).json()
    assert recruiter["criteria_approved"] is True and recruiter["criteria_status"] == "DRAFT"
    status_route = f"/v1/applications/{seed['app']}/status"
    for state in ("IN_REVIEW", "SHORTLIST"):
        assert client.patch(status_route, headers=headers(seed["hr"]), json={"new_status": state}).status_code == 200
    share = client.post("/v1/shortlist/share", headers=headers(seed["hr"]), json={
        "position_id": seed["pos"], "shared_with_user_id": seed["hm"],
        "application_ids": [seed["app"]], "allow_cv_view": False,
    })
    assert share.status_code == 201, share.text
    manager = client.get(route, headers=headers(seed["hm"])).json()
    assert manager["total_applications"] == manager["shortlisted"] == 1
    assert client.post(f"/v1/shortlist/{share.json()['share_id']}/revoke", headers=headers(seed["hr"])).status_code == 200
    assert client.get(route, headers=headers(seed["hm"])).json()["total_applications"] == 0


def test_position_scoped_hr_lead_has_hr_access_only_on_assigned_position(client, seed):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.position_assignments(position_id,user_id,position_role) VALUES (:pos,:id,'HR_LEAD')"),
                     {"pos": seed["pos"], "id": seed["other"]})
    lead = headers(seed["other"])
    positions = client.get("/v1/positions", headers=lead)
    assert positions.status_code == 200 and [p["position_id"] for p in positions.json()] == [seed["pos"]]
    assert positions.json()[0]["total_applications"] == 1
    assert client.get(f"/v1/applications/{seed['app']}", headers=lead).status_code == 200
    assert client.get(f"/v1/applications/{seed['app2']}", headers=lead).status_code == 403
    assert client.get(f"/v1/dashboard/position/{seed['pos2']}", headers=lead).status_code == 403
    assert client.patch(f"/v1/applications/{seed['app']}/status", headers=lead, json={"new_status": "IN_REVIEW"}).status_code == 200
    assert client.post(f"/v1/criteria/{seed['cv']}/approve", headers=lead, json={"action": "APPROVE"}).json()["status"] == "PENDING_HM_APPROVAL"
    assert client.post(f"/v1/criteria/{seed['cv']}/approve", headers=headers(seed["hm"]), json={"action": "APPROVE"}).json()["status"] == "APPROVED"


def test_private_schema_and_public_views_are_backend_only_after_migration():
    with engine.connect() as conn:
        for role in ("anon", "authenticated"):
            assert not conn.execute(text("SELECT has_schema_privilege(:role, 'app_private', 'USAGE')"), {"role": role}).scalar_one()
            for relation in ("app_private.applications", "public.applications"):
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    assert not conn.execute(text("SELECT has_table_privilege(:role, :relation, :privilege)"),
                                            {"role": role, "relation": relation, "privilege": privilege}).scalar_one()
            executable = conn.execute(text("""
                SELECT COUNT(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                WHERE n.nspname='app_private' AND has_function_privilege(:role, p.oid, 'EXECUTE')
            """), {"role": role}).scalar_one()
            assert executable == 0
        assert conn.execute(text("SELECT has_schema_privilege('service_role', 'app_private', 'USAGE')")).scalar_one()
        assert conn.execute(text("SELECT has_table_privilege('service_role', 'public.applications', 'SELECT')")).scalar_one()


def test_group_weights_are_approved_immutable_and_drive_worker_score(client, seed, tmp_path, monkeypatch):
    from app.core.config import settings
    from app.workers.processor import worker, llm_client
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    second_criterion = uid()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO app_private.criteria_items(criterion_id,criteria_version_id,name,description,category,weight_in_group,display_order)
            VALUES (:id,:cv,'Testing','Testing experience','NICE_TO_HAVE',100,2)
        """), {"id": second_criterion, "cv": seed["cv"]})
    weights_route = f"/v1/criteria/{seed['cv']}/weights"
    weights = {"mandatory_weight_total": 50, "nice_to_have_weight_total": 50}
    assert client.patch(weights_route, headers=headers(seed["hm"]), json=weights).status_code == 403
    assert client.patch(weights_route, headers=headers(seed["hr"]), json={**weights, "nice_to_have_weight_total": 49}).status_code == 422
    assert client.patch(weights_route, headers=headers(seed["hr"]), json={"mandatory_weight_total": 0, "nice_to_have_weight_total": 100}).status_code == 422
    changed = client.patch(weights_route, headers=headers(seed["hr"]), json=weights)
    assert changed.status_code == 200 and changed.json()["mandatory_weight_total"] == 50
    approve = f"/v1/criteria/{seed['cv']}/approve"
    assert client.post(approve, headers=headers(seed["hr"]), json={"action": "APPROVE"}).status_code == 200
    assert client.patch(weights_route, headers=headers(seed["hr"]), json=weights).status_code == 400
    assert client.post(approve, headers=headers(seed["hm"]), json={"action": "APPROVE"}).status_code == 200
    assert client.patch(weights_route, headers=headers(seed["hr"]), json=weights).status_code == 400

    async def extract(**kwargs):
        return {"education": [], "work_history": [], "skills": ["Python"], "certifications": []}
    async def match(**kwargs):
        return {"findings": [
            {"criterion_id": seed["criterion"], "outcome": "STRONG_MATCH", "confidence": .9,
             "confidence_band": "HIGH", "evidence": {"verbatim_quote": "Developed Python systems for five years"}},
            {"criterion_id": second_criterion, "outcome": "MATCH", "confidence": .8,
             "confidence_band": "MEDIUM", "evidence": {"verbatim_quote": "Built reliable automated testing systems"}},
        ]}
    monkeypatch.setattr(llm_client, "extract_candidate_profile", extract)
    monkeypatch.setattr(llm_client, "match_criterion_evidence", match)
    document = Document(); document.add_paragraph("Developed Python systems for five years. Built reliable automated testing systems.")
    content = io.BytesIO(); document.save(content)
    upload = client.post(f"/v1/applications/upload-batch/{seed['pos']}", headers=headers(seed["hr"]), files={"files": ("candidate.docx", content.getvalue())})
    assert upload.status_code == 202, upload.text
    worker._process_pending_operations()
    with engine.connect() as conn:
        assessment = conn.execute(text("""
            SELECT matching_score, evidence_coverage, criteria_version_id FROM app_private.assessment_runs
            WHERE operation_id=:op AND status='COMPLETED'
        """), {"op": upload.json()["operation_id"]}).mappings().one()
        assert float(assessment["matching_score"]) == 90.0
        assert float(assessment["evidence_coverage"]) == 1.0
        assert str(assessment["criteria_version_id"]) == seed["cv"]
        ranking_version = conn.execute(text("SELECT criteria_version_id FROM app_private.ranking_runs WHERE operation_id=:op"), {"op": upload.json()["operation_id"]}).scalar_one()
        assert str(ranking_version) == seed["cv"]
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.audit_events WHERE action_type='UPDATE_CRITERIA_WEIGHTS'")).scalar_one() == 1


def test_revoked_requester_cannot_read_operation_progress(client, seed):
    op = uid()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.operations(operation_id,position_id,capability,requested_by,status) VALUES (:id,:pos,'CV_PROCESSING',:hr,'PROCESSING')"),
                     {"id": op, "pos": seed["pos"], "hr": seed["hr"]})
    assert client.get(f"/v1/operations/{op}", headers=headers(seed["hr"])).status_code == 200
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.position_assignments SET revoked_at=NOW() WHERE user_id=:id AND position_id=:pos"),
                     {"id": seed["hr"], "pos": seed["pos"]})
    assert client.get(f"/v1/operations/{op}", headers=headers(seed["hr"])).status_code == 403


def test_empty_assessment_returns_real_completed_operation(client, seed):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM app_private.applications WHERE application_id=:id"), {"id": seed["app"]})
        conn.execute(text("UPDATE app_private.criteria_versions SET status='APPROVED' WHERE criteria_version_id=:id"), {"id": seed["cv"]})
    result = client.post(f"/v1/assessments/run/{seed['pos']}", headers=headers(seed["hr"]))
    assert result.status_code == 202 and result.json()["status"] == "completed"
    operation = client.get(f"/v1/operations/{result.json()['operation_id']}", headers=headers(seed["hr"]))
    assert operation.status_code == 200 and operation.json()["status"] == "COMPLETED"


def test_user_directory_is_hr_only_or_scoped_to_visible_position(client, seed):
    assert client.get("/v1/users?search=HM", headers=headers(seed["hr"])).status_code == 200
    assert client.get("/v1/users", headers=headers(seed["hm"])).status_code == 403
    scoped = client.get(f"/v1/users?position_id={seed['pos']}", headers=headers(seed["hm"]))
    assert scoped.status_code == 200
    assert {u["user_id"] for u in scoped.json()} == {seed["hm"], seed["hr"]}
    assert client.get(f"/v1/users?position_id={seed['pos2']}", headers=headers(seed["hm"])).status_code == 403


def test_position_status_lifecycle_sets_current_closure_and_audits(client, seed):
    route = f"/v1/positions/{seed['pos']}"
    assert client.patch(route, headers=headers(seed["hm"]), json={"status": "CLOSED"}).status_code == 403
    assert client.patch(route, headers=headers(seed["hr"]), json={"title": "  "}).status_code == 400
    paused = client.patch(route, headers=headers(seed["hr"]), json={"status": "PAUSED", "title": "  New title  "})
    assert paused.status_code == 200 and paused.json()["title"] == "New title" and paused.json()["closed_at"] is None
    closed = client.patch(route, headers=headers(seed["hr"]), json={"status": "CLOSED"})
    assert closed.status_code == 200 and closed.json()["closed_at"] is not None
    reopened = client.patch(route, headers=headers(seed["hr"]), json={"status": "OPEN"})
    assert reopened.status_code == 200 and reopened.json()["closed_at"] is None
    with engine.connect() as conn:
        events = conn.execute(text("SELECT previous_status,new_status FROM app_private.position_status_events WHERE position_id=:id ORDER BY changed_at"), {"id": seed["pos"]}).all()
        assert events == [("OPEN", "PAUSED"), ("PAUSED", "CLOSED"), ("CLOSED", "OPEN")]
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.audit_events WHERE action_type='UPDATE_POSITION' AND position_id=:id"), {"id": seed["pos"]}).scalar_one() == 3


def test_new_rubric_cannot_be_approved_during_active_position_operation(client, seed):
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status='APPROVED' WHERE criteria_version_id=:id"), {"id": seed["cv"]})
        next_cv = uid()
        conn.execute(text("INSERT INTO app_private.criteria_versions(criteria_version_id,position_id,jd_version_id,version_number,status) VALUES (:id,:pos,:jd,2,'DRAFT')"),
                     {"id": next_cv, "pos": seed["pos"], "jd": seed["jd"]})
        conn.execute(text("INSERT INTO app_private.criteria_items(criteria_version_id,name,description,category,weight_in_group,display_order) VALUES (:cv,'Skill','Relevant skill','MUST_HAVE',100,1)"), {"cv": next_cv})
    queued = client.post(f"/v1/assessments/run/{seed['pos']}", headers=headers(seed["hr"]))
    assert queued.status_code == 202 and queued.json()["status"] == "pending"
    approve = f"/v1/criteria/{next_cv}/approve"
    assert client.post(approve, headers=headers(seed["hr"]), json={"action": "APPROVE"}).status_code == 200
    blocked = client.post(approve, headers=headers(seed["hm"]), json={"action": "APPROVE"})
    assert blocked.status_code == 409, blocked.text
    with engine.begin() as conn:
        assert conn.execute(text("SELECT status FROM app_private.criteria_versions WHERE criteria_version_id=:id"), {"id": next_cv}).scalar_one() == "PENDING_HM_APPROVAL"
        conn.execute(text("UPDATE app_private.operations SET status='COMPLETED' WHERE operation_id=:id"), {"id": queued.json()["operation_id"]})
    assert client.post(approve, headers=headers(seed["hm"]), json={"action": "APPROVE"}).json()["status"] == "APPROVED"


def test_partial_upload_file_is_cleaned_up_if_write_fails(client, seed, tmp_path, monkeypatch):
    from app.core.config import settings
    from app.api import applications as applications_api
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status='APPROVED' WHERE criteria_version_id=:id"), {"id": seed["cv"]})
    document = Document(); document.add_paragraph("Some demonstration CV text which is long enough to process")
    content = io.BytesIO(); document.save(content)
    class FailingWriter:
        def __init__(self, path):
            self.path = path
        async def __aenter__(self):
            with open(self.path, "wb") as partial:
                partial.write(b"partial")
            raise OSError("simulated disk write failure")
        async def __aexit__(self, *args):
            return False
    monkeypatch.setattr(applications_api.aiofiles, "open", lambda path, mode: FailingWriter(path))
    with pytest.raises(OSError, match="simulated"):
        client.post(f"/v1/applications/upload-batch/{seed['pos']}", headers=headers(seed["hr"]), files={"files": ("candidate.docx", content.getvalue())})
    assert not [path for path in tmp_path.rglob('*') if path.is_file()]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.operations")).scalar_one() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.applications WHERE position_id=:pos"), {"pos": seed["pos"]}).scalar_one() == 1


def test_another_assigned_recruiter_can_find_and_manage_position_shares(client, seed):
    for state in ("IN_REVIEW", "SHORTLIST"):
        assert client.patch(f"/v1/applications/{seed['app']}/status", headers=headers(seed["hr"]), json={"new_status": state}).status_code == 200
    response = client.post("/v1/shortlist/share", headers=headers(seed["hr"]), json={
        "position_id": seed["pos"], "shared_with_user_id": seed["hm"], "application_ids": [seed["app"]], "allow_cv_view": False,
    })
    assert response.status_code == 201
    share = response.json()["share_id"]
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.position_assignments(position_id,user_id,position_role) VALUES (:pos,:id,'HR_RECRUITER')"),
                     {"pos": seed["pos"], "id": seed["hr2"]})
    inbox = client.get("/v1/shortlist/shared-with-me", headers=headers(seed["hr2"]))
    assert inbox.status_code == 200 and inbox.json()[0]["share_id"] == share and inbox.json()[0]["direction"] == "sent"
    assert client.post(f"/v1/shortlist/{share}/revoke", headers=headers(seed["hr2"])).status_code == 200
    assert client.get(f"/v1/shortlist/{share}", headers=headers(seed["hm"])).status_code == 403


def test_admin_receives_not_found_for_unknown_position(client, seed):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id,role_code) VALUES (:id,'ADMIN')"), {"id": seed["hr"]})
    assert client.get(f"/v1/positions/{uid()}", headers=headers(seed["hr"])).status_code == 404


def test_latest_ranking_excludes_candidates_outside_screening_and_old_rubrics(client, seed):
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status='APPROVED' WHERE criteria_version_id=:id"), {"id": seed["cv"]})
        ranking = uid()
        conn.execute(text("INSERT INTO app_private.ranking_runs(ranking_run_id,position_id,criteria_version_id,status) VALUES (:id,:pos,:cv,'COMPLETED')"),
                     {"id": ranking, "pos": seed["pos"], "cv": seed["cv"]})
        conn.execute(text("INSERT INTO app_private.ranking_items(ranking_run_id,position_id,application_id,rank_number,ranking_status,evidence_coverage) VALUES (:run,:pos,:app,1,'MEETS_MANDATORY',1)"),
                     {"run": ranking, "pos": seed["pos"], "app": seed["app"]})
    endpoint = f"/v1/assessments/ranking/latest/{seed['pos']}"
    assert len(client.get(endpoint, headers=headers(seed["hr"])).json()) == 1
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.applications SET application_status='INTERVIEW' WHERE application_id=:id"), {"id": seed["app"]})
    assert client.get(endpoint, headers=headers(seed["hr"])).json() == []
    assert len(client.get(f"/v1/applications?position_id={seed['pos']}", headers=headers(seed["hr"])).json()) == 1
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.applications SET application_status='NEW' WHERE application_id=:id"), {"id": seed["app"]})
        conn.execute(text("INSERT INTO app_private.criteria_versions(position_id,jd_version_id,version_number,status) VALUES (:pos,:jd,2,'APPROVED')"), {"pos": seed["pos"], "jd": seed["jd"]})
    assert client.get(endpoint, headers=headers(seed["hr"])).json() == []
