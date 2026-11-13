"""
===============================================================================
MODULE: test_hybrid_search.py
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
LAYER: Backend Test Suite Layer (Hybrid Search Tests)
===============================================================================

DESCRIPTION:
    Integration tests for `hybrid_search.py`. Validates dense Pinecone vector 
    retrieval combined with in-memory BM25 sparse search and Reciprocal Rank Fusion (RRF k=60).

KEY RESPONSIBILITIES:
    1. Testing hybrid search execution on real policy questions ('What is the return policy?').
    2. Asserting structure of returned candidate dictionaries ('id', 'text', 'metadata', 'score').
    3. Testing empty string query fallback handling.
===============================================================================
"""

import os

import pytest
from dotenv import load_dotenv

from app.retrieval.hybrid_search import search

load_dotenv()


def test_hybrid_search() -> None:
    """Test hybrid search against real Pinecone index and Gemini embedding API."""
    pinecone_key = os.getenv("PINECONE_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")
    if not pinecone_key or "mock" in pinecone_key.lower() or not google_key or "mock" in google_key.lower():
        pytest.skip("Valid API keys not set for real integration test")
    
    query = "What is the return policy?"
    results = search(query, top_k=2)
    
    # Assert candidate list return structure
    assert isinstance(results, list)
    assert len(results) > 0
    assert len(results) <= 2
    
    # Assert candidate dictionary keys
    first_result = results[0]
    assert "id" in first_result
    assert "text" in first_result
    assert "metadata" in first_result
    assert "score" in first_result
    
    # Assert data types
    assert isinstance(first_result["text"], str)
    assert isinstance(first_result["score"], float)


def test_hybrid_search_empty_query() -> None:
    """Test hybrid search behavior when passed an empty query string."""
    pinecone_key = os.getenv("PINECONE_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")
    if not pinecone_key or "mock" in pinecone_key.lower() or not google_key or "mock" in google_key.lower():
        pytest.skip("Valid API keys not set for real integration test")
    
    results = search("", top_k=2)
    assert isinstance(results, list)
