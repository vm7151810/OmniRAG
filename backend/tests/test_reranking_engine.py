"""
===============================================================================
MODULE: test_reranking_engine.py
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
LAYER: Backend Test Suite Layer (Reranking Engine Unit Tests)
===============================================================================

DESCRIPTION:
    Unit tests for secondary reranking engine (`reranking_engine.py`). 
    Validates Min-Max score normalization guards, Maximal Marginal Relevance 
    (MMR) candidate diversity selection, consensus pinning, and telemetry logging.

KEY RESPONSIBILITIES:
    1. Testing `_normalize_scores` zero-variance guard and scaling onto [0.0, 1.0].
    2. Testing `_mmr` seeding logic with pinned consensus chunk embeddings.
    3. Testing `rerank` candidate output count, deduplication, and empty candidate fallback.
    4. Testing structured JSON telemetry logging when DEBUG=true.
===============================================================================
"""

import json
from typing import Any

import pytest

from app.retrieval.reranking_engine import _mmr, _normalize_scores, rerank


@pytest.fixture
def sample_candidates() -> list[dict[str, Any]]:
    """Fixture generating a list of 6 sample candidate dictionaries for reranking tests."""
    return [
        {"id": str(i), "text": f"Sample document text {i}", "metadata": {}, "score": 0.0}
        for i in range(1, 7)
    ]


def test_normalization_guard() -> None:
    """Test Min-Max score normalization zero-variance safety and scaling math."""
    # Test zero variance scores (all scores identical) -> returns all 1.0
    scores = [0.5, 0.5, 0.5]
    norm = _normalize_scores(scores)
    assert norm == [1.0, 1.0, 1.0]
    
    # Test standard min-max scaling ([0.0, 5.0, 10.0] -> [0.0, 0.5, 1.0])
    scores2 = [0.0, 5.0, 10.0]
    norm2 = _normalize_scores(scores2)
    assert norm2 == [0.0, 0.5, 1.0]


def test_mmr_seeding() -> None:
    """Test MMR selection seeded with already pinned consensus chunk embeddings."""
    # Define query vector pointing along x-axis
    q_emb = [1.0, 0.0]
    # Remaining candidate 0 is identical to query [1.0, 0.0], candidate 1 is orthogonal/diverse [0.5, 0.866]
    rem_embs = [[1.0, 0.0], [0.5, 0.866]]
    # Seeded pinned embedding is already identical to candidate 0 [1.0, 0.0]
    seeded_embs = [[1.0, 0.0]]
    
    # Execute _mmr with lambda 0.1 to heavily favor diversity over redundancy
    selected = _mmr(q_emb, rem_embs, seeded_embs, lambda_param=0.1, top_n=1)
    
    # Verify candidate 1 is selected due to diversity penalty on candidate 0
    assert selected == [1]


def test_rerank_basic(sample_candidates: list[dict[str, Any]]) -> None:
    """Test basic reranking workflow returning top_n candidates without duplicates."""
    query = "Test query for reranking"
    results = rerank(query, sample_candidates, top_n=4)
    assert len(results) == 4
    
    # Assert zero duplicate IDs exist in returned list
    ids = [r["id"] for r in results]
    assert len(ids) == len(set(ids))


def test_rerank_empty() -> None:
    """Test reranking fallback behavior when passed an empty candidate list."""
    assert rerank("test", [], top_n=5) == []


def test_atomic_logging(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    sample_candidates: list[dict[str, Any]],
) -> None:
    """Test structured JSON telemetry log output when DEBUG=true."""
    monkeypatch.setenv("DEBUG", "true")
    rerank("test", sample_candidates[:1], top_n=1)
    
    captured = capsys.readouterr()
    lines = captured.out.strip().split('\n')
    found_log = False
    for line in lines:
        if not line.strip():
            continue
        try:
            log_obj = json.loads(line)
            if log_obj.get("module") == "reranking_engine.py":
                assert "timestamp" in log_obj
                found_log = True
        except json.JSONDecodeError:
            continue
    assert found_log
