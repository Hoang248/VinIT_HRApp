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
        conn.execute(text("TRUNCATE app_private.departments CASCADE"))
        conn.execute(text("UPDATE app_private.ai_configuration_versions SET status='DISABLED' WHERE status='ACTIVE'"))
        for key in ("hr", "hm", "other", "hr2"):
            conn.execute(text("INSERT INTO auth.users(id) VALUES (:id)"), {"id": ids[key]})
            conn.execute(text("INSERT INTO app_private.user_profiles(user_id, display_name) VALUES (:id, :name)"), {"id": ids[key], "name": key.upper()})
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id, role_code) VALUES (:id, 'HR_RECRUITER')"), {"id": ids["hr"]})
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id, role_code) VALUES (:id, 'HIRING_MANAGER')"), {"id": ids["hm"]})
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


def create_test_department():
    with engine.begin() as conn:
        return str(conn.execute(text("""
            INSERT INTO app_private.departments (name, code_format)
            VALUES ('Phòng Công nghệ thông tin', 'REQ-IT-{SEQ:000}')
            RETURNING department_id
        """)).scalar_one())


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



def test_dual_approval_requires_distinct_accounts_even_with_both_roles(client, seed):
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO app_private.position_assignments
            (position_id, user_id, position_role) VALUES (:position, :user, 'HIRING_MANAGER')"""),
            {"position": seed["pos"], "user": seed["hr"]})
    url = f"/v1/criteria/{seed['cv']}/approve"
    assert client.post(url, headers=headers(seed["hr"]), json={"action": "APPROVE"}).status_code == 200
    self_review = client.post(url, headers=headers(seed["hr"]), json={"action": "APPROVE"})
    assert self_review.status_code == 409
    with engine.connect() as conn:
        row = conn.execute(text("""SELECT status, approved_by_hr, approved_by_hm
            FROM app_private.criteria_versions WHERE criteria_version_id = :id"""), {"id": seed["cv"]}).mappings().one()
        events = conn.execute(text("SELECT count(*) FROM app_private.criteria_approval_events WHERE criteria_version_id = :id"), {"id": seed["cv"]}).scalar_one()
    assert row["status"] == "PENDING_HM_APPROVAL" and row["approved_by_hm"] is None and events == 1
    final = client.post(url, headers=headers(seed["hm"]), json={"action": "APPROVE"})
    assert final.status_code == 200 and final.json()["status"] == "APPROVED"

def test_status_shortlist_permissions_feedback_and_revocation(client, seed):
    base = f"/v1/applications/{seed['app']}"
    change = lambda user, status, reason=None: client.patch(base + "/status", headers=headers(seed[user]), json={"new_status": status, "reason": reason})
    assert change("hm", "IN_REVIEW").status_code == 403
    assert change("hr", "SHORTLIST").status_code == 400
    assert change("hr", "REJECTED_SCREENING").status_code == 400
    assert change("hr", "IN_REVIEW").status_code == 200
    assert change("hr", "SHORTLIST").status_code == 200
    assert client.get(base, headers=headers(seed["hm"])).status_code == 403
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.application_identities SET email='private@example.test', phone='0123456789' WHERE application_id=:id"), {"id": seed["app"]})
        conn.execute(text("""INSERT INTO app_private.application_documents(application_id,bucket,storage_path,original_filename,mime_type,size_bytes,file_processing_status,processing_error)
            VALUES (:id,'cv-originals','synthetic','synthetic.pdf','application/pdf',100,'NEEDS_HR_REVIEW','Synthetic internal diagnostic')"""), {"id": seed["app"]})
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
    assert detail.json()["identity"]["email"] is None and detail.json()["identity"]["phone"] is None
    assert detail.json()["documents"] == [] and detail.json()["file_processing_status"] == "UNKNOWN"
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
    document = Document(); document.add_paragraph(
        "Developed Python systems for five years. test@example.com" if valid_quote
        else "Developed backend systems for five years. test@example.com")
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
        criterion_result = conn.execute(text("SELECT score, decision_source, evidence_chunk_id FROM app_private.criterion_assessment_results")).mappings().one()
        assert float(criterion_result["score"]) == 95 if valid_quote else criterion_result["score"] is None
        assert criterion_result["decision_source"] == ("RULE" if valid_quote else "LLM")
        assert (criterion_result["evidence_chunk_id"] is not None) if valid_quote else criterion_result["evidence_chunk_id"] is None
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
    department_id = create_test_department()
    payload = {"department_id": department_id, "title": "Engineer", "jd_content": "Job description", "hiring_manager_user_id": seed["hm"]}
    assert client.post("/v1/positions", headers=headers(seed["hm"]), json=payload).status_code == 403
    assert client.post("/v1/positions", headers=headers(seed["hr"]), json={**payload, "hiring_manager_user_id": None}).status_code == 400
    result = client.post("/v1/positions", headers=headers(seed["hr"]), json=payload)
    assert result.status_code == 201, result.text
    assert result.json()["position_code"] == "REQ-IT-001"
    assert result.json()["department_id"] == department_id
    created = result.json()["position_id"]
    second = client.post("/v1/positions", headers=headers(seed["hr"]), json={**payload, "title": "Engineer 2"})
    assert second.status_code == 201, second.text
    assert second.json()["position_code"] == "REQ-IT-002"
    with engine.connect() as conn:
        roles = conn.execute(text("SELECT position_role FROM app_private.position_assignments WHERE position_id=:id ORDER BY position_role"), {"id": created}).scalars().all()
        assert roles == ["HIRING_MANAGER", "HR_RECRUITER"]
        assert conn.execute(text("SELECT content_text FROM app_private.jd_versions WHERE position_id=:id"), {"id": created}).scalar_one() == "Job description"
        assert conn.execute(text("SELECT org_unit FROM app_private.positions WHERE position_id=:id"), {"id": created}).scalar_one() == "Phòng Công nghệ thông tin"


def test_departments_are_admin_managed_and_used_by_positions(client, seed):
    admin = uid()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO auth.users(id) VALUES (:id)"), {"id": admin})
        conn.execute(text("INSERT INTO app_private.user_profiles(user_id, display_name) VALUES (:id, 'ADMIN')"), {"id": admin})
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id, role_code) VALUES (:id, 'ADMIN')"), {"id": admin})
    payload = {"name": "Phòng Nhân sự", "code_format": "REQ-HR-{SEQ:000}", "is_active": True}
    assert client.post("/v1/departments", headers=headers(seed["hr"]), json=payload).status_code == 403
    created = client.post("/v1/departments", headers=headers(admin), json=payload)
    assert created.status_code == 201, created.text
    department_id = created.json()["department_id"]
    assert client.post("/v1/departments", headers=headers(admin), json=payload).status_code == 409
    listed = client.get("/v1/departments", headers=headers(seed["hr"]))
    assert listed.status_code == 200 and listed.json()[0]["department_id"] == department_id
    position = client.post("/v1/positions", headers=headers(seed["hr"]), json={
        "department_id": department_id, "title": "HR Specialist", "jd_content": "Job description",
        "hiring_manager_user_id": seed["hm"],
    })
    assert position.status_code == 201, position.text
    assert position.json()["position_code"] == "REQ-HR-001"
    assert client.delete(f"/v1/departments/{department_id}", headers=headers(admin)).status_code == 409
    updated = client.patch(f"/v1/departments/{department_id}", headers=headers(admin), json={"is_active": False})
    assert updated.status_code == 200 and updated.json()["is_active"] is False
    assert client.get("/v1/departments", headers=headers(seed["hr"])).json() == []


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


def test_admin_ai_config_is_runtime_backed_allowlisted_and_stores_only_encrypted_compatible_secrets(client, seed, monkeypatch):
    from cryptography.fernet import Fernet
    from app.core.config import settings
    monkeypatch.setattr(settings, "LLM_API_BASE", "http://127.0.0.1:11434/v1")
    monkeypatch.setattr(settings, "LLM_ALLOWED_API_BASES", ["http://127.0.0.1:11435/v1"])
    monkeypatch.setattr(settings, "LLM_ALLOWED_MODELS", ["approved-model"])
    monkeypatch.setattr(settings, "ALLOW_EXTERNAL_API", False)
    monkeypatch.setattr(settings, "AI_CONFIG_ENCRYPTION_KEY", Fernet.generate_key().decode())
    assert client.get("/v1/admin/ai/active-config", headers=headers(seed["hr"])).status_code == 403
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id,role_code) VALUES (:id,'ADMIN')"), {"id": seed["other"]})
    admin = headers(seed["other"])
    response = client.get("/v1/admin/ai/active-config", headers=admin)
    assert response.status_code == 200 and response.json()["source"] == "environment"
    assert "api_key" not in response.json()["config"]
    payload = {"provider": "local", "model_name": "approved-model", "api_base": "http://127.0.0.1:11435/v1", "temperature_default": .3}
    assert client.post("/v1/admin/ai/config", headers=admin, json={**payload, "api_key": "must-not-be-stored-here"}).status_code == 400
    assert client.post("/v1/admin/ai/config", headers=admin, json={**payload, "unexpected": "value"}).status_code == 422
    assert client.post("/v1/admin/ai/config", headers=admin, json={**payload, "api_base": "http://169.254.169.254/v1"}).status_code == 400
    assert client.post("/v1/admin/ai/config", headers=admin, json={**payload, "api_base": "https://user:password@example.test/v1"}).status_code == 400
    assert client.post("/v1/admin/ai/config", headers=admin, json={**payload, "model_name": "unapproved"}).status_code == 400
    created = client.post("/v1/admin/ai/config", headers=admin, json=payload)
    assert created.status_code == 201, created.text
    config_id = created.json()["config_id"]
    assert client.post(f"/v1/admin/ai/config/{config_id}/enable", headers=admin).status_code == 200
    active = client.get("/v1/admin/ai/active-config", headers=admin).json()
    assert active["source"] == "database" and active["allowed_by_this_process"]
    assert active["config"]["config_id"] == config_id and active["config"]["model_name"] == "approved-model"
    compatible_payload = {"provider": "compatible", "provider_name": "Synthetic Compatible",
                          "model_name": "vendor/custom-model", "api_base": "http://127.0.0.1:11435/v1",
                          "api_key": "provider-key-1234567890", "temperature_default": .2}
    compatible = client.post("/v1/admin/ai/config", headers=admin, json=compatible_payload)
    assert compatible.status_code == 201, compatible.text
    compatible_body = compatible.json()
    compatible_id = compatible_body["config_id"]
    assert compatible_body["provider_name"] == "Synthetic Compatible"
    assert compatible_body["api_key_configured"] is True and compatible_body["api_key_hint"].endswith("7890")
    assert "api_key" not in compatible_body and "api_key_ciphertext" not in compatible_body
    listed = client.get("/v1/admin/ai/config", headers=admin).json()
    listed_compatible = next(item for item in listed if item["config_id"] == compatible_id)
    assert "api_key" not in listed_compatible and "api_key_ciphertext" not in listed_compatible
    assert listed_compatible["api_key_configured"] is True
    assert client.post(f"/v1/admin/ai/config/{compatible_id}/enable", headers=admin).status_code == 200
    active = client.get("/v1/admin/ai/active-config", headers=admin).json()
    assert active["config"]["config_id"] == compatible_id
    assert active["config"]["provider_name"] == "Synthetic Compatible"
    assert active["config"]["model_name"] == "vendor/custom-model"
    assert active["config"]["api_key_configured"] is True
    assert "api_key" not in active["config"] and "api_key_ciphertext" not in active["config"]
    with engine.connect() as conn:
        stored = conn.execute(text("SELECT provider_name, api_key_ciphertext FROM app_private.ai_configuration_versions WHERE config_id=:id"), {"id": compatible_id}).mappings().one()
    assert stored["provider_name"] == "Synthetic Compatible"
    assert stored["api_key_ciphertext"] and "provider-key-1234567890" not in stored["api_key_ciphertext"]
    from app.api import admin as admin_module
    seen_runtime = {}
    async def fake_connection_test(runtime):
        seen_runtime.update(runtime)
        return {"ok": True, "status_code": 200, "latency_ms": 3,
                "provider_name": runtime.get("provider_name"), "model": runtime.get("model_name"),
                "provider_returned_model": "vendor/custom-model",
                "message": "Kết nối thành công tới nhà cung cấp."}
    monkeypatch.setattr(admin_module.llm_client, "test_provider_connection", fake_connection_test)
    tested = client.post("/v1/admin/ai/test-connection", headers=admin, json=compatible_payload)
    assert tested.status_code == 200, tested.text
    assert tested.json()["ok"] is True and tested.json()["provider_returned_model"] == "vendor/custom-model"
    assert seen_runtime["provider_name"] == "Synthetic Compatible"
    assert seen_runtime["api_key"] == "provider-key-1234567890"
    assert "provider-key-1234567890" not in tested.text
    assert client.post("/v1/admin/ai/test-connection", headers=headers(seed["hr"]), json=compatible_payload).status_code == 403
    with engine.begin() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.audit_events WHERE object_id=:id AND object_type='AI_CONFIG'"), {"id": config_id}).scalar_one() == 2
        conn.execute(text("UPDATE app_private.user_role_assignments SET revoked_at=NOW() WHERE user_id=:id AND role_code='ADMIN'"), {"id": seed["other"]})
    assert client.get("/v1/admin/ai/active-config", headers=admin).status_code == 403

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
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.criterion_assessment_results WHERE decision_source='RULE'")).scalar_one() == 2
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
        document, profile, assessment = uid(), uid(), uid()
        conn.execute(text("""INSERT INTO app_private.application_documents(document_id,application_id,bucket,storage_path,original_filename,mime_type,size_bytes,file_processing_status)
            VALUES (:doc,:app,'cv-originals','synthetic','synthetic.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document',100,'COMPLETED')"""), {'doc': document, 'app': seed['app']})
        conn.execute(text("INSERT INTO app_private.profile_versions(profile_version_id,application_id,source_document_id,version_number,status) VALUES (:id,:app,:doc,1,'COMPLETED')"), {'id': profile, 'app': seed['app'], 'doc': document})
        conn.execute(text("""INSERT INTO app_private.assessment_runs(assessment_id,position_id,application_id,jd_version_id,criteria_version_id,profile_version_id,status,matching_status,evidence_coverage)
            VALUES (:id,:pos,:app,:jd,:cv,:profile,'COMPLETED','MEETS_MANDATORY',1)"""), {'id': assessment, 'pos': seed['pos'], 'app': seed['app'], 'jd': seed['jd'], 'cv': seed['cv'], 'profile': profile})
        conn.execute(text("INSERT INTO app_private.ranking_items(ranking_run_id,position_id,application_id,assessment_id,rank_number,ranking_status,evidence_coverage) VALUES (:run,:pos,:app,:assessment,1,'MEETS_MANDATORY',1)"),
                     {"run": ranking, "pos": seed["pos"], "app": seed["app"], "assessment": assessment})
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


def test_live_worker_advisory_lock_prevents_concurrent_takeover(seed):
    import threading
    from app.workers.processor import ProcessingWorker
    op = uid()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.operations(operation_id,position_id,capability,requested_by,status) VALUES (:id,:pos,'RANKING',:user,'PENDING')"),
                     {"id": op, "pos": seed["pos"], "user": seed["hr"]})
    started, release = threading.Event(), threading.Event()
    first, second = ProcessingWorker(), ProcessingWorker()
    calls = []
    def hold(operation_id, db, **kwargs):
        calls.append("first")
        started.set()
        assert release.wait(10)
    first._generate_ranking = hold
    second._generate_ranking = lambda *args, **kwargs: calls.append("second")
    thread = threading.Thread(target=first._process_pending_operations)
    thread.start()
    try:
        assert started.wait(10)
        second._process_pending_operations()
        assert calls == ["first"]
        with engine.connect() as conn:
            row = conn.execute(text("SELECT status, attempt_count FROM app_private.operations WHERE operation_id=:id"), {"id": op}).mappings().one()
            assert row["status"] == "PROCESSING" and row["attempt_count"] == 1
    finally:
        release.set(); thread.join(10)
    assert not thread.is_alive()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM app_private.operations WHERE operation_id=:id"), {"id": op}).scalar_one() == "COMPLETED"


def test_process_crash_releases_lock_and_another_worker_recovers(seed):
    import subprocess, sys
    from pathlib import Path
    from app.workers.processor import ProcessingWorker
    op = uid()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.operations(operation_id,position_id,capability,requested_by,status) VALUES (:id,:pos,'RANKING',:user,'PENDING')"),
                     {"id": op, "pos": seed["pos"], "user": seed["hr"]})
    script = """
import os
from app.workers.processor import ProcessingWorker
worker = ProcessingWorker()
def crash(*args, **kwargs):
    os._exit(71)
worker._generate_ranking = crash
worker._process_pending_operations()
"""
    env = {**os.environ, "DATABASE_URL": os.environ["TEST_DATABASE_URL"], "APP_ENV": "testing",
           "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    child = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=15)
    assert child.returncode == 71, child.stderr
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM app_private.operations WHERE operation_id=:id"), {"id": op}).scalar_one() == "PROCESSING"
    recovered = []
    worker = ProcessingWorker()
    worker._generate_ranking = lambda operation_id, db, **kwargs: recovered.append(str(operation_id))
    worker._process_pending_operations()
    assert recovered == [op]
    with engine.connect() as conn:
        row = conn.execute(text("SELECT status, attempt_count, recovery_count, heartbeat_at FROM app_private.operations WHERE operation_id=:id"), {"id": op}).mappings().one()
    assert row["status"] == "COMPLETED" and row["attempt_count"] == 2 and row["recovery_count"] == 1 and row["heartbeat_at"]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.operation_recovery_events WHERE operation_id=:id"), {"id": op}).scalar_one() == 1


def test_superseded_worker_cannot_commit_after_database_connection_loss(seed):
    import threading
    from app.workers.processor import ProcessingWorker
    op = uid()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.operations(operation_id,position_id,capability,requested_by,status) VALUES (:id,:pos,'RANKING',:user,'PENDING')"),
                     {"id": op, "pos": seed["pos"], "user": seed["hr"]})
    old_ready, old_resume, new_ready, new_resume = (threading.Event() for _ in range(4))
    pids, errors = [], []
    first, second = ProcessingWorker(), ProcessingWorker()
    def stale(operation_id, db, **kwargs):
        pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
        old_ready.set(); assert old_resume.wait(10)
        db.execute(text("UPDATE app_private.operations SET error_message='STALE WRITE' WHERE operation_id=:id"), {"id": op})
        db.commit()
    def recovered(operation_id, db, **kwargs):
        new_ready.set(); assert new_resume.wait(10)
    first._generate_ranking, second._generate_ranking = stale, recovered
    def invoke(worker):
        try: worker._process_pending_operations()
        except Exception as exc: errors.append(exc)
    old_thread = threading.Thread(target=invoke, args=(first,)); old_thread.start()
    new_thread = None
    try:
        assert old_ready.wait(10)
        with engine.begin() as conn:
            assert conn.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pids[0]}).scalar_one()
        new_thread = threading.Thread(target=invoke, args=(second,)); new_thread.start()
        assert new_ready.wait(10)
        old_resume.set(); old_thread.join(10)
        assert not old_thread.is_alive() and not errors
        with engine.connect() as conn:
            row = conn.execute(text("SELECT status,error_message,recovery_count FROM app_private.operations WHERE operation_id=:id"), {"id": op}).mappings().one()
            assert row["status"] == "PROCESSING" and row["error_message"] is None and row["recovery_count"] == 1
    finally:
        old_resume.set(); new_resume.set(); old_thread.join(10)
        if new_thread: new_thread.join(10)
    assert not errors
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM app_private.operations WHERE operation_id=:id"), {"id": op}).scalar_one() == "COMPLETED"


def test_recovery_resumes_processing_document_and_reconciles_batch(client, seed, tmp_path, monkeypatch):
    from app.core.config import settings
    from app.workers.processor import ProcessingWorker, llm_client
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    async def extract(cv_text, candidate_identifier):
        return {"candidate_identifier": candidate_identifier, "total_years_experience": 2,
                "education": [], "work_history": [], "skills": ["Python"], "certifications": [],
                "languages": [{"name": "English", "level": "Professional"}],
                "projects": [{"name": "Synthetic Search", "description": "Python services"}]}
    async def match(cv_text, candidate_profile, rubric, candidate_identifier, rubric_version):
        return {"findings": [{"criterion_id": rubric[0]["criterion_id"], "outcome": "MATCH", "confidence": .9,
                              "confidence_band": "HIGH", "reasoning": "Evidence provided",
                              "evidence": {"verbatim_quote": "Built Python services for two years", "page_number": None}}]}
    monkeypatch.setattr(llm_client, "extract_candidate_profile", extract)
    monkeypatch.setattr(llm_client, "match_criterion_evidence", match)
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status='APPROVED' WHERE criteria_version_id=:id"), {"id": seed["cv"]})
    doc = Document(); doc.add_paragraph("Built Python services for two years and developed several reliable applications.")
    content = io.BytesIO(); doc.save(content)
    response = client.post(f"/v1/applications/upload-batch/{seed['pos']}", headers=headers(seed["hr"]),
                           files=[("files", ("synthetic.docx", content.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))])
    assert response.status_code == 202, response.text
    op = response.json()["operation_id"]
    worker = ProcessingWorker(); original = worker._read_file_content
    worker._read_file_content = lambda doc: (_ for _ in ()).throw(SystemExit("simulated hard interruption"))
    with pytest.raises(SystemExit):
        worker._process_pending_operations()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT file_processing_status FROM app_private.application_documents")).scalar_one() == "PROCESSING"
    worker._read_file_content = original
    worker._process_pending_operations()
    with engine.connect() as conn:
        row = conn.execute(text("SELECT status,attempt_count,recovery_count FROM app_private.operations WHERE operation_id=:id"), {"id": op}).mappings().one()
        batch = conn.execute(text("SELECT processed_files,failed_files FROM app_private.cv_batches WHERE operation_id=:id"), {"id": op}).mappings().one()
        assert row["status"] == "COMPLETED" and row["attempt_count"] == 2 and row["recovery_count"] == 1
        assert batch["processed_files"] == 1 and batch["failed_files"] == 0
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.assessment_runs WHERE operation_id=:id AND status='COMPLETED'"), {"id": op}).scalar_one() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.ranking_runs WHERE operation_id=:id"), {"id": op}).scalar_one() == 1
        assert set(conn.execute(text("SELECT fact_type FROM app_private.profile_facts WHERE fact_type IN ('LANGUAGE','PROJECT')")).scalars()) == {'LANGUAGE', 'PROJECT'}


def test_worker_health_is_admin_only_and_reports_stale_work(client, seed):
    op = uid()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id,role_code) VALUES (:id,'ADMIN')"), {"id": seed["other"]})
        conn.execute(text("""INSERT INTO app_private.operations(operation_id,position_id,capability,requested_by,status,attempt_started_at,heartbeat_at)
            VALUES (:id,:pos,'RANKING',:hr,'PROCESSING',NOW()-INTERVAL '31 minutes',NOW()-INTERVAL '3 minutes')"""),
                     {"id": op, "pos": seed["pos"], "hr": seed["hr"]})
    assert client.get('/v1/admin/worker/health', headers=headers(seed['hr'])).status_code == 403
    response = client.get('/v1/admin/worker/health', headers=headers(seed['other']))
    assert response.status_code == 200, response.text
    assert response.json()['processing'] == 1 and response.json()['stale_heartbeat'] == 1 and response.json()['long_running'] == 1
    with engine.begin() as conn:
        # Counts reflect individual events, not the cumulative count on an
        # operation or the timestamp of its most recent attempt.
        conn.execute(text("UPDATE app_private.operations SET recovery_count=9 WHERE operation_id=:id"), {"id": op})
        conn.execute(text("""INSERT INTO app_private.operation_recovery_events(operation_id,recovered_at)
            VALUES (:id,NOW()-INTERVAL '25 hours'), (:id,NOW()-INTERVAL '2 hours'), (:id,NOW()-INTERVAL '1 hour')"""), {"id": op})
    response = client.get('/v1/admin/worker/health', headers=headers(seed['other']))
    assert response.status_code == 200 and response.json()['recoveries_24h'] == 2


def test_ai_runtime_changes_actual_request_and_worker_recovery_keeps_pinned_config(client, seed, monkeypatch):
    import asyncio
    from app.core.config import settings
    from app.services.llm_client import LLMClient
    from app.services.ai_config import runtime_context
    from app.workers.processor import ProcessingWorker
    monkeypatch.setattr(settings, 'LLM_API_BASE', 'http://127.0.0.1:11434/v1')
    monkeypatch.setattr(settings, 'LLM_ALLOWED_API_BASES', ['http://127.0.0.1:11435/v1'])
    monkeypatch.setattr(settings, 'LLM_ALLOWED_MODELS', ['model-a', 'model-b'])
    monkeypatch.setattr(settings, 'ALLOW_EXTERNAL_API', False)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id,role_code) VALUES (:id,'ADMIN')"), {'id': seed['other']})
    admin = headers(seed['other'])
    def create_and_enable(model, base, temperature):
        res = client.post('/v1/admin/ai/config', headers=admin, json={'provider': 'local', 'model_name': model, 'api_base': base, 'temperature_default': temperature})
        assert res.status_code == 201, res.text
        cid = res.json()['config_id']
        assert client.post(f'/v1/admin/ai/config/{cid}/enable', headers=admin).status_code == 200
        return cid
    first = create_and_enable('model-a', settings.LLM_API_BASE, .2)
    captured = []
    class Reply:
        def raise_for_status(self): pass
        def json(self): return {'choices': [{'message': {'content': '{"ok":true}'}}]}
    class Transport:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs): captured.append((url, kwargs['json'])); return Reply()
    monkeypatch.setattr('app.services.llm_client.httpx.AsyncClient', Transport)
    assert asyncio.run(LLMClient()._call_llm('system', 'synthetic')) == {'ok': True}
    assert captured[-1][0] == 'http://127.0.0.1:11434/v1/chat/completions'
    assert captured[-1][1]['model'] == 'model-a' and captured[-1][1]['temperature'] == .2
    op = uid()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.operations(operation_id,position_id,capability,requested_by,status) VALUES (:id,:pos,'RANKING',:user,'PENDING')"),
                     {'id': op, 'pos': seed['pos'], 'user': seed['hr']})
    worker = ProcessingWorker(); seen = []
    def die(operation_id, db, **kwargs):
        seen.append(runtime_context.get()['config_id'])
        raise SystemExit('simulated interruption')
    worker._generate_ranking = die
    with pytest.raises(SystemExit): worker._process_pending_operations()
    second = create_and_enable('model-b', 'http://127.0.0.1:11435/v1', .4)
    assert asyncio.run(LLMClient()._call_llm('system', 'synthetic')) == {'ok': True}
    assert captured[-1][1]['model'] == 'model-b' and captured[-1][1]['temperature'] == .4
    worker._generate_ranking = lambda operation_id, db, **kwargs: seen.append(runtime_context.get()['config_id'])
    worker._process_pending_operations()
    assert seen == [first, first] and second != first
    with engine.connect() as conn:
        row = conn.execute(text('SELECT ai_config_id, ai_config_snapshot, recovery_count FROM app_private.operations WHERE operation_id=:id'), {'id': op}).mappings().one()
    assert str(row['ai_config_id']) == first and row['ai_config_snapshot']['model_name'] == 'model-a' and row['recovery_count'] == 1


def test_concurrent_ai_activation_leaves_exactly_one_active(client, seed, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from app.core.config import settings
    monkeypatch.setattr(settings, 'LLM_API_BASE', 'http://127.0.0.1:11434/v1')
    monkeypatch.setattr(settings, 'LLM_ALLOWED_MODELS', ['model-a', 'model-b'])
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id,role_code) VALUES (:id,'ADMIN')"), {'id': seed['other']})
    admin = headers(seed['other'])
    ids = []
    for model in ('model-a', 'model-b'):
        response = client.post('/v1/admin/ai/config', headers=admin, json={'provider': 'local', 'model_name': model, 'api_base': settings.LLM_API_BASE})
        assert response.status_code == 201, response.text
        ids.append(response.json()['config_id'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda cid: client.post(f'/v1/admin/ai/config/{cid}/enable', headers=admin), ids))
    assert [result.status_code for result in results] == [200, 200]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.ai_configuration_versions WHERE status='ACTIVE'")).scalar_one() == 1


def test_jd_versioning_is_immutable_scoped_and_invalidates_stale_approval(client, seed):
    base = f"/v1/positions/{seed['pos']}/jd-versions"
    body = {'content_text': 'Synthetic updated role description with Python experience.', 'language_code': 'en', 'expected_jd_version_id': seed['jd']}
    assert client.get(base, headers=headers(seed['other'])).status_code == 403
    assert client.get(base, headers=headers(seed['hm'])).status_code == 200
    assert client.post(base, headers=headers(seed['hm']), json=body).status_code == 403
    assert client.post(f"/v1/criteria/{seed['cv']}/approve", headers=headers(seed['hr']), json={'action': 'APPROVE'}).status_code == 200
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.operations(position_id,capability,status,requested_by) VALUES (:pos,'RANKING','PENDING',:hr)"), {'pos': seed['pos'], 'hr': seed['hr']})
    assert client.post(base, headers=headers(seed['hr']), json=body).status_code == 409
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.operations SET status='COMPLETED' WHERE position_id=:pos"), {'pos': seed['pos']})
    created = client.post(base, headers=headers(seed['hr']), json=body)
    assert created.status_code == 201, created.text
    assert created.json()['version_number'] == 2
    assert client.post(base, headers=headers(seed['hr']), json=body).status_code == 409
    assert client.post(f"/v1/criteria/{seed['cv']}/approve", headers=headers(seed['hm']), json={'action': 'APPROVE'}).status_code == 409
    versions = client.get(base, headers=headers(seed['hr'])).json()
    assert [item['version_number'] for item in versions] == [2, 1] and versions[1]['content_text'] == 'JD'
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status='APPROVED' WHERE criteria_version_id=:id"), {'id': seed['cv']})
    assert client.get(f"/v1/criteria/position/{seed['pos']}/approved", headers=headers(seed['hr'])).json() is None
    assert client.get(f"/v1/positions/{seed['pos']}", headers=headers(seed['hr'])).json()['criteria_approved'] is False
    assert client.post(f"/v1/assessments/run/{seed['pos']}", headers=headers(seed['hr'])).status_code == 400


def test_jd_changed_during_ai_generation_does_not_save_stale_draft(client, seed, monkeypatch):
    from app.api.criteria import llm_client
    async def generate(**kwargs):
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO app_private.jd_versions(position_id,version_number,content_text,created_by) VALUES (:pos,2,'new synthetic JD',:hr)"), {'pos': seed['pos'], 'hr': seed['hr']})
        return {'criteria': [{'name': 'Python', 'description': 'Python skills', 'category': 'MUST_HAVE', 'weight': 100, 'expected_evidence_keywords': []}]}
    monkeypatch.setattr(llm_client, 'extract_criteria_from_jd', generate)
    response = client.post(f"/v1/criteria/generate/{seed['pos']}", headers=headers(seed['hr']))
    assert response.status_code == 409
    with engine.connect() as conn:
        assert conn.execute(text('SELECT COUNT(*) FROM app_private.criteria_versions WHERE position_id=:pos'), {'pos': seed['pos']}).scalar_one() == 1


def test_hr_private_notes_do_not_leak_to_hm_or_admin_without_hr_role(client, seed):
    base = f"/v1/applications/{seed['app']}"
    for state in ('IN_REVIEW', 'SHORTLIST'):
        assert client.patch(base + '/status', headers=headers(seed['hr']), json={'new_status': state}).status_code == 200
    share = client.post('/v1/shortlist/share', headers=headers(seed['hr']), json={
        'position_id': seed['pos'], 'shared_with_user_id': seed['hm'], 'application_ids': [seed['app']], 'allow_cv_view': True})
    assert share.status_code == 201
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id,role_code) VALUES (:id,'ADMIN')"), {'id': seed['other']})
    assert client.get(base, headers=headers(seed['hr'])).json()['can_manage_hr_notes'] is True
    assert client.get(base, headers=headers(seed['hm'])).json()['can_manage_hr_notes'] is False
    assert client.get(base, headers=headers(seed['other'])).json()['can_manage_hr_notes'] is False
    note = client.post(base + '/private-notes', headers=headers(seed['hr']), json={'content': 'Synthetic HR-only internal note'})
    assert note.status_code == 201, note.text
    assert client.get(base + '/private-notes', headers=headers(seed['hr'])).json()[0]['content'] == 'Synthetic HR-only internal note'
    for forbidden in ('hm', 'other', 'hr2'):
        assert client.get(base + '/private-notes', headers=headers(seed[forbidden])).status_code == 403
        assert client.post(base + '/private-notes', headers=headers(seed[forbidden]), json={'content': 'forbidden'}).status_code == 403
    assert 'Synthetic HR-only internal note' not in str(client.get(f"/v1/shortlist/{share.json()['share_id']}", headers=headers(seed['hm'])).json())
    assert 'Synthetic HR-only internal note' not in str(client.get(base, headers=headers(seed['hm'])).json())
    with engine.begin() as conn:
        assert not conn.execute(text("SELECT has_table_privilege('authenticated', 'app_private.application_private_notes', 'SELECT')")).scalar_one()
        assert conn.execute(text("SELECT to_regclass('public.application_private_notes') IS NULL")).scalar_one()
        conn.execute(text("UPDATE app_private.position_assignments SET revoked_at=NOW() WHERE position_id=:pos AND user_id=:id AND position_role='HR_RECRUITER'"), {'pos': seed['pos'], 'id': seed['hr']})
    assert client.get(base + '/private-notes', headers=headers(seed['hr'])).status_code == 403


def test_profile_versions_reject_races_and_hide_stale_results_until_reassessment(client, seed, tmp_path, monkeypatch):
    from app.core.config import settings
    from app.workers.processor import ProcessingWorker, llm_client
    monkeypatch.setattr(settings, 'LOCAL_STORAGE_PATH', str(tmp_path))
    async def extract(cv_text, candidate_identifier):
        return {'candidate_identifier': candidate_identifier, 'total_years_experience': 2,
                'education': [], 'work_history': [], 'skills': ['Python'], 'certifications': []}
    captured_profiles = []
    async def match(cv_text, candidate_profile, rubric, candidate_identifier, rubric_version):
        captured_profiles.append(candidate_profile)
        return {'findings': [{'criterion_id': rubric[0]['criterion_id'], 'outcome': 'MATCH', 'confidence': .9,
                              'confidence_band': 'HIGH', 'reasoning': 'Evidence provided',
                              'evidence': {'verbatim_quote': 'Built Python services for two years', 'page_number': None}}]}
    monkeypatch.setattr(llm_client, 'extract_candidate_profile', extract)
    monkeypatch.setattr(llm_client, 'match_criterion_evidence', match)
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status='APPROVED' WHERE criteria_version_id=:id"), {'id': seed['cv']})
    doc = Document(); doc.add_paragraph('Built Python services for two years and developed several reliable applications.')
    content = io.BytesIO(); doc.save(content)
    uploaded = client.post(f"/v1/applications/upload-batch/{seed['pos']}", headers=headers(seed['hr']),
                           files=[('files', ('synthetic.docx', content.getvalue(), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))])
    assert uploaded.status_code == 202
    op = uploaded.json()['operation_id']; worker = ProcessingWorker(); worker._process_pending_operations()
    with engine.connect() as conn:
        app_id = str(conn.execute(text('SELECT application_id FROM app_private.cv_batch_items WHERE batch_id=(SELECT batch_id FROM app_private.cv_batches WHERE operation_id=:op)'), {'op': op}).scalar_one())
    base = f'/v1/applications/{app_id}'
    old_assessment = client.get(base, headers=headers(seed['hr'])).json()['latest_assessment']['assessment_id']
    for state in ('IN_REVIEW', 'SHORTLIST'):
        assert client.patch(base + '/status', headers=headers(seed['hr']), json={'new_status': state}).status_code == 200
    share = client.post('/v1/shortlist/share', headers=headers(seed['hr']), json={'position_id': seed['pos'],
        'shared_with_user_id': seed['hm'], 'application_ids': [app_id], 'allow_cv_view': True}).json()['share_id']
    before = client.get(base + '/profile', headers=headers(seed['hr'])).json()
    assert before['version_number'] == 1
    note_text = 'Synthetic private note never in model profile'
    assert client.post(base + '/private-notes', headers=headers(seed['hr']), json={'content': note_text}).status_code == 201
    body = {'expected_profile_version_id': before['profile_version_id'], 'display_name': 'Synthetic Candidate',
            'email': 'person@example.test', 'phone': None,
            'facts': [{'fact_type': 'SKILL', 'fact_value': {'name': 'Python'}, 'source_page_number': None},
                      {'fact_type': 'PROJECT', 'fact_value': {'description': 'Built Python services'}}]}
    assert client.put(base + '/profile', headers=headers(seed['hm']), json=body).status_code == 403
    changed = client.put(base + '/profile', headers=headers(seed['hr']), json=body)
    assert changed.status_code == 200, changed.text
    assert changed.json()['version_number'] == 2 and changed.json()['identity']['display_name'] == 'Synthetic Candidate'
    assert client.put(base + '/profile', headers=headers(seed['hr']), json=body).status_code == 409
    assert client.get(base, headers=headers(seed['hr'])).json()['latest_assessment'] is None
    assert client.get(f"/v1/assessments/ranking/latest/{seed['pos']}", headers=headers(seed['hr'])).json() == []
    shared = client.get(f'/v1/shortlist/{share}', headers=headers(seed['hm'])).json()
    assert shared['applications'][0]['matching_status'] is None
    assert client.get(f"/v1/dashboard/position/{seed['pos']}", headers=headers(seed['hr'])).json()['assessments_completed'] == 0
    queued = client.post(f"/v1/assessments/run/{seed['pos']}", headers=headers(seed['hr']))
    assert queued.status_code == 202
    body['expected_profile_version_id'] = changed.json()['profile_version_id']
    assert client.put(base + '/profile', headers=headers(seed['hr']), json=body).status_code == 409
    worker._process_pending_operations()
    latest = client.get(base, headers=headers(seed['hr'])).json()['latest_assessment']
    assert latest and latest['assessment_id'] != old_assessment
    assert client.get(f"/v1/assessments/ranking/latest/{seed['pos']}", headers=headers(seed['hr'])).json()[0]['application_id'] == app_id
    assert note_text not in str(captured_profiles)
    # An existing share is a historical snapshot, so HR must re-share it to
    # include the newly computed assessment rather than silently changing it.
    assert client.get(f'/v1/shortlist/{share}', headers=headers(seed['hm'])).json()['applications'][0]['matching_status'] is None
    assert client.get(base, headers=headers(seed['hm'])).json()['latest_assessment'] is None
    assert client.get(f"/v1/assessments/{latest['assessment_id']}", headers=headers(seed['hm'])).status_code == 403
    assert client.get(f"/v1/assessments/{old_assessment}", headers=headers(seed['hm'])).status_code == 403
    new_share = client.post('/v1/shortlist/share', headers=headers(seed['hr']), json={'position_id': seed['pos'],
        'shared_with_user_id': seed['hm'], 'application_ids': [app_id], 'allow_cv_view': False})
    assert new_share.status_code == 201
    hm_detail = client.get(base, headers=headers(seed['hm'])).json()
    assert hm_detail['latest_assessment']['assessment_id'] == latest['assessment_id']
    assert hm_detail['can_view_cv'] is True  # original active share still permits the CV
    assert hm_detail['can_view_assessment_evidence'] is False
    assert hm_detail['latest_assessment']['criterion_results'] == []  # new snapshot is summary-only
    assert client.get(f"/v1/assessments/{latest['assessment_id']}", headers=headers(seed['hm'])).status_code == 403
    cv_share = client.post('/v1/shortlist/share', headers=headers(seed['hr']), json={'position_id': seed['pos'],
        'shared_with_user_id': seed['hm'], 'application_ids': [app_id], 'allow_cv_view': True})
    assert cv_share.status_code == 201
    cv_detail = client.get(base, headers=headers(seed['hm'])).json()
    assert cv_detail['can_view_assessment_evidence'] is True and cv_detail['latest_assessment']['criterion_results']
    assert client.get(f"/v1/assessments/{latest['assessment_id']}", headers=headers(seed['hm'])).status_code == 200


def test_worker_scans_past_a_full_page_of_live_locks(seed):
    from app.workers.processor import ProcessingWorker
    with engine.begin() as conn:
        # Synthetic pre-existing jobs; the first 100 have live session locks.
        conn.execute(text("""INSERT INTO app_private.operations(position_id, capability, requested_by, status, created_at)
            SELECT :pos, 'RANKING', :user, 'PROCESSING', NOW() - INTERVAL '5 minutes' + n * INTERVAL '1 millisecond'
            FROM generate_series(1, 100) n"""), {"pos": seed["pos"], "user": seed["hr"]})
        pending = conn.execute(text("""INSERT INTO app_private.operations(position_id, capability, requested_by, status)
            VALUES (:pos, 'RANKING', :user, 'PENDING') RETURNING operation_id"""),
            {"pos": seed["pos"], "user": seed["hr"]}).scalar_one()
    locked = engine.connect()
    try:
        ids = locked.execute(text("SELECT operation_id FROM app_private.operations WHERE status='PROCESSING' ORDER BY created_at, operation_id")).scalars().all()
        for job_id in ids:
            locked.execute(text("SELECT pg_advisory_lock(hashtextextended(:id, 418630021))"), {"id": str(job_id)})
        locked.commit()
        worker = ProcessingWorker()
        done = []
        worker._generate_ranking = lambda job_id, db, **kwargs: done.append(str(job_id))
        worker._process_pending_operations()  # full page is held by another session
        assert done == []
        worker._process_pending_operations()  # continues after that page
        assert done == [str(pending)]
    finally:
        locked.execute(text("SELECT pg_advisory_unlock_all()")); locked.commit(); locked.close()


def test_ai_config_writes_recheck_active_admin_inside_transaction(client, seed, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, 'LLM_API_BASE', 'http://127.0.0.1:11434/v1')
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id,role_code) VALUES (:user,'ADMIN')"), {'user': seed['other']})
    body = {'provider': 'local', 'model_name': settings.LLM_MODEL_NAME, 'api_base': settings.LLM_API_BASE}
    created = client.post('/v1/admin/ai/config', headers=headers(seed['other']), json=body)
    assert created.status_code == 201
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.user_profiles SET account_status='INACTIVE' WHERE user_id=:user"), {'user': seed['other']})
    # The test identity override bypasses the normal auth dependency, so these
    # assertions specifically exercise the transactional write recheck.
    assert client.post('/v1/admin/ai/config', headers=headers(seed['other']), json=body).status_code == 403
    assert client.post(f"/v1/admin/ai/config/{created.json()['config_id']}/enable", headers=headers(seed['other'])).status_code == 403
