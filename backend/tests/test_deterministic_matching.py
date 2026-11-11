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
    # One quantified fragment is not a reliable career total, so the safer
    # result is unresolved rather than a rule NO_MATCH.
    assert not_enough["findings"] == []
    assert not_enough["unresolved_criterion_ids"] == ["c1"]


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


def test_negated_skill_mention_is_unresolved_not_a_rule_match():
    criteria = [criterion(
        "docker", "Docker/container delivery", "Docker or containerised deployment experience",
        category="NICE_TO_HAVE", keywords=["Docker", "container", "Kubernetes"],
    )]
    text = (
        "WORK EXPERIENCE\n"
        "Developed Python backend APIs and PostgreSQL reports.\n\n"
        "Skills\nPython, PostgreSQL, SQL, Linux, Git.\n\n"
        "Note: this synthetic CV intentionally does not claim Docker or container delivery experience."
    )
    result = deterministic_matcher.evaluate_criteria(text, criteria, {})
    assert result["findings"] == []
    assert result["unresolved_criterion_ids"] == ["docker"]


def test_positive_skill_still_matches_when_another_sentence_is_negated():
    criteria = [criterion(
        "docker", "Docker/container delivery", "Docker or containerised deployment experience",
        category="NICE_TO_HAVE", keywords=["Docker", "container", "Kubernetes"],
    )]
    text = (
        "WORK EXPERIENCE\n"
        "No Docker use in the first role. Delivered services with Docker container deployments in the second role."
    )
    result = deterministic_matcher.evaluate_criteria(text, criteria, {})
    assert result["findings"]
    assert result["findings"][0]["decision_source"] == "RULE"
    assert "Docker container deployments" in result["findings"][0]["evidence"]["verbatim_quote"]


def test_vietnamese_negated_skill_mention_is_unresolved():
    criteria = [criterion(
        "docker", "Docker/container delivery", "Docker or containerised deployment experience",
        category="NICE_TO_HAVE", keywords=["Docker", "container", "Kubernetes"],
    )]
    result = deterministic_matcher.evaluate_criteria(
        "KINH NGHIỆM\nChưa có kinh nghiệm Docker hoặc triển khai container.", criteria, {})
    assert result["findings"] == []
    assert result["unresolved_criterion_ids"] == ["docker"]


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


def test_years_rule_sums_distinct_duration_sentences_and_quotes_duration():
    criteria = [criterion("c1", "Python experience", "At least 5 years of Python experience")]
    text = (
        "WORK EXPERIENCE\n"
        "Python Engineer at A. Built APIs for 3 years.\n\n"
        "Python Engineer at B. Built services for 3 years."
    )
    result = deterministic_matcher.evaluate_criteria(text, criteria, {})
    finding = result["findings"][0]
    assert result["candidate_years_experience"] == 6
    assert finding["outcome"] in {"MATCH", "STRONG_MATCH"}
    assert "years" in finding["evidence"]["verbatim_quote"]


def test_years_rule_does_not_no_match_from_unreliable_duration_fragment():
    criteria = [criterion("c1", "Python experience", "At least 5 years of Python experience")]
    result = deterministic_matcher.evaluate_criteria(
        "WORK EXPERIENCE\nBuilt Python tools for 2 years. Other work is undated.",
        criteria, {})
    assert result["findings"] == []
    assert result["unresolved_criterion_ids"] == ["c1"]


def test_language_rule_is_order_independent_and_conflicts_are_unresolved():
    criteria = [criterion("lang", "English", "English language, IELTS 7.0 required")]
    high_first = deterministic_matcher.evaluate_criteria(
        "LANGUAGES\nEnglish IELTS 7.0. English IELTS 5.5.", criteria, {})
    low_first = deterministic_matcher.evaluate_criteria(
        "LANGUAGES\nEnglish IELTS 5.5. English IELTS 7.0.", criteria, {})
    assert high_first["findings"] == []
    assert low_first["findings"] == []
    assert high_first["unresolved_criterion_ids"] == ["lang"]
    assert low_first["unresolved_criterion_ids"] == ["lang"]


def test_language_rule_preserves_decimal_quote_and_uses_level_sentence():
    criteria = [criterion("lang", "English", "English language, IELTS 7.0 required")]
    result = deterministic_matcher.evaluate_criteria(
        "EDUCATION\nPhD in Management.\n\nLANGUAGES\nIELTS 6.5.", criteria, {})
    finding = result["findings"][0]
    assert finding["outcome"] == "NO_MATCH"
    assert finding["evidence"]["verbatim_quote"] == "IELTS 6.5."


def test_degree_rule_does_not_use_lower_cv_quote_for_profile_only_match():
    criteria = [criterion("degree", "Education", "Master degree required")]
    result = deterministic_matcher.evaluate_criteria(
        "EDUCATION\nBachelor of Computer Science, Example University.",
        criteria,
        {"education": ["Master of Finance"]},
    )
    assert result["findings"] == []
    assert result["unresolved_criterion_ids"] == ["degree"]


def test_degree_below_outside_education_section_is_unresolved():
    criteria = [criterion("degree", "Education", "Master degree required")]
    result = deterministic_matcher.evaluate_criteria(
        "WORK EXPERIENCE\nSupported bachelor-level coursework tooling.", criteria, {})
    assert result["findings"] == []
    assert result["unresolved_criterion_ids"] == ["degree"]


def test_phrase_constituent_token_does_not_satisfy_skill():
    criteria = [criterion("c1", "Python programming", "Python programming", keywords=["Python programming"])]
    result = deterministic_matcher.evaluate_criteria(
        "SKILLS\nProgramming reliable business systems for clients.", criteria, {})
    assert result["findings"] == []
    assert result["unresolved_criterion_ids"] == ["c1"]
    assert result["fallback_chunks"]["c1"]


def test_explicit_requirement_spec_overrides_text_inference():
    item = criterion("c1", "Backend role", "General backend work")
    item["requirement_spec"] = {
        "kind": "YEARS",
        "terms": ["Python"],
        "min_years": 5,
    }
    spec = deterministic_matcher.build_requirement_spec(item)
    assert spec.kind == "YEARS"
    assert spec.min_years == 5
    assert [term.label for term in spec.terms] == ["python"]
