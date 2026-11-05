from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
from app.core.config import settings
from app.schemas.criteria import CriterionRating, CriteriaCategory
import difflib


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
        all_criteria: List[Dict[str, Any]]
    ) -> float:
        """Calculate effective weight for a criterion: group_total_weight * relative_weight_in_group"""
        group_weight = (
            settings.MANDATORY_CRITERIA_WEIGHT_DEFAULT
            if criterion["category"] == CriteriaCategory.MUST_HAVE.value
            else settings.NICE_TO_HAVE_WEIGHT_DEFAULT
        )
        # Sum of weight_in_group in this category
        group_total = sum(c["weight_in_group"] for c in all_criteria if c["category"] == criterion["category"])
        if group_total == 0:
            return 0
        relative = criterion["weight_in_group"] / group_total
        return group_weight * relative / 100

    def calculate_assessment_scores(
        self,
        criteria: List[Dict[str, Any]],
        findings: List[Dict[str, Any]]
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
            effective_weight = self.calculate_criterion_weight(crit, criteria)
            total_applicable_weight += effective_weight

            finding = findings_map.get(crit_id, {})
            outcome = finding.get("outcome", CriterionRating.UNCLEAR.value)
            confidence = finding.get("confidence", 0.5)
            confidence_band = finding.get("confidence_band", "LOW")

            # Determine if finding is reliable enough
            is_reliable = (
                outcome != CriterionRating.UNCLEAR.value
                and confidence >= 0.6
                and confidence_band != "LOW"
            )

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
            aug_finding = {**finding, "effective_weight": effective_weight}
            augmented_findings.append(aug_finding)

        # Calculate final scores
        if total_scored_weight == 0:
            matching_score = None
        else:
            matching_score = round((weighted_score_sum / total_applicable_weight) * 100, 1) if total_applicable_weight > 0 else None

        evidence_coverage = round(total_scored_weight / total_applicable_weight, 3) if total_applicable_weight > 0 else 0

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

    def verify_verbatim_quote(self, quote: str, cv_full_text: str, threshold: float = 0.85) -> bool:
        """Verify that verbatim quote actually exists in CV text (anti-hallucination guard)"""
        if not quote or len(quote) < 10:
            return False

        # Normalize whitespace for comparison
        def normalize(s: str) -> str:
            return " ".join(s.lower().split())

        norm_quote = normalize(quote)
        norm_cv = normalize(cv_full_text)

        # Direct substring match
        if norm_quote in norm_cv:
            return True

        # Fuzzy match for minor OCR differences
        # Use sliding window matching
        quote_len = len(norm_quote)
        if quote_len > len(norm_cv):
            return False

        for i in range(0, len(norm_cv) - quote_len + 1, max(1, quote_len // 4)):
            window = norm_cv[i:i + quote_len + 20]
            similarity = difflib.SequenceMatcher(None, norm_quote, window[:quote_len]).ratio()
            if similarity >= threshold:
                return True

        return False

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
            score = assess.get("matching_score") or -1
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
