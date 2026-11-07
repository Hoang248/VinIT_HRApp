from app.services.deterministic_matching import deterministic_matcher


def criterion(criterion_id, name, description, category="MUST_HAVE", keywords=None):
    return {
        "criterion_id": criterion_id,
        "name": name,
        "description": description,
        "category": category,
        "weight_in_group": 100,
        "expected_evidence_keywords": keywords or [],
    }


def test_chunking_preserves_page_section_and_offsets():
    text = (
        "--- Page 1 ---\n"
        "Summary\n"
        "Backend developer.\n\n"
        "--- Page 2 ---\n"
        "WORK EXPERIENCE\n"
        "Built Python services for five years.\n\n"
        "Skills: Docker, Kubernetes\n"
    )
    chunks = deterministic_matcher.chunk_document(text)
    assert [chunk.chunk_id for chunk in chunks] == ["chunk-0001", "chunk-0002", "chunk-0003"]
    assert chunks[0].page_number == 1 and chunks[0].section == "SUMMARY"
    assert chunks[1].page_number == 2 and chunks[1].section == "WORK"
    assert chunks[2].section == "SKILL"
    for chunk in chunks:
        assert text[chunk.char_start:chunk.char_end] == chunk.text


def test_skill_rule_is_deterministic_and_uses_aliases():
    criteria = [criterion("c1", "JavaScript", "JavaScript experience", keywords=["JS"])]
    text = "WORK EXPERIENCE\nDeveloped JavaScript applications with React for four years."
    first = deterministic_matcher.evaluate_criteria(text, criteria, {})
    second = deterministic_matcher.evaluate_criteria(text, criteria, {})
    assert first == second
    finding = first["findings"][0]
    assert finding["outcome"] == "STRONG_MATCH"
    assert finding["decision_source"] == "RULE"
    assert finding["evidence_chunk_id"].startswith("chunk-")
    assert "JavaScript applications" in finding["evidence"]["verbatim_quote"]
    assert first["unresolved_criterion_ids"] == []


def test_years_rule_matches_and_rejects_explicit_evidence():
    criteria = [criterion("c1", "Python experience", "At least 5 years of Python experience")]
    enough = deterministic_matcher.evaluate_criteria(
        "WORK EXPERIENCE\nBuilt Python platforms for 8 years.", criteria, {})
    not_enough = deterministic_matcher.evaluate_criteria(
        "WORK EXPERIENCE\nBuilt Python tools for 2 years.", criteria, {})
    assert enough["findings"][0]["outcome"] == "STRONG_MATCH"
    assert not_enough["findings"][0]["outcome"] == "NO_MATCH"


def test_years_rule_can_sum_non_overlapping_date_ranges():
    criteria = [criterion("c1", "Backend experience", "Minimum 5 years of backend experience")]
    text = (
        "WORK EXPERIENCE\n"
        "Backend Engineer 2016 - 2019. Built APIs.\n\n"
        "Senior Backend Engineer 2019 - 2022. Led services."
    )
    result = deterministic_matcher.evaluate_criteria(text, criteria, {})
    assert result["candidate_years_experience"] >= 5
    assert result["findings"][0]["outcome"] in {"MATCH", "STRONG_MATCH"}


def test_degree_and_language_rules():
    criteria = [
        criterion("degree", "Education", "Bachelor degree required"),
        criterion("lang", "English", "English language, IELTS 6.5 required", category="NICE_TO_HAVE"),
    ]
    text = (
        "EDUCATION\nBachelor of Computer Science, Example University.\n\n"
        "LANGUAGES\nEnglish IELTS 7.0."
    )
    result = deterministic_matcher.evaluate_criteria(text, criteria, {})
    outcomes = {finding["criterion_id"]: finding["outcome"] for finding in result["findings"]}
    assert outcomes == {"degree": "MATCH", "lang": "MATCH"}


def test_degree_below_requirement_is_explicit_no_match():
    criteria = [criterion("degree", "Education", "Master degree required")]
    result = deterministic_matcher.evaluate_criteria(
        "EDUCATION\nBachelor of Computer Science, Example University.", criteria, {})
    assert result["findings"][0]["outcome"] == "NO_MATCH"


def test_absent_skill_is_unresolved_not_no_match():
    criteria = [criterion("c1", "Rust", "Rust experience")]
    result = deterministic_matcher.evaluate_criteria(
        "WORK EXPERIENCE\nBuilt Python services for five years.", criteria, {})
    assert result["findings"] == []
    assert result["unresolved_criterion_ids"] == ["c1"]


def test_requirement_spec_detects_measurable_kinds():
    years = deterministic_matcher.build_requirement_spec(
        criterion("y", "Python", "At least 3 years of Python experience"))
    degree = deterministic_matcher.build_requirement_spec(
        criterion("d", "Education", "Master's degree in Computer Science"))
    cert = deterministic_matcher.build_requirement_spec(
        criterion("c", "AWS Certification", "AWS Certified Solutions Architect"))
    language = deterministic_matcher.build_requirement_spec(
        criterion("l", "English", "English proficiency, IELTS 6.0"))
    assert (years.kind, years.min_years) == ("YEARS", 3.0)
    assert (degree.kind, degree.required_degree_level) == ("DEGREE", 4)
    assert cert.kind == "CERTIFICATION"
    assert (language.kind, language.required_ielts) == ("LANGUAGE", 6.0)
