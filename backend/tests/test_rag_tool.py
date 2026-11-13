"""
===============================================================================
MODULE: test_rag_tool.py
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
LAYER: Backend Test Suite Layer (RAG Tool Unit Tests)
===============================================================================

DESCRIPTION:
    Unit tests for the RAG search tool wrapper (`rag_tool.py`). Validates document 
    retrieval, citation formatting (`source - section_title`), LangChain tool invocation, 
    and ImportError exception propagation.

KEY RESPONSIBILITIES:
    1. Testing `run_rag_search` output context and citations.
    2. Testing `rag_search_tool` LangChain Tool export and `invoke()` behavior.
    3. Testing `run_rag_search_importerror` fallback when reranking engine raises ImportError.
===============================================================================
"""

import os
from typing import Any

import pytest

from app.retrieval import reranking_engine
from app.tools.rag_tool import rag_search_tool, run_rag_search


def test_run_rag_search_valid() -> None:
    """Test executing a valid RAG search against policy PDF documents."""
    pinecone_key = os.getenv("PINECONE_API_KEY")
    if not pinecone_key or "mock" in pinecone_key.lower():
        pytest.skip("Valid PINECONE_API_KEY is not set. Skipping retrieval test.")

    query = "What is the refund window?"
    print(f"\n[test_run_rag_search_valid] Query: {query}")
    
    # Execute RAG search
    result_str = run_rag_search(query)
    import json
    result = json.loads(result_str)
    
    # Assert JSON payload structure
    assert isinstance(result, dict)
    assert "context" in result
    assert "citations" in result
    
    # Assert context text and citations lists are populated
    assert len(result["context"]) > 0
    assert len(result["citations"]) > 0
    
    # Assert citation string formatting ('source.pdf - section')
    for citation in result["citations"]:
        assert " - " in citation
        assert ".pdf" in citation
        
    # Assert context block formatting includes numeric citation header
    assert "[Citation:" in result["context"]


def test_rag_tool_export() -> None:
    """Test the LangChain tool metadata and invoke() interface."""
    assert rag_search_tool.name == "rag_search"
    assert "Search Northwind Gadgets policy documents" in rag_search_tool.description
    
    pinecone_key = os.getenv("PINECONE_API_KEY")
    if not pinecone_key or "mock" in pinecone_key.lower():
        pytest.skip("Valid PINECONE_API_KEY is not set. Skipping retrieval test.")
        
    query = "How many days of annual leave do employees get?"
    print(f"\n[test_rag_tool_export] Query: {query}")
    
    # Execute tool via invoke() interface
    result_str = rag_search_tool.invoke({"query": query})
    import json
    result = json.loads(result_str)
    assert isinstance(result, dict)
    assert "context" in result
    assert "citations" in result
    assert len(result["citations"]) > 0


def test_run_rag_search_importerror(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test clean error propagation when reranking_engine raises ImportError.
    Uses monkeypatch to simulate FlashRank failure on CPU.
    """
    def mock_search(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return [{
            "id": "1",
            "text": "dummy text",
            "metadata": {"source": "doc.pdf", "section_title": "sec"},
            "score": 0.9,
        }]
    monkeypatch.setattr("app.retrieval.hybrid_search.search", mock_search)
    
    def mock_rerank(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        raise ImportError("FlashRank failed to load on CPU")
        
    # Monkeypatch reranking_engine.rerank with failing mock function
    monkeypatch.setattr(reranking_engine, "rerank", mock_rerank)
    
    # Execute RAG search and verify error payload returned
    result_str = run_rag_search("test query")
    import json
    result = json.loads(result_str)
    assert isinstance(result, dict)
    assert "error" in result
    assert "FlashRank failed to load" in result["error"]
