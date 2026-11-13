"""
===============================================================================
MODULE: reranking_engine.py
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
LAYER: Backend Retrieval Layer (Dual FlashRank Consensus & MMR Diversity Engine)
===============================================================================

DESCRIPTION:
    This module implements a 2-stage secondary reranking engine for filtering candidate 
    chunks retrieved by hybrid search. Stage 1 executes Dual-Model Cross-Encoder scoring 
    (`ms-marco-TinyBERT-L-2-v2` and `ce-esci-MiniLM-L12-v2`) and pins top consensus chunks. 
    Stage 2 applies Maximal Marginal Relevance (MMR lambda=0.7) over the remaining candidate 
    pool to eliminate semantic redundancy.

KEY RESPONSIBILITIES:
    1. Scoring candidate chunks independently across two cross-encoder models.
    2. Min-max normalizing raw cross-encoder relevance scores to a [0.0, 1.0] interval.
    3. Computing consensus pinning: selecting candidate chunks appearing in the top-5 sets 
       of BOTH cross-encoder models (up to 3 pinned chunks).
    4. Filling remaining result slots using Maximal Marginal Relevance (MMR lambda=0.7) 
       seeded with the embeddings of the consensus-pinned chunks.
    5. Returning the final top_n (5) pristine, non-redundant parent text chunks.

SECURITY & RESILIENCE:
    - Graceful fallback if FlashRank dependency is missing.
    - Graceful fallback to score-sorted candidate selection if MMR embedding generation fails.
    - Emits structured JSON log telemetry when DEBUG mode is enabled.
===============================================================================
"""

import json
import os
import uuid
from datetime import UTC, datetime
from typing import Any

import numpy as np
from langchain_google_genai import GoogleGenerativeAIEmbeddings

try:
    from flashrank import Ranker, RerankRequest  # type: ignore
except ImportError:
    Ranker = None
    RerankRequest = None


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
        "module": "reranking_engine.py",            # Source file name
        "action": action,                           # Log action event title
        "trace_id": trace_id,                       # Request trace ID
        "data": data,                               # Telemetry dictionary payload
    }
    # Print JSON serialized string to standard output stream
    print(json.dumps(log_entry))


def _normalize_scores(scores: list[float]) -> list[float]:
    """
    Applies Min-Max normalization to a list of raw floating-point relevance scores.

    ARGUMENTS:
        scores (list[float]): List of raw model cross-encoder scores.

    RETURNS:
        list[float]: Normalized scores scaled onto a [0.0, 1.0] interval.
    """
    # Check if input scores list is empty
    if not scores:
        return []
    min_s = min(scores)
    max_s = max(scores)
    # Handle edge-case where all scores are identical to prevent division by zero
    if max_s == min_s:
        return [1.0 for _ in scores]
    # Apply Min-Max formula: (score - min) / (max - min)
    return [(s - min_s) / (max_s - min_s) for s in scores]


def _mmr(
    query_embedding: list[float],
    remaining_embeddings: list[list[float]],
    seeded_embeddings: list[list[float]],
    lambda_param: float = 0.7,
    top_n: int = 5,
) -> list[int]:
    """
    Calculates Maximal Marginal Relevance (MMR) over remaining candidate embeddings, 
    seeded with already pinned consensus chunk embeddings.

    ARGUMENTS:
        query_embedding (list[float]): 3072-dim vector embedding of the user search query.
        remaining_embeddings (list[list[float]]): Matrix of 3072-dim embeddings for remaining candidates.
        seeded_embeddings (list[list[float]]): Matrix of 3072-dim embeddings for already pinned chunks.
        lambda_param (float): Trade-off parameter balancing query relevance vs diversity (default 0.7).
        top_n (int): Target number of diverse candidates to select.

    RETURNS:
        list[int]: Indices of selected candidates relative to the remaining_embeddings list.
    """
    # Return empty list early if remaining pool is empty or top_n is non-positive
    if not remaining_embeddings or top_n <= 0:
        return []

    # Convert Python lists to NumPy arrays for vectorized linear algebra
    q_emb = np.array(query_embedding)
    rem_embs = np.array(remaining_embeddings)
    
    # Compute vector L2 norms for cosine similarity denominator
    norm_rem = np.linalg.norm(rem_embs, axis=1)
    norm_q = np.linalg.norm(q_emb)
    # Compute Query Relevance Cosine Similarity vector (sim_q)
    sim_q = np.dot(rem_embs, q_emb) / (norm_rem * norm_q + 1e-9)

    selected_indices: list[int] = []
    unselected = list(range(len(remaining_embeddings)))
    
    # Initialize matrix of selected embeddings with seeded consensus pinned embeddings if present
    if seeded_embeddings:
        sel_embs = np.array(seeded_embeddings)
    else:
        sel_embs = np.empty((0, len(query_embedding)))

    # Iterative selection loop until top_n candidates are picked or unselected pool is exhausted
    while len(selected_indices) < top_n and unselected:
        # Step 1: If no embeddings are in the selected pool yet, pick the candidate with highest query similarity
        if sel_embs.shape[0] == 0:
            best_idx = int(unselected[np.argmax(sim_q[unselected])])
            selected_indices.append(best_idx)
            sel_embs = np.vstack([sel_embs, rem_embs[best_idx]])
            unselected.remove(best_idx)
        else:
            # Step 2: Compute pairwise similarity matrix between unselected candidates and already selected pool
            norm_unsel = np.linalg.norm(rem_embs[unselected], axis=1)
            norm_sel = np.linalg.norm(sel_embs, axis=1)
            sim_d = np.dot(rem_embs[unselected], sel_embs.T) / (
                np.outer(norm_unsel, norm_sel) + 1e-9
            )
            # Find maximum similarity of each unselected candidate to any already selected candidate
            max_sim_d = np.max(sim_d, axis=1)
            
            # Compute MMR score: lambda * Relevance - (1 - lambda) * Redundancy
            mmr_score = (
                lambda_param * sim_q[unselected] - (1 - lambda_param) * max_sim_d
            )
            # Select candidate with the highest MMR score
            best_idx = int(unselected[np.argmax(mmr_score)])
            
            # Append selected index and update tracking matrices
            selected_indices.append(best_idx)
            sel_embs = np.vstack([sel_embs, rem_embs[best_idx]])
            unselected.remove(best_idx)

    return selected_indices


def rerank(
    query: str,
    candidates: list[dict[str, Any]],
    top_n: int = 5,
    trace: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Reranks hybrid search candidates using Dual FlashRank Consensus Pinning and MMR Diversity.

    ARGUMENTS:
        query (str): Input natural language search query string.
        candidates (list[dict[str, Any]]): List of hybrid search candidate chunk dictionaries.
        top_n (int): Number of top reranked chunks to return (default 5).
        trace (dict[str, Any] | None): Optional telemetry trace dictionary.

    RETURNS:
        list[dict[str, Any]]: List of pristine top_n reranked chunk dictionaries.
    """
    # Step 1: Generate unique trace ID for telemetry logging
    trace_id = str(uuid.uuid4())
    log_debug(
        "rerank_started",
        trace_id,
        {"query": query, "candidate_count": len(candidates), "top_n": top_n},
    )

    # Return empty list early if input candidates list is empty
    if not candidates:
        log_debug(
            "rerank_completed",
            trace_id,
            {"returned_count": 0, "reason": "empty_candidates"},
        )
        return []

    # Raise ImportError if FlashRank cross-encoder package is not installed
    if Ranker is None or RerankRequest is None:
        raise ImportError(
            "flashrank is not installed. "
            "Please install it using 'uv add flashrank numpy'"
        )

    # Step 2: Initialize dual cross-encoder ranker models
    ranker1 = Ranker(model_name="ms-marco-TinyBERT-L-2-v2")
    ranker2 = Ranker(model_name="ce-esci-MiniLM-L12-v2")

    # Format passages payload for FlashRank request
    passages = []
    for c in candidates:
        passages.append({
            "id": c["id"],
            "text": c["text"],
            "meta": c.get("metadata", {}),
        })

    # Construct RerankRequest object
    req = RerankRequest(query=query, passages=passages)
    # Execute inference across both cross-encoder models
    res1 = ranker1.rerank(req)
    res2 = ranker2.rerank(req)

    # Extract score lookup dictionaries mapping chunk ID to raw model score
    scores1_dict = {r["id"]: r["score"] for r in res1}
    scores2_dict = {r["id"]: r["score"] for r in res2}

    # Extract ordered raw score arrays matching candidates list order
    raw_scores1 = [scores1_dict.get(c["id"], 0.0) for c in candidates]
    raw_scores2 = [scores2_dict.get(c["id"], 0.0) for c in candidates]

    # Step 3: Min-Max normalize raw scores to [0.0, 1.0] interval
    norm_scores1 = _normalize_scores(raw_scores1)
    norm_scores2 = _normalize_scores(raw_scores2)

    # Step 4: Compute combined average cross-encoder score for each candidate chunk
    for i, c in enumerate(candidates):
        c["score"] = (norm_scores1[i] + norm_scores2[i]) / 2.0
        c["_norm1"] = norm_scores1[i]
        c["_norm2"] = norm_scores2[i]

    # Step 5: Execute Consensus Pinning Logic
    # Find top 5 candidate IDs from Model 1 (TinyBERT)
    m1_sorted = sorted(candidates, key=lambda x: x["_norm1"], reverse=True)
    m1_top5_ids = {c["id"] for c in m1_sorted[:5]}

    # Find top 5 candidate IDs from Model 2 (MiniLM)
    m2_sorted = sorted(candidates, key=lambda x: x["_norm2"], reverse=True)
    m2_top5_ids = {c["id"] for c in m2_sorted[:5]}

    # Find set intersection of candidate IDs agreed upon by both models
    intersection = m1_top5_ids & m2_top5_ids
    
    # Sort consensus intersection chunks by average score descending
    intersection_chunks = [c for c in candidates if c["id"] in intersection]
    intersection_chunks.sort(key=lambda x: x["score"], reverse=True)
    
    # Pin up to top 3 consensus chunks
    pinned_chunks = intersection_chunks[:3]
    pinned_ids = {c["id"] for c in pinned_chunks}

    log_debug(
        "consensus_pinning",
        trace_id,
        {"intersection_count": len(intersection), "pinned_count": len(pinned_chunks)},
    )
    if trace is not None:
        trace["models_run"] = ["ms-marco-TinyBERT-L-2-v2", "ce-esci-MiniLM-L12-v2"]
        trace["chunks_pinned_by_consensus"] = len(pinned_chunks)

    # Step 6: Isolate remaining candidate pool (excluding pinned chunks)
    remaining_pool = [c for c in candidates if c["id"] not in pinned_ids]
    
    # Clean up temporary normalization keys to keep candidate dictionary pure
    for c in candidates:
        c.pop("_norm1", None)
        c.pop("_norm2", None)

    # Calculate exact number of additional chunks needed to fulfill top_n target
    num_needed = top_n - len(pinned_chunks)
    # If consensus pinning already fulfilled or exceeded top_n, return pinned slice immediately
    if num_needed <= 0:
        return pinned_chunks[:top_n]
        
    # If remaining pool is empty, return pinned chunks
    if not remaining_pool:
        return pinned_chunks
        
    # Sort remaining pool by average score descending to seed MMR optimally
    remaining_pool.sort(key=lambda x: x["score"], reverse=True)

    # Step 7: Apply Maximal Marginal Relevance (MMR lambda=0.7) over remaining pool
    try:
        # Initialize Gemini embeddings generator for vector similarity math in MMR
        emb_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        query_emb = emb_model.embed_query(query)
        
        # Embed pinned chunk texts if present
        pinned_embs: list[list[float]] = []
        if pinned_chunks:
            pinned_texts = [p["text"] for p in pinned_chunks]
            pinned_embs = emb_model.embed_documents(pinned_texts)
            
        # Embed remaining pool chunk texts
        remaining_texts = [p["text"] for p in remaining_pool]
        remaining_embs = emb_model.embed_documents(remaining_texts)
        
        # Execute MMR selection algorithm
        selected_indices = _mmr(
            query_embedding=query_emb,
            remaining_embeddings=remaining_embs,
            seeded_embeddings=pinned_embs,
            lambda_param=0.7,
            top_n=num_needed,
        )
        diverse_chunks = [remaining_pool[i] for i in selected_indices]
        log_debug(
            "mmr_applied",
            trace_id,
            {
                "remaining_pool_size": len(remaining_pool),
                "diverse_added": len(diverse_chunks),
            },
        )
    # Fall back to score-sorted candidate selection if embedding generation or MMR fails
    except Exception as e:
        log_debug("mmr_failed_fallback", trace_id, {"error": str(e)})
        diverse_chunks = remaining_pool[:num_needed]

    # Step 8: Combine pinned consensus chunks with MMR diverse chunks and return
    final_results = pinned_chunks + diverse_chunks
    log_debug(
        "rerank_completed",
        trace_id,
        {"returned_count": len(final_results)},
    )
    if trace is not None:
        trace["chunks_added_by_mmr"] = len(diverse_chunks)
    return final_results
