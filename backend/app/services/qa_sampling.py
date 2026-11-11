"""F2.04 quality-assurance sample selection.

Selection rules (HRA_NextPhase F2.04, decisions D-1..D-6 of 11/11/2026):

* one sample run per CV batch ("đợt"), over the latest completed assessment of
  each application in that batch for the approved rubric version;
* RANDOM: ceil(10%) of the population, minimum 1, chosen deterministically as
  the smallest sha256(sample_run_id ":" application_id).  An auditor can
  re-derive the same sample from the stored run id without a random seed;
* SINGLE_MUST_HAVE_FAIL: every assessment with exactly one MUST_HAVE criterion
  whose outcome is NO_MATCH (UNCLEAR is not a failure);
* COVERAGE_NEAR_THRESHOLD: every assessment whose evidence coverage lies in
  [0.60, 0.80), i.e. close to the 0.70 working threshold.

The pure functions here never touch the database so they can be unit tested;
``create_sample_run`` persists a run with plain SQL like the rest of the app.
"""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from sqlalchemy import text

SAMPLING_RULES_VERSION = "qa-sampling-v1"
RANDOM_RATE = 0.10
COVERAGE_BAND_LOW = 0.60
COVERAGE_BAND_HIGH = 0.80
MIN_RELIABLE_SAMPLE = 30

REASON_RANDOM = "RANDOM"
REASON_SINGLE_MUST_HAVE_FAIL = "SINGLE_MUST_HAVE_FAIL"
REASON_COVERAGE_NEAR_THRESHOLD = "COVERAGE_NEAR_THRESHOLD"
REASON_ORDER = (REASON_RANDOM, REASON_SINGLE_MUST_HAVE_FAIL, REASON_COVERAGE_NEAR_THRESHOLD)


@dataclass(frozen=True)
class Candidate:
    application_id: str
    assessment_id: str
    evidence_coverage: float | None
    must_have_no_match_count: int


@dataclass
class SelectedItem:
    application_id: str
    assessment_id: str
    selection_sha256: str
    reasons: list[str] = field(default_factory=list)


def selection_sha256(sample_run_id: str, application_id: str) -> str:
    return hashlib.sha256(f"{sample_run_id}:{application_id}".encode("utf-8")).hexdigest()


def random_sample_size(population: int, rate: float = RANDOM_RATE) -> int:
    if population <= 0:
        return 0
    return min(population, max(1, math.ceil(population * rate - 1e-9)))


def risk_reasons(candidate: Candidate, *, band_low: float = COVERAGE_BAND_LOW,
                 band_high: float = COVERAGE_BAND_HIGH) -> list[str]:
    reasons: list[str] = []
    if candidate.must_have_no_match_count == 1:
        reasons.append(REASON_SINGLE_MUST_HAVE_FAIL)
    coverage = candidate.evidence_coverage
    if coverage is not None and band_low <= coverage < band_high:
        reasons.append(REASON_COVERAGE_NEAR_THRESHOLD)
    return reasons


def select_sample(sample_run_id: str, candidates: Iterable[Candidate], *, rate: float = RANDOM_RATE,
                  band_low: float = COVERAGE_BAND_LOW, band_high: float = COVERAGE_BAND_HIGH) -> list[SelectedItem]:
    """Return the union of the deterministic random sample and all risk cases."""
    unique: dict[str, Candidate] = {}
    for candidate in candidates:
        unique.setdefault(candidate.application_id, candidate)
    hashed = sorted(
        ((selection_sha256(sample_run_id, app_id), cand) for app_id, cand in unique.items()),
        key=lambda pair: pair[0],
    )
    random_ids = {cand.application_id for _, cand in hashed[:random_sample_size(len(hashed), rate)]}
    selected: list[SelectedItem] = []
    for digest, cand in hashed:
        reasons = risk_reasons(cand, band_low=band_low, band_high=band_high)
        if cand.application_id in random_ids:
            reasons.insert(0, REASON_RANDOM)
        if reasons:
            selected.append(SelectedItem(cand.application_id, cand.assessment_id, digest,
                                         sorted(reasons, key=REASON_ORDER.index)))
    return selected


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    """Wilson score interval for a proportion; None when there is no data."""
    if total <= 0:
        return None
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def flag_rate_summary(reviewed: int, flagged_by_type: Mapping[str, int], flagged_items: int) -> dict[str, Any]:
    """Flag rates with 95% Wilson intervals and a small-sample warning."""
    def entry(count: int) -> dict[str, Any]:
        interval = wilson_interval(count, reviewed)
        return {
            "count": count,
            "rate": round(count / reviewed, 4) if reviewed else None,
            "wilson95": [round(interval[0], 4), round(interval[1], 4)] if interval else None,
        }
    return {
        "reviewed_items": reviewed,
        "flagged_items": entry(flagged_items),
        "by_flag_type": {flag_type: entry(count) for flag_type, count in sorted(flagged_by_type.items())},
        "small_sample_warning": reviewed < MIN_RELIABLE_SAMPLE,
        "min_reliable_sample": MIN_RELIABLE_SAMPLE,
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def load_batch_candidates(db, *, position_id: str, batch_id: str, criteria_version_id: str) -> list[Candidate]:
    """Latest completed assessment per application of the batch for one rubric version."""
    rows = db.execute(text("""
        WITH latest AS (
            SELECT DISTINCT ON (ar.application_id)
                   ar.application_id, ar.assessment_id, ar.evidence_coverage
            FROM app_private.assessment_runs ar
            JOIN app_private.cv_batch_items bi ON bi.application_id = ar.application_id
            WHERE bi.batch_id = :batch_id AND ar.position_id = :position_id
              AND ar.criteria_version_id = :criteria_version_id AND ar.status = 'COMPLETED'
            ORDER BY ar.application_id, ar.completed_at DESC NULLS LAST, ar.created_at DESC
        )
        SELECT l.application_id, l.assessment_id, l.evidence_coverage,
               COUNT(cr.result_id) FILTER (
                   WHERE ci.category = 'MUST_HAVE' AND cr.outcome = 'NO_MATCH'
               ) AS must_have_no_match_count
        FROM latest l
        LEFT JOIN app_private.criterion_assessment_results cr ON cr.assessment_id = l.assessment_id
        LEFT JOIN app_private.criteria_items ci ON ci.criterion_id = cr.criterion_id
        GROUP BY l.application_id, l.assessment_id, l.evidence_coverage
    """), {"position_id": position_id, "batch_id": batch_id,
           "criteria_version_id": criteria_version_id}).mappings().all()
    return [
        Candidate(
            application_id=str(row["application_id"]),
            assessment_id=str(row["assessment_id"]),
            evidence_coverage=float(row["evidence_coverage"]) if row["evidence_coverage"] is not None else None,
            must_have_no_match_count=int(row["must_have_no_match_count"] or 0),
        )
        for row in rows
    ]


def create_sample_run(db, *, position_id: str, batch_id: str, criteria_version_id: str,
                      trigger_type: str, actor_user_id: str | None = None) -> dict[str, Any] | None:
    """Insert one sample run with its items; caller commits.

    Returns None when the batch has no completed assessment, or when an AUTO
    run already exists for this batch and rubric version.
    """
    if trigger_type not in ("AUTO", "MANUAL"):
        raise ValueError("trigger_type must be AUTO or MANUAL")
    if trigger_type == "AUTO":
        exists = db.execute(text("""
            SELECT 1 FROM app_private.qa_sample_runs
            WHERE batch_id = :batch_id AND criteria_version_id = :criteria_version_id AND trigger_type = 'AUTO'
        """), {"batch_id": batch_id, "criteria_version_id": criteria_version_id}).first()
        if exists:
            return None
    candidates = load_batch_candidates(db, position_id=position_id, batch_id=batch_id,
                                       criteria_version_id=criteria_version_id)
    if not candidates:
        return None
    sample_run_id = str(uuid.uuid4())
    selected = select_sample(sample_run_id, candidates)
    db.execute(text("""
        INSERT INTO app_private.qa_sample_runs (
            sample_run_id, position_id, batch_id, criteria_version_id, trigger_type, sampling_rules_version,
            random_rate, coverage_band_low, coverage_band_high, population_size, sample_size, created_by)
        VALUES (:id, :position_id, :batch_id, :criteria_version_id, :trigger_type, :rules,
                :rate, :low, :high, :population, :sample, :actor)
    """), {"id": sample_run_id, "position_id": position_id, "batch_id": batch_id,
           "criteria_version_id": criteria_version_id, "trigger_type": trigger_type,
           "rules": SAMPLING_RULES_VERSION, "rate": RANDOM_RATE, "low": COVERAGE_BAND_LOW,
           "high": COVERAGE_BAND_HIGH, "population": len(candidates), "sample": len(selected),
           "actor": actor_user_id})
    for item in selected:
        db.execute(text("""
            INSERT INTO app_private.qa_sample_items
                (sample_run_id, application_id, assessment_id, reasons, selection_sha256)
            VALUES (:run, :application_id, :assessment_id, :reasons, :digest)
        """), {"run": sample_run_id, "application_id": item.application_id,
               "assessment_id": item.assessment_id, "reasons": item.reasons, "digest": item.selection_sha256})
    db.execute(text("""
        INSERT INTO app_private.audit_events
            (actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
        VALUES (:actor, 'CREATE_QA_SAMPLE', 'QA_SAMPLE_RUN', :id, :position_id, 'SUCCESS', CAST(:metadata AS JSONB))
    """), {"actor": actor_user_id, "id": sample_run_id, "position_id": position_id,
           "metadata": _json({"trigger_type": trigger_type, "batch_id": batch_id,
                              "population_size": len(candidates), "sample_size": len(selected),
                              "rules_version": SAMPLING_RULES_VERSION})})
    return {"sample_run_id": sample_run_id, "population_size": len(candidates), "sample_size": len(selected)}


def create_auto_runs_for_position(db, *, position_id: str, criteria_version_id: str) -> list[dict[str, Any]]:
    """Create AUTO runs for finished batches of a position that have none yet."""
    batches = db.execute(text("""
        SELECT b.batch_id FROM app_private.cv_batches b
        WHERE b.position_id = :position_id AND b.status IN ('COMPLETED', 'PARTIALLY_COMPLETED')
          AND NOT EXISTS (
              SELECT 1 FROM app_private.qa_sample_runs r
              WHERE r.batch_id = b.batch_id AND r.criteria_version_id = :criteria_version_id
                AND r.trigger_type = 'AUTO')
        ORDER BY b.created_at
    """), {"position_id": position_id, "criteria_version_id": criteria_version_id}).scalars().all()
    created = []
    for batch_id in batches:
        run = create_sample_run(db, position_id=position_id, batch_id=str(batch_id),
                                criteria_version_id=criteria_version_id, trigger_type="AUTO")
        if run:
            created.append(run)
    return created


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
