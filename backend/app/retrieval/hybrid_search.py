"""
===============================================================================
MODULE: hybrid_search.py
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
LAYER: Backend Retrieval Layer (Hybrid Dense + Sparse Search & RRF)
===============================================================================

DESCRIPTION:
    This module implements the initial candidate retrieval engine combining 
    Dense Vector Search (Pinecone Cosine Distance over 3072-dim Gemini embeddings) 
    and Sparse Keyword Search (In-Memory BM25). Ranks are fused using Reciprocal 
    Rank Fusion (RRF k=60).

KEY RESPONSIBILITIES:
    1. Converting input user queries into 3072-dimensional dense vector embeddings.
    2. Querying Pinecone Serverless index for top-50 dense candidate chunks (fetch_k = top_k * 5).
    3. Tokenizing candidate document texts and computing in-memory BM25 term frequency scores.
    4. Fusing dense and sparse ranks via Reciprocal Rank Fusion:
       RRF_Score = (1 / (60 + Dense_Rank)) + (1 / (60 + Sparse_Rank))
    5. Sorting merged candidate chunks by RRF score descending and returning top_k candidates.

SECURITY & RESILIENCE:
    - Environment variable validation for PINECONE_API_KEY.
    - Emits structured JSON log telemetry when DEBUG mode is enabled.
===============================================================================
"""

import json
import math
import os
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pinecone import Pinecone


def log_debug(action: str, trace_id: str, data: dict[str, Any]) -> None:
    """
    Emits structured JSON log entries to stdout when DEBUG mode is enabled.

    ARGUMENTS:
        action (str): Identifier for the logged event/step.
        trace_id (str): Unique UUID trace identifier for request tracking.
        data (dict[str, Any]): Arbitrary key-value telemetry data to serialize.

    RETURNS:
        None: Side-effect logger that prints to stdout.
    """
    # Check if DEBUG environment variable is set to "true" (case-insensitive)
    if os.getenv("DEBUG", "false").lower() != "true":
        return
    # Construct standardized structured log dictionary
    log_entry = {
        "timestamp": datetime.now(UTC).isoformat(),  # ISO-8601 UTC timestamp string
        "module": "hybrid_search.py",                # Source file name
        "action": action,                           # Log action event title
        "trace_id": trace_id,                       # Request trace ID
        "data": data                                # Telemetry dictionary payload
    }
    # Print JSON serialized string to standard output stream
    print(json.dumps(log_entry))


def tokenize(text: str) -> list[str]:
    """
    Normalizes and tokenizes a text string into lowercase term tokens.

    ARGUMENTS:
        text (str): Input text string to tokenize.

    RETURNS:
        list[str]: A list of cleaned, lowercased word token strings.
    """
    # Check if input text string is empty or None
    if not text:
        return []
    # Replace punctuation dots and commas with spaces, convert to lowercase, and split by whitespace
    return text.lower().replace(".", " ").replace(",", " ").split()


def compute_bm25(
    query: str, docs: list[str], k1: float = 1.5, b: float = 0.75
) -> list[float]:
    """
    Computes Okapi BM25 relevance scores for a query across a candidate list of document texts.

    ARGUMENTS:
        query (str): Input natural language search query string.
        docs (list[str]): List of candidate document text strings.
        k1 (float): BM25 term frequency saturation parameter (default 1.5).
        b (float): BM25 document length normalization parameter (default 0.75).

    RETURNS:
        list[float]: List of float BM25 relevance scores corresponding to each input document.
    """
    # Step 1: Tokenize all candidate document texts and input query string
    tokenized_docs = [tokenize(d) for d in docs]
    tokenized_query = tokenize(query)
    
    # Step 2: Compute total document count and average document length across candidate set
    n_docs = len(tokenized_docs)
    avgdl = sum(len(d) for d in tokenized_docs) / n_docs if n_docs > 0 else 0
    
    # Step 3: Compute Document Frequency (DF) for each unique token term across all candidate documents
    df: Counter[str] = Counter()
    for doc in tokenized_docs:
        # Update counter with set of unique terms present in doc (prevents double counting per doc)
        df.update(set(doc))
        
    # Step 4: Compute BM25 score for each document
    scores: list[float] = []
    for doc in tokenized_docs:
        doc_len = len(doc)
        doc_freqs = Counter(doc)
        score = 0.0
        # Iterate over each term token in the user search query
        for q_term in tokenized_query:
            # Skip query terms that do not appear in any candidate document
            if q_term not in df:
                continue
            # Compute Inverse Document Frequency (IDF) using Robertson-Spärck Jones formula variant
            idf = math.log(1 + (n_docs - df[q_term] + 0.5) / (df[q_term] + 0.5))
            # Get term frequency (TF) in current document
            tf = doc_freqs[q_term]
            # Compute numerator and length-normalized denominator for BM25 term weight
            num = tf * (k1 + 1)
            den = tf + k1 * (1 - b + b * (doc_len / avgdl)) if avgdl > 0 else tf + k1
            # Accumulate term contribution into document BM25 score
            score += idf * (num / den)
        scores.append(score)
    return scores


def search(
    query: str, top_k: int = 10, trace: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """
    Executes hybrid search combining Pinecone dense vector search and BM25 sparse keyword search via RRF.

    ARGUMENTS:
        query (str): Input natural language search query string.
        top_k (int): Number of top fused candidate chunks to return (default 10).
        trace (dict[str, Any] | None): Optional dictionary to capture search telemetry traces.

    RETURNS:
        list[dict[str, Any]]: List of top candidate chunk dictionaries containing 'id', 'text',
                             'metadata', and 'score' (RRF score).
    """
    # Step 1: Generate unique trace ID for telemetry logging
    trace_id = str(uuid.uuid4())
    log_debug("search_started", trace_id, {"query": query, "top_k": top_k})
    
    # Step 2: Validate Pinecone credentials and environment configuration
    api_key = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv("PINECONE_INDEX_NAME", "omnirag").lower()
    
    if not api_key:
        raise ValueError("PINECONE_API_KEY environment variable not set")
    
    # Step 3: Initialize Pinecone client and index connection
    pc = Pinecone(api_key=api_key)
    index = pc.Index(index_name)
    
    # Step 4: Initialize Gemini Embeddings wrapper for gemini-embedding-001 model (3072 dim)
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    
    # Return empty list early if query string is empty or whitespace
    if not query.strip():
        return []
    
    # Step 5: Generate 3072-dimensional dense vector embedding for user query
    query_vector = embeddings.embed_query(query)
    
    # Step 6: Query Pinecone for top dense candidates (fetch_k = top_k * 5 = 50 candidates)
    fetch_k = top_k * 5
    res = index.query(
        vector=query_vector,
        top_k=fetch_k,
        include_metadata=True
    )
    
    matches = res.get("matches", [])
    # Return empty list early if zero dense matches were returned from Pinecone
    if not matches:
        log_debug("dense_search_completed", trace_id, {"matches_found": 0})
        if trace is not None:
            trace["dense_matches"] = 0
            trace["hybrid_candidates_extracted"] = 0
        return []
        
    log_debug("dense_search_completed", trace_id, {"matches_found": len(matches)})
    if trace is not None:
        trace["dense_matches"] = len(matches)
    
    # Step 7: Extract document texts from metadata for local BM25 score calculation
    docs_text: list[str] = []
    for match in matches:
        meta = match.get("metadata", {})
        # Fallback hierarchy for text extraction: parent_text -> text -> section_title
        text = meta.get("parent_text", meta.get("text", meta.get("section_title", "")))
        docs_text.append(str(text))
        
    # Step 8: Compute BM25 sparse keyword scores for all candidate document texts
    bm25_scores = compute_bm25(query, docs_text)
    
    # Step 9: Compute Sparse Rank positions (1-indexed) by sorting BM25 scores descending
    sparse_ranked_indices = sorted(
        range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True
    )
    sparse_ranks = {
        orig_idx: rank + 1 for rank, orig_idx in enumerate(sparse_ranked_indices)
    }
    
    # Step 10: Apply Reciprocal Rank Fusion (RRF) with constant k = 60
    # Formula: RRF_Score = (1 / (60 + Dense_Rank)) + (1 / (60 + Sparse_Rank))
    rrf_k = 60
    scored_candidates: list[dict[str, Any]] = []
    for i, match in enumerate(matches):
        dense_rank = i + 1              # Dense rank based on Pinecone Cosine distance order
        sparse_rank = sparse_ranks[i]    # Sparse rank based on BM25 score order
        
        # Calculate RRF score
        rrf_score = (1 / (rrf_k + dense_rank)) + (1 / (rrf_k + sparse_rank))
        
        meta = match.get("metadata", {})
        text = meta.get("parent_text", meta.get("text", meta.get("section_title", "")))
        
        scored_candidates.append({
            "id": match["id"],
            "text": str(text),
            "metadata": meta,
            "score": rrf_score
        })
        
    # Step 11: Sort merged candidate list by RRF score descending
    scored_candidates.sort(key=lambda x: x["score"], reverse=True)
    
    # Slice top_k candidates (top 10) for downstream reranking
    final_candidates = scored_candidates[:top_k]
    log_debug("search_completed", trace_id, {"returned_count": len(final_candidates)})
    if trace is not None:
        trace["hybrid_candidates_extracted"] = len(final_candidates)
    return final_candidates
