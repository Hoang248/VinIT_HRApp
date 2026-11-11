"""Unit tests for F2.04 QA sample selection and the redacted flag export."""
import importlib.util
import uuid
from pathlib import Path

from app.services import qa_sampling as qa
from app.services.qa_sampling import Candidate


def _cand(i, coverage=0.9, fails=0):
    return Candidate(application_id=str(uuid.UUID(int=i + 1)), assessment_id=str(uuid.UUID(int=10_000 + i)),
                     evidence_coverage=coverage, must_have_no_match_count=fails)


def test_random_sample_size_rounds_up_with_minimum_one():
    assert qa.random_sample_size(0) == 0
    assert qa.random_sample_size(1) == 1
    assert qa.random_sample_size(9) == 1
    assert qa.random_sample_size(10) == 1
    assert qa.random_sample_size(11) == 2
    assert qa.random_sample_size(100) == 10


def test_random_selection_is_deterministic_and_uses_smallest_hash():
    run_id = "6f1b5c1e-0000-4000-8000-000000000001"
    candidates = [_cand(i) for i in range(40)]
    first = qa.select_sample(run_id, candidates)
    second = qa.select_sample(run_id, list(reversed(candidates)))
    assert [i.application_id for i in first] == [i.application_id for i in second]
    assert len(first) == 4 and all(i.reasons == ["RANDOM"] for i in first)
    expected = sorted(c.application_id for c in candidates
                      if qa.selection_sha256(run_id, c.application_id)
                      in sorted(qa.selection_sha256(run_id, x.application_id) for x in candidates)[:4])
    assert sorted(i.application_id for i in first) == expected
    other = qa.select_sample("6f1b5c1e-0000-4000-8000-000000000002", candidates)
    assert {i.application_id for i in other} != {i.application_id for i in first}


def test_all_risk_cases_are_included_with_reasons():
    candidates = [_cand(i) for i in range(30)]
    candidates[3] = _cand(3, fails=1)
    candidates[4] = _cand(4, fails=2)            # two must-have failures: not "single"
    candidates[5] = _cand(5, coverage=0.60)      # lower bound inclusive
    candidates[6] = _cand(6, coverage=0.80)      # upper bound exclusive
    candidates[7] = _cand(7, coverage=0.65, fails=1)
    candidates[8] = _cand(8, coverage=None)
    selected = {i.application_id: i.reasons for i in qa.select_sample("run", candidates)}
    ids = [c.application_id for c in candidates]
    assert "SINGLE_MUST_HAVE_FAIL" in selected[ids[3]]
    assert ids[4] not in selected or selected[ids[4]] == ["RANDOM"]
    assert "COVERAGE_NEAR_THRESHOLD" in selected[ids[5]]
    assert ids[6] not in selected or selected[ids[6]] == ["RANDOM"]
    assert [r for r in selected[ids[7]] if r != "RANDOM"] == ["SINGLE_MUST_HAVE_FAIL", "COVERAGE_NEAR_THRESHOLD"]
    assert sum("RANDOM" in r for r in selected.values()) == 3


def test_duplicate_application_rows_are_counted_once():
    c = _cand(1)
    assert len(qa.select_sample("run", [c, c, c])) == 1


def test_wilson_interval_and_small_sample_warning():
    assert qa.wilson_interval(0, 0) is None
    low, high = qa.wilson_interval(4, 10)
    assert 0.16 < low < 0.17 and 0.68 < high < 0.69
    summary = qa.flag_rate_summary(10, {"OCR_ERROR": 1, "MISSED_CONTENT": 3}, 4)
    assert summary["small_sample_warning"] is True
    assert summary["flagged_items"]["rate"] == 0.4
    assert list(summary["by_flag_type"]) == ["MISSED_CONTENT", "OCR_ERROR"]
    assert qa.flag_rate_summary(30, {}, 0)["small_sample_warning"] is False


def _export_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "export_qa_flags.py"
    spec = importlib.util.spec_from_file_location("export_qa_flags", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_export_redacts_note_and_omits_quotes_by_default():
    module = _export_module()
    record = {"flag_id": uuid.uuid4(), "flag_type": "MISSED_CONTENT", "position_id": uuid.uuid4(),
              "application_id": uuid.uuid4(), "assessment_id": uuid.uuid4(), "criterion_id": uuid.uuid4(),
              "criterion_name": "Python", "category": "MUST_HAVE", "outcome": "NO_MATCH",
              "expected_outcome": "MATCH", "reasons": ["SINGLE_MUST_HAVE_FAIL"], "sampling_rules_version": "v",
              "note": "Ứng viên ghi Python ở mục dự án, liên hệ an.nguyen@example.com 0912 345 678",
              "created_at": "2026-11-11T03:00:00+00:00", "verbatim_quote": "Python 3 at Example Co", "page_number": 1}
    row = module.build_row(record, include_quotes=False)
    assert "evidence_quote_redacted" not in row
    assert "example.com" not in row["note_redacted"] and "345" not in row["note_redacted"]
    assert module.find_pii([row]) == []
    assert module.build_row(record, include_quotes=True)["evidence_quote_redacted"]


def test_export_guard_detects_surviving_contact_details():
    module = _export_module()
    rows = [{"flag_id": "a", "note_redacted": "call +84 912 345 678", "created_at": "2026-11-11T03:00:00"},
            {"flag_id": "b", "note_redacted": "ok", "created_at": "2026-11-11T03:00:00"}]
    assert module.find_pii(rows) == ["a"]
