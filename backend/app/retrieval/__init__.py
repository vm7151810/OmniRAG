"""
===============================================================================
PACKAGE: app.retrieval
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
===============================================================================

DESCRIPTION:
    Package initializer for backend retrieval engine components.

EXPORTS:
    - ingest: Parent-child PDF chunking and Pinecone vector ingestion module.
    - hybrid_search: Dense Pinecone + Sparse BM25 RRF search module.
    - reranking_engine: Dual FlashRank cross-encoder consensus & MMR diversity module.
===============================================================================
"""

from app.retrieval import hybrid_search, ingest, reranking_engine

__all__ = ["ingest", "hybrid_search", "reranking_engine"]
