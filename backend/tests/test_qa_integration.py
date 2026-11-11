"""F2.04 QA sample inspection against real PostgreSQL with synthetic data only."""
import os

import pytest
from sqlalchemy import text

from app.db.database import SessionLocal, engine
from app.services import qa_sampling
from test_phase1_integration import client, headers, seed, uid  # noqa: F401  (fixtures)

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database")

# (coverage, MUST_HAVE outcome) for 12 synthetic applications in one batch.
SCENARIO = [(0.95, "MATCH")] * 8 + [(0.95, "NO_MATCH"), (0.65, "MATCH"), (0.80, "MATCH"), (0.55, "UNCLEAR")]


def _seed_batch(ids):
    """One approved rubric, one completed batch, 12 completed assessments; ids['other'] becomes HR_LEAD."""
    batch, apps, results = uid(), [], {}
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.criteria_versions SET status='APPROVED' WHERE criteria_version_id=:id"),
                     {"id": ids["cv"]})
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id, role_code) VALUES (:id, 'HR_LEAD')"),
                     {"id": ids["other"]})
        conn.execute(text("""INSERT INTO app_private.cv_batches(batch_id,position_id,uploaded_by,status,total_files,total_size_bytes)
            VALUES (:id,:pos,:hr,'COMPLETED',:n,100)"""), {"id": batch, "pos": ids["pos"], "hr": ids["hr"], "n": len(SCENARIO)})
        for index, (coverage, outcome) in enumerate(SCENARIO):
            app_id, document, profile, assessment, result = uid(), uid(), uid(), uid(), uid()
            conn.execute(text("INSERT INTO app_private.applications(application_id,position_id,created_by) VALUES (:id,:pos,:hr)"),
                         {"id": app_id, "pos": ids["pos"], "hr": ids["hr"]})
            conn.execute(text("INSERT INTO app_private.application_identities(application_id,display_name) VALUES (:id,:name)"),
                         {"id": app_id, "name": f"Synthetic {index}"})
            conn.execute(text("""INSERT INTO app_private.cv_batch_items(batch_id,original_filename,size_bytes,application_id)
                VALUES (:batch,'synthetic.docx',10,:app)"""), {"batch": batch, "app": app_id})
            conn.execute(text("""INSERT INTO app_private.application_documents(document_id,application_id,bucket,storage_path,original_filename,mime_type,size_bytes,file_processing_status)
                VALUES (:doc,:app,'cv-originals','synthetic','synthetic.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document',100,'COMPLETED')"""),
                         {"doc": document, "app": app_id})
            conn.execute(text("""INSERT INTO app_private.profile_versions(profile_version_id,application_id,source_document_id,version_number,status)
                VALUES (:id,:app,:doc,1,'COMPLETED')"""), {"id": profile, "app": app_id, "doc": document})
            conn.execute(text("""INSERT INTO app_private.assessment_runs(assessment_id,position_id,application_id,jd_version_id,criteria_version_id,profile_version_id,status,matching_status,evidence_coverage,completed_at)
                VALUES (:id,:pos,:app,:jd,:cv,:profile,'COMPLETED','MEETS_MANDATORY',:coverage,NOW())"""),
                         {"id": assessment, "pos": ids["pos"], "app": app_id, "jd": ids["jd"], "cv": ids["cv"],
                          "profile": profile, "coverage": coverage})
            conn.execute(text("""INSERT INTO app_private.criterion_assessment_results(result_id,assessment_id,criterion_id,outcome)
                VALUES (:id,:assessment,:criterion,:outcome)"""),
                         {"id": result, "assessment": assessment, "criterion": ids["criterion"], "outcome": outcome})
            conn.execute(text("""INSERT INTO app_private.evidence_items(criterion_result_id,source_document_id,verbatim_quote,page_number)
                VALUES (:result,:doc,'Python 3 projects',1)"""), {"result": result, "doc": document})
            apps.append(app_id)
            results[app_id] = result
    return batch, apps, results


def _auto_runs(ids):
    db = SessionLocal()
    try:
        runs = qa_sampling.create_auto_runs_for_position(db, position_id=ids["pos"], criteria_version_id=ids["cv"])
        db.commit()
        return runs
    finally:
        db.close()


def test_auto_sample_selects_random_and_risk_cases_once(seed):  # noqa: F811
    batch, apps, _ = _seed_batch(seed)
    runs = _auto_runs(seed)
    assert len(runs) == 1 and runs[0]["population_size"] == 12
    assert _auto_runs(seed) == []  # idempotent per batch and rubric version
    with engine.begin() as conn:
        items = conn.execute(text("""
            SELECT i.application_id, i.reasons, i.selection_sha256, r.sample_run_id
            FROM app_private.qa_sample_items i JOIN app_private.qa_sample_runs r USING (sample_run_id)
            WHERE r.batch_id = :batch
        """), {"batch": batch}).mappings().all()
        audit = conn.execute(text("SELECT COUNT(*) FROM app_private.audit_events WHERE action_type='CREATE_QA_SAMPLE'")).scalar_one()
    by_app = {str(row["application_id"]): list(row["reasons"]) for row in items}
    assert "SINGLE_MUST_HAVE_FAIL" in by_app[apps[8]]
    assert "COVERAGE_NEAR_THRESHOLD" in by_app[apps[9]]
    assert by_app.get(apps[10], ["RANDOM"]) == ["RANDOM"]  # 0.80 is outside the band
    assert by_app.get(apps[11], ["RANDOM"]) == ["RANDOM"]  # UNCLEAR is not a failure, 0.55 outside band
    assert sum("RANDOM" in reasons for reasons in by_app.values()) == 2  # ceil(10% of 12)
    run_id = str(items[0]["sample_run_id"])
    assert all(row["selection_sha256"] == qa_sampling.selection_sha256(run_id, str(row["application_id"])) for row in items)
    assert audit == 1


def test_qa_review_permissions_flags_and_summary(client, seed):  # noqa: F811
    batch, apps, results = _seed_batch(seed)
    _auto_runs(seed)
    lead, recruiter, hm, other_recruiter = seed["other"], seed["hr"], seed["hm"], seed["hr2"]

    queue = client.get(f"/v1/qa/queue?position_id={seed['pos']}", headers=headers(lead)).json()
    assert queue["can_review"] is True and queue["items"]
    recruiter_queue = client.get(f"/v1/qa/queue?position_id={seed['pos']}", headers=headers(recruiter)).json()
    assert recruiter_queue["can_review"] is False and len(recruiter_queue["items"]) == len(queue["items"])
    assert client.get(f"/v1/qa/queue?position_id={seed['pos']}", headers=headers(hm)).status_code == 403
    assert client.get("/v1/qa/queue", headers=headers(other_recruiter)).json()["items"] == []

    flagged = next(i for i in queue["items"] if str(i["application_id"]) == apps[8])
    item_id = flagged["sample_item_id"]
    detail = client.get(f"/v1/qa/items/{item_id}", headers=headers(recruiter)).json()
    assert detail["criterion_results"][0]["evidence"][0]["verbatim_quote"] == "Python 3 projects"
    assert detail["document"]["original_filename"] == "synthetic.docx"
    assert client.get(f"/v1/qa/items/{item_id}", headers=headers(other_recruiter)).status_code == 403

    body = {"flag_type": "MISSED_CONTENT", "criterion_result_id": results[apps[8]], "expected_outcome": "MATCH",
            "note": "CV có Python ở mục dự án"}
    assert client.post(f"/v1/qa/items/{item_id}/flags", json=body, headers=headers(recruiter)).status_code == 403
    assert client.post(f"/v1/qa/items/{item_id}/flags", json={**body, "criterion_result_id": results[apps[0]]},
                       headers=headers(lead)).status_code == 400
    assert client.post(f"/v1/qa/items/{item_id}/flags", json=body, headers=headers(lead)).status_code == 201
    assert client.post(f"/v1/qa/items/{item_id}/review", json={"decision": "PASSED"}, headers=headers(lead)).status_code == 409

    passed = next(i for i in queue["items"] if i["sample_item_id"] != item_id)
    assert client.post(f"/v1/qa/items/{passed['sample_item_id']}/review", json={"decision": "PASSED"},
                       headers=headers(lead)).status_code == 200

    summary = client.get(f"/v1/qa/summary?position_id={seed['pos']}", headers=headers(recruiter)).json()
    assert summary["reviewed_items"] == 2 and summary["flagged_items"]["count"] == 1
    assert summary["by_flag_type"]["MISSED_CONTENT"]["count"] == 1
    assert summary["small_sample_warning"] is True
    assert summary["pending_items"] == len(queue["items"]) - 2
    assert client.get("/v1/qa/summary", headers=headers(recruiter)).status_code == 403

    manual = client.post(f"/v1/qa/positions/{seed['pos']}/sample-runs", json={"batch_id": batch}, headers=headers(lead))
    assert manual.status_code == 201 and manual.json()["population_size"] == 12
    assert client.post(f"/v1/qa/positions/{seed['pos']}/sample-runs", json={"batch_id": batch},
                       headers=headers(recruiter)).status_code == 403
    with engine.begin() as conn:
        actions = conn.execute(text("""
            SELECT action_type, COUNT(*) FROM app_private.audit_events
            WHERE action_type IN ('ADD_QA_FLAG','PASS_QA_SAMPLE','CREATE_QA_SAMPLE') GROUP BY action_type
        """)).all()
    assert dict(actions) == {"ADD_QA_FLAG": 1, "PASS_QA_SAMPLE": 1, "CREATE_QA_SAMPLE": 2}
