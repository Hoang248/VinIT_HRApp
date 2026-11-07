"""Unit tests for BGE/pgvector plumbing and offline LTR safety gates."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.services.embedding import (
    BGEHttpEmbeddingProvider,
    EmbeddingError,
    HashEmbeddingProvider,
    cosine_similarity,
    normalize_vector,
    requirement_query_text,
    semantic_config_fingerprint,
)
from app.services.ltr import LTRError, LTRModel, extract_ranking_features, train_ltr_model
from app.services.matching import MatchingEngine
from app.services.semantic_retrieval import merge_candidate_chunks, retrieve_semantic_candidates
from app.workers.processor import ProcessingWorker


def test_semantic_fingerprint_is_disabled_by_default(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SEMANTIC_RETRIEVAL_ENABLED", False)
    assert semantic_config_fingerprint() is None


def test_semantic_fingerprint_changes_with_model(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SEMANTIC_RETRIEVAL_ENABLED", True)
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "BAAI/bge-m3")
    monkeypatch.setattr(settings, "EMBEDDING_INDEX_VERSION", "bge-index-v1")
    first = semantic_config_fingerprint()
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
    assert semantic_config_fingerprint() != first
    assert semantic_config_fingerprint()["model"].endswith("bge-large-en-v1.5")


def test_normalize_and_cosine():
    assert normalize_vector([3, 4]) == pytest.approx([0.6, 0.8])
    assert cosine_similarity([1, 0], [1, 0]) == 1.0
    with pytest.raises(EmbeddingError):
        normalize_vector([0, 0])


def test_hash_embedding_is_deterministic_and_query_document_differ():
    provider = HashEmbeddingProvider(dimension=16)
    first = asyncio.run(provider.embed(["Python SQL"], kind="document"))[0]
    second = asyncio.run(provider.embed(["Python SQL"], kind="document"))[0]
    query = asyncio.run(provider.embed(["Python SQL"], kind="query"))[0]
    assert first == second
    assert first != query
    assert len(first) == 16




class _FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"data": [
            {"index": 1, "embedding": [0.0, 1.0]},
            {"index": 0, "embedding": [1.0, 0.0]},
        ]}


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, *, json, headers):
        assert url.endswith("/embeddings")
        assert json["model"] == "BAAI/bge-m3"
        assert len(json["input"]) == 2
        return _FakeResponse()


def test_bge_provider_reorders_response_rows_and_validates_dimension(monkeypatch):
    import app.services.embedding as embedding_module

    monkeypatch.setattr(embedding_module.httpx, "AsyncClient", _FakeAsyncClient)
    provider = BGEHttpEmbeddingProvider(
        api_base="https://embeddings.internal.example", model="BAAI/bge-m3", dimension=2)
    monkeypatch.setattr(provider, "_check_endpoint_policy", lambda: None)
    vectors = asyncio.run(provider.embed(["first", "second"], kind="document"))
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]

    bad_provider = BGEHttpEmbeddingProvider(
        api_base="https://embeddings.internal.example", model="BAAI/bge-m3", dimension=3)
    monkeypatch.setattr(bad_provider, "_check_endpoint_policy", lambda: None)
    with pytest.raises(EmbeddingError, match="dimension"):
        asyncio.run(bad_provider.embed(["first", "second"], kind="document"))


def test_bge_provider_requires_configured_endpoint():
    provider = BGEHttpEmbeddingProvider(api_base="", model="BAAI/bge-m3", dimension=2)
    with pytest.raises(EmbeddingError, match="not configured"):
        asyncio.run(provider.embed(["text"], kind="document"))


def test_requirement_query_text_from_structured_spec():
    query = requirement_query_text({
        "name": "Backend experience",
        "kind": "experience",
        "terms": [{"label": "Python"}, "PostgreSQL"],
        "min_years": 3,
    })
    assert "Python" in query and "PostgreSQL" in query and "3" in query


def test_semantic_retrieval_and_merge_prefer_dual_source_chunks():
    chunks = [
        {"chunk_id": "c1", "text": "Python", "page_number": 1, "char_start": 0, "char_end": 6},
        {"chunk_id": "c2", "text": "Cooking", "page_number": 1, "char_start": 7, "char_end": 14},
    ]
    semantic = retrieve_semantic_candidates(
        [1.0, 0.0], chunks, [[1.0, 0.0], [0.0, 1.0]], min_similarity=0.5)
    assert [chunk["chunk_id"] for chunk in semantic] == ["c1"]
    merged = merge_candidate_chunks(
        [{"chunk_id": "c1", "retrieval_source": "LEXICAL"}], semantic, limit=2)
    assert merged[0]["retrieval_source"] == "LEXICAL+SEMANTIC"
    assert merged[0]["semantic_similarity"] == 1.0




class _FakeDb:
    class _Nested:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    def begin_nested(self):
        return self._Nested()

    def execute(self, *args, **kwargs):
        raise RuntimeError("pgvector unavailable in unit test")


def test_worker_semantic_fallback_uses_in_memory_when_pgvector_fails(monkeypatch):
    import app.workers.processor as processor_module
    from app.core.config import settings

    monkeypatch.setattr(settings, "SEMANTIC_RETRIEVAL_ENABLED", True)
    monkeypatch.setattr(settings, "SEMANTIC_MIN_SIMILARITY", 0.1)
    monkeypatch.setattr(settings, "SEMANTIC_TOP_K", 5)
    monkeypatch.setattr(
        processor_module, "get_embedding_provider",
        lambda: HashEmbeddingProvider(dimension=32))
    worker = ProcessingWorker.__new__(ProcessingWorker)
    loop = asyncio.new_event_loop()
    try:
        result = worker._semantic_fallback_chunks(
            _FakeDb(), loop,
            application_id="app-1", document_id="doc-1",
            deterministic_result={
                "chunks": [
                    {"chunk_id": "c1", "text": "Python SQL backend APIs",
                     "page_number": 1, "char_start": 0, "char_end": 25},
                    {"chunk_id": "c2", "text": "Cooking gardening travel",
                     "page_number": 1, "char_start": 26, "char_end": 50},
                ],
                "fallback_chunks": {"crit-1": []},
                "requirement_specs": {
                    "crit-1": {"name": "Backend", "kind": "skill",
                               "terms": [{"label": "Python"}, {"label": "SQL"}]},
                },
            },
            unresolved_criteria=[{"criterion_id": "crit-1"}],
        )
    finally:
        loop.close()
    assert result["crit-1"][0]["chunk_id"] == "c1"
    assert result["crit-1"][0]["retrieval_source"] == "SEMANTIC"


def _ltr_examples(group_count: int = 6, per_group: int = 8):
    examples = []
    for group in range(group_count):
        for rank in range(per_group):
            score = (per_group - rank) / per_group
            label = 3 if rank < 2 else 2 if rank < 4 else 1 if rank < 6 else 0
            examples.append({
                "group_id": f"position-{group}",
                "application_id": f"app-{group}-{rank}",
                "label": label,
                "features": {
                    "matching_score": score,
                    "evidence_coverage": score,
                    "mandatory_match_ratio": score,
                    "mandatory_verified_ratio": score,
                    "nice_to_have_match_ratio": score,
                    "llm_fallback_ratio": 0.0,
                    "verified_evidence_count": float(per_group - rank),
                    "strong_evidence_ratio": score,
                },
            })
    return examples




class _FakeMappingsResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


class _FakeRegistryDb:
    def __init__(self, row):
        self._row = row

    def execute(self, *args, **kwargs):
        return _FakeMappingsResult(self._row)


def test_worker_ltr_registry_requires_approval_for_active(monkeypatch):
    from app.core.config import settings

    artifact = train_ltr_model(
        _ltr_examples(group_count=20), min_examples=30, min_groups=5, epochs=80)
    monkeypatch.setattr(settings, "LTR_MODE", "ACTIVE")
    monkeypatch.setattr(settings, "LTR_MODEL_VERSION", artifact["model_version"])
    monkeypatch.setattr(settings, "LTR_MODEL_PATH", None)
    worker = ProcessingWorker.__new__(ProcessingWorker)

    draft = worker._load_ltr_model(_FakeRegistryDb({"artifact": artifact, "status": "DRAFT"}))
    assert draft is None
    approved = worker._load_ltr_model(
        _FakeRegistryDb({"artifact": artifact, "status": "APPROVED"}))
    assert approved is not None
    assert approved.model_version == artifact["model_version"]


def test_worker_ltr_file_artifact_is_blocked_for_active_in_production(monkeypatch, tmp_path):
    import json

    from app.core.config import settings

    artifact = train_ltr_model(
        _ltr_examples(group_count=20), min_examples=30, min_groups=5, epochs=80)
    artifact_path = tmp_path / "ltr.json"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    monkeypatch.setattr(settings, "LTR_MODE", "ACTIVE")
    monkeypatch.setattr(settings, "LTR_MODEL_VERSION", None)
    monkeypatch.setattr(settings, "LTR_MODEL_PATH", str(artifact_path))
    worker = ProcessingWorker.__new__(ProcessingWorker)

    monkeypatch.setattr(settings, "APP_ENV", "production")
    assert worker._load_ltr_model() is None

    monkeypatch.setattr(settings, "APP_ENV", "staging")
    assert worker._load_ltr_model() is not None


def test_ltr_training_and_group_holdout_metrics():
    artifact = train_ltr_model(_ltr_examples(), min_examples=30, min_groups=5, epochs=80)
    assert artifact["training"]["examples"] == 48
    assert artifact["training"]["groups"] == 6
    assert artifact["training"]["test_groups"] >= 1
    assert artifact["metrics"]["test"]["ndcg_at_10"] > 0.8
    model = LTRModel.from_artifact(artifact)
    high = model.score({"matching_score": 0.95, "evidence_coverage": 0.9})
    low = model.score({"matching_score": 0.1, "evidence_coverage": 0.1})
    assert high > low
    assert model.passes_gates(min_ndcg=0.7, min_pairwise=0.65)


def test_ltr_training_rejects_small_or_single_level_data():
    with pytest.raises(LTRError):
        train_ltr_model(_ltr_examples(group_count=2), min_examples=30, min_groups=5)
    one_level = _ltr_examples()
    for example in one_level:
        example["label"] = 1
    with pytest.raises(LTRError, match="relevance"):
        train_ltr_model(one_level, min_examples=30, min_groups=5)


def test_ltr_features_from_criterion_aggregates():
    features = extract_ranking_features(
        {"matching_score": 80, "evidence_coverage": 0.75, "matching_status": "MEETS_MANDATORY"},
        [
            {"outcome": "MATCH", "decision_source": "RULE",
             "evidence_strength": 0.9, "category": "MUST_HAVE"},
            {"outcome": "NO_MATCH", "decision_source": "LLM",
             "evidence_strength": 0.0, "category": "MUST_HAVE"},
            {"outcome": "MATCH", "decision_source": "RULE",
             "evidence_strength": 0.3, "category": "NICE_TO_HAVE"},
        ],
    )
    assert features["matching_score"] == pytest.approx(0.8)
    assert features["match_rate"] == pytest.approx(2 / 3)
    assert features["no_match_rate"] == pytest.approx(1 / 3)
    assert features["rule_decision_rate"] == pytest.approx(2 / 3)
    assert features["llm_decision_rate"] == pytest.approx(1 / 3)
    assert features["avg_evidence_strength"] == pytest.approx(0.4)
    assert features["mandatory_no_match"] == 1.0
    assert features["meets_mandatory"] == 1.0


def test_ltr_shadow_does_not_change_ranking_and_active_stays_inside_gate():
    engine = MatchingEngine()
    criteria = []
    applications = [
        {"application_id": "b", "latest_assessment": {
            "matching_status": "MEETS_MANDATORY", "matching_score": 80,
            "evidence_coverage": 0.9}},
        {"application_id": "a", "latest_assessment": {
            "matching_status": "MEETS_MANDATORY", "matching_score": 85,
            "evidence_coverage": 0.9}},
        {"application_id": "blocked", "latest_assessment": {
            "matching_status": "POSSIBLE_MISMATCH", "matching_score": 99,
            "evidence_coverage": 1.0}},
    ]
    scores = {"a": 0.1, "b": 0.9, "blocked": 1.0}
    shadow = engine.rank_applications(applications, criteria, ltr_scores=scores, ltr_mode="SHADOW")
    assert [item["application_id"] for item in shadow] == ["a", "b", "blocked"]
    assert shadow[1]["ltr_score"] == 0.9

    active = engine.rank_applications(applications, criteria, ltr_scores=scores, ltr_mode="ACTIVE")
    assert [item["application_id"] for item in active] == ["b", "a", "blocked"]
    assert active[-1]["application_id"] == "blocked"


def test_frontend_types_expose_ltr_score_contract():
    types_file = Path(__file__).resolve().parents[2] / "frontend/src/types/index.ts"
    assert "ltr_score?: number | null" in types_file.read_text(encoding="utf-8")
