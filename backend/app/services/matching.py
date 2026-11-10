from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
import json
import re
import math
from app.core.config import settings
from app.schemas.criteria import CriterionRating, CriteriaCategory


MAX_YEARS_EXPERIENCE = 60.0


def normalize_years_experience(value: Any) -> Optional[float]:
    """Return a plausible years-of-experience number, or None when unknown.

    The model may return strings, negatives or NaN; an unknown value must stay
    None so the assessment step does not read it as "0 years".
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        years = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(years) or years < 0 or years > MAX_YEARS_EXPERIENCE:
        return None
    return round(years, 1)


def profile_years_experience(extraction_config: Any) -> Optional[float]:
    """Read years of experience stored on a profile version's extraction_config."""
    if isinstance(extraction_config, str):
        try:
            extraction_config = json.loads(extraction_config)
        except ValueError:
            return None
    if not isinstance(extraction_config, dict):
        return None
    return normalize_years_experience(extraction_config.get("total_years_experience"))


class MatchingEngine:
    """Deterministic scoring and ranking engine - NO LLM CALLS HERE
    All calculations follow approved policy to eliminate hallucination risk.
    """

    SCORE_MAP = {
        CriterionRating.STRONG_MATCH: settings.STRONG_MATCH_SCORE,
        CriterionRating.MATCH: settings.MATCH_SCORE,
        CriterionRating.NO_MATCH: settings.NO_MATCH_SCORE,
        CriterionRating.UNCLEAR: None  # Does not count towards score or coverage
    }

    def calculate_criterion_weight(
        self,
        criterion: Dict[str, Any],
        all_criteria: List[Dict[str, Any]],
        group_weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """Calculate effective weight for a criterion: group_total_weight * relative_weight_in_group"""
        group_weight = (group_weights.get(criterion["category"], 0.0) if group_weights is not None else (
            settings.MANDATORY_CRITERIA_WEIGHT_DEFAULT
            if criterion["category"] == CriteriaCategory.MUST_HAVE.value
            else settings.NICE_TO_HAVE_WEIGHT_DEFAULT
        ))
        # Sum of weight_in_group in this category
        group_total = sum(float(c["weight_in_group"]) for c in all_criteria if c["category"] == criterion["category"])
        if group_total == 0:
            return 0
        relative = float(criterion["weight_in_group"]) / group_total
        return group_weight * relative

    def calculate_assessment_scores(
        self,
        criteria: List[Dict[str, Any]],
        findings: List[Dict[str, Any]],
        group_weights: Optional[Dict[str, float]] = None,
    ) -> Tuple[Optional[float], float, str, List[Dict[str, Any]], bool]:
        """
        Calculate matching score, evidence coverage, and matching status.
        Returns: (score, coverage, matching_status, augmented_findings, needs_verification)
        """
        total_applicable_weight = 0.0
        total_scored_weight = 0.0
        weighted_score_sum = 0.0
        has_mandatory_mismatch = False
        needs_verification = False
        augmented_findings = []

        # Map findings by criterion_id
        findings_map = {f["criterion_id"]: f for f in findings}

        for crit in criteria:
            crit_id = crit["criterion_id"]
            effective_weight = self.calculate_criterion_weight(crit, criteria, group_weights)
            total_applicable_weight += effective_weight

            finding = findings_map.get(crit_id, {})
            outcome = finding.get("outcome", CriterionRating.UNCLEAR.value)
            if outcome not in {rating.value for rating in CriterionRating}:
                outcome = CriterionRating.UNCLEAR.value
            try:
                confidence = float(finding.get("confidence", 0.5))
            except (TypeError, ValueError):
                confidence = 0.0
            confidence = confidence if math.isfinite(confidence) and 0 <= confidence <= 1 else 0.0
            confidence_band = str(finding.get("confidence_band") or "LOW").strip().upper()
            if confidence_band not in {"HIGH", "MEDIUM", "LOW"}:
                confidence_band = "LOW"

            # A low/invalid confidence or explicit review flag is not a reliable
            # finding, even when the model claimed MATCH or NO_MATCH.
            is_reliable = (
                outcome != CriterionRating.UNCLEAR.value
                and confidence >= 0.6
                and confidence_band in {"MEDIUM", "HIGH"}
                and not finding.get("requires_verification")
            )
            if not is_reliable:
                outcome = CriterionRating.UNCLEAR.value

            if is_reliable:
                point_value = self.SCORE_MAP.get(CriterionRating(outcome), None)
                if point_value is not None:
                    weighted_score_sum += (point_value / 100) * effective_weight
                    total_scored_weight += effective_weight

                    if outcome == CriterionRating.NO_MATCH.value and crit["category"] == CriteriaCategory.MUST_HAVE.value:
                        has_mandatory_mismatch = True
            else:
                # Unclear or low confidence
                if crit["category"] == CriteriaCategory.MUST_HAVE.value:
                    needs_verification = True

            # Augment finding with effective weight
            aug_finding = {**finding, "criterion_id": crit_id, "outcome": outcome,
                           "confidence": confidence, "confidence_band": confidence_band,
                           "requires_verification": bool(finding.get("requires_verification")) or not is_reliable,
                           "effective_weight": effective_weight}
            augmented_findings.append(aug_finding)

        # Calculate final scores
        if total_scored_weight == 0:
            matching_score = None
        else:
            matching_score = round((weighted_score_sum / total_applicable_weight) * 100, 1) if total_applicable_weight > 0 else None

        # The DB stores two decimal places. Round down conservatively before
        # applying the threshold so 69.9% cannot be stored as 70% and ranked.
        evidence_coverage = (min(1.0, math.floor((total_scored_weight / total_applicable_weight + 1e-12) * 100) / 100)
                             if total_applicable_weight > 0 else 0)

        # Check coverage threshold
        if evidence_coverage < settings.MIN_EVIDENCE_COVERAGE:
            needs_verification = True

        # Determine matching status
        if not criteria or total_applicable_weight == 0:
            matching_status = "NOT_ASSESSED"
        elif has_mandatory_mismatch and not needs_verification:
            matching_status = "POSSIBLE_MISMATCH"
        elif needs_verification:
            matching_status = "NEEDS_HR_VERIFICATION"
        else:
            matching_status = "MEETS_MANDATORY"

        return matching_score, evidence_coverage, matching_status, augmented_findings, needs_verification

    def verify_verbatim_quote(self, quote: str, cv_full_text: str) -> bool:
        """Verify an exact quote after whitespace/case normalization, not a fuzzy guess."""
        if not quote or len(quote) < 10:
            return False
        normalize = lambda value: " ".join(value.lower().split())
        return normalize(quote) in normalize(cv_full_text)

    def quote_pages(self, quote: str, cv_full_text: str) -> list[int]:
        """Return actual PDF page markers containing the quote; DOCX has no page markers."""
        parts = re.split(r"--- Page (\d+) ---", cv_full_text)
        return [int(parts[index]) for index in range(1, len(parts) - 1, 2)
                if self.verify_verbatim_quote(quote, parts[index + 1])]

    def rank_applications(
        self,
        applications_with_assessments: List[Dict[str, Any]],
        criteria: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Rank applications within same position per policy:
        Priority 1: Match mandatory criteria (MEETS_MANDATORY > NEEDS_VERIFICATION > POSSIBLE_MISMATCH)
        Priority 2: Matching score (descending)
        Priority 3: Evidence coverage (descending)
        """
        # Group by matching status priority
        status_order = {
            "MEETS_MANDATORY": 0,
            "NEEDS_HR_VERIFICATION": 1,
            "POSSIBLE_MISMATCH": 2,
            "NOT_ASSESSED": 3
        }

        def sort_key(item):
            assess = item.get("latest_assessment", {})
            status = assess.get("matching_status", "NOT_ASSESSED")
            score = assess.get("matching_score")
            score = score if score is not None else -1
            coverage = assess.get("evidence_coverage") or 0
            return (
                status_order.get(status, 99),
                -score,  # Negative for descending sort
                -coverage
            )

        sorted_items = sorted(applications_with_assessments, key=sort_key)

        # Assign rank numbers only to applications with enough evidence
        result = []
        current_rank = 1
        for item in sorted_items:
            assess = item.get("latest_assessment", {})
            coverage = assess.get("evidence_coverage") or 0
            status = assess.get("matching_status", "NOT_ASSESSED")

            rank_num = current_rank if (
                coverage >= settings.MIN_EVIDENCE_COVERAGE
                and status != "NOT_ASSESSED"
            ) else None

            result.append({
                **item,
                "rank_number": rank_num,
                "has_mismatch": status == "POSSIBLE_MISMATCH",
                "needs_verification": status == "NEEDS_HR_VERIFICATION" or coverage < settings.MIN_EVIDENCE_COVERAGE
            })

            if rank_num is not None:
                current_rank += 1

        return result

    def detect_duplicates(
        self,
        applications: List[Dict[str, Any]]
    ) -> List[Tuple[str, str, float, str]]:
        """
        Detect potential duplicate applications within same position.
        Returns list of (app_id_1, app_id_2, confidence, signal_type)
        """
        duplicates = []

        for i, app1 in enumerate(applications):
            identity1 = app1.get("identity", {})
            email1 = (identity1.get("email") or "").lower().strip()
            phone1 = (identity1.get("phone") or "").strip()

            for j in range(i + 1, len(applications)):
                app2 = applications[j]
                identity2 = app2.get("identity", {})
                email2 = (identity2.get("email") or "").lower().strip()
                phone2 = (identity2.get("phone") or "").strip()

                # Exact email match
                if email1 and email1 == email2:
                    duplicates.append((
                        app1["application_id"],
                        app2["application_id"],
                        0.98,
                        "EMAIL_MATCH"
                    ))
                    continue

                # Exact phone match
                if phone1 and phone1 == phone2:
                    duplicates.append((
                        app1["application_id"],
                        app2["application_id"],
                        0.95,
                        "PHONE_MATCH"
                    ))
                    continue

                # Fuzzy name match + content similarity would go here in production
                # For MVP MVP we only use hard contact signals

        return duplicates


# Singleton instance
matching_engine = MatchingEngine()
