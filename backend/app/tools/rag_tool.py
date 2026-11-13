"""
===============================================================================
MODULE: rag_tool.py
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
LAYER: Backend Tools Layer (RAG Tool)
===============================================================================

DESCRIPTION:
    This module provides the LangChain tool wrapper (`rag_search_tool`) and 
    execution engine (`run_rag_search`) for performing Unstructured Document RAG 
    retrieval across corporate policy PDFs.

KEY RESPONSIBILITIES:
    1. Interfacing with `hybrid_search.py` to retrieve top-50 dense vector and 
       sparse BM25 candidates via Reciprocal Rank Fusion (RRF k=60).
    2. Interfacing with `reranking_engine.py` to filter candidates via 
       Dual FlashRank Cross-Encoder consensus pinning and Maximal Marginal Relevance (MMR lambda=0.7).
    3. Constructing ordered, non-duplicate citation lists and formatted text context blocks.
    4. Returning stringified JSON payloads containing context, citations, and retrieval telemetry traces.

SECURITY & RESILIENCE:
    - Wraps all operations in safe try-except blocks to prevent agent execution crashes.
    - Emits structured JSON log entries when DEBUG mode is enabled.
===============================================================================
"""

import json
import os
import re
from datetime import UTC, datetime
from typing import Any

from langchain_core.tools import tool

from app.retrieval import hybrid_search, reranking_engine


def atomic_log(action: str, data: dict[str, Any]) -> None:
    """
    Emits structured JSON log entries to stdout when DEBUG mode is enabled.

    ARGUMENTS:
        action (str): Identifier for the logged event/step.
        data (dict[str, Any]): Arbitrary key-value telemetry data to serialize.

    RETURNS:
        None: Side-effect logger that prints to stdout.
    """
    # Check if the environment variable DEBUG is explicitly set to string "true"
    if os.getenv("DEBUG") == "true":
        # Construct a standardized structured JSON log dictionary
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),  # ISO-8601 UTC timestamp string
            "module": "rag_tool.py",                     # Source file name for tracing
            "action": action,                           # Log action event title
            "trace_id": "N/A",                          # Optional trace ID placeholder
            "data": data                                # Telemetry dictionary payload
        }
        # Print JSON serialized string to standard output stream
        print(json.dumps(log_entry))


def run_rag_search(query: str) -> str:
    """
    Executes the full RAG pipeline by querying the hybrid search and reranking engines.

    ARGUMENTS:
        query (str): The natural language query string from the user or agent.

    RETURNS:
        str: A JSON-serialized string containing three keys:
             - 'context': The formatted text passages from matching policy documents.
             - 'citations': A list of unique document section citations.
             - 'trace': Telemetry information regarding candidate counts and reranking scores.
    """
    # Log the initiation of the RAG search pipeline with the raw query string
    atomic_log("run_rag_search_start", {"query": query})
    
    try:
        # Step 1: Initialize an empty dictionary to capture retrieval telemetry data
        trace_data: dict[str, Any] = {}
        
        # Step 1.1: Execute Hybrid Search (Dense Pinecone Cosine + Local BM25 fused with RRF k=60)
        # Retrieves top 10 candidates from the vector store for initial filtering
        candidates = hybrid_search.search(query, top_k=10, trace=trace_data)
        
        # Step 2: Pass candidates through Dual-Model Reranker (FlashRank consensus + MMR diversity)
        # Selects top 5 non-redundant pristine parent text chunks for the LLM context window
        chunks = reranking_engine.rerank(query, candidates, top_n=5, trace=trace_data)
        
        # Step 3: Initialize accumulator mapping for unique document citations and text context blocks
        unique_citations: list[str] = []
        citation_details: list[dict[str, Any]] = []
        citation_map: dict[str, int] = {}
        context_blocks: list[str] = []
        
        # Iterate over each reranked chunk object returned by the reranking engine
        for chunk in chunks:
            # Safely fetch the metadata dictionary from the chunk (defaults to empty dict if missing)
            meta = chunk.get("metadata", {})
            
            # Extract PDF source filename from metadata (defaults to 'unknown.pdf')
            source = meta.get("source", "unknown.pdf")
            
            # Extract markdown section title from metadata, stripping trailing digits (e.g. "Policy 1.")
            raw_section = meta.get("section_title", "Unknown Section")
            section = re.sub(r'[\s\d\.]+$', '', raw_section)
            
            # Extract parent text snippet from chunk object
            text = chunk.get("text", "")
            
            # Format raw citation string as 'filename.pdf - Section Title'
            raw_citation = f"{source} - {section}"
            
            # Check if this raw citation has already been assigned a numeric ID
            if raw_citation not in citation_map:
                # Assign the next sequential integer ID (1-indexed)
                new_id = len(citation_map) + 1
                citation_map[raw_citation] = new_id
                # Append the formatted raw citation string to the unique array
                unique_citations.append(raw_citation)
                # Append structured citation details for enhanced UI rendering
                parent_snippet = meta.get("parent_text", text)
                clean_excerpt = parent_snippet.strip()[:350] + ("..." if len(parent_snippet.strip()) > 350 else "")
                citation_details.append({
                    "id": new_id,
                    "source": source,
                    "title": section,
                    "page": meta.get("page_number", 1),
                    "excerpt": clean_excerpt,
                    "url": f"/policies/{source}"
                })
            
            # Retrieve the numeric ID assigned to this chunk's citation
            citation_id = citation_map[raw_citation]
            
            # Format context text block with numeric citation header and quoted text passage
            context_blocks.append(f"[Citation: {citation_id}]\n\"{text}\"")
            
        # Combine all individual context blocks into a single double-newline separated string
        context_str = "\n\n".join(context_blocks)
        
        # Log successful completion of RAG search along with chunk count and unique citations
        atomic_log(
            "run_rag_search_success",
            {"num_chunks": len(chunks), "citations": unique_citations},
        )
        
        # Return JSON serialized dictionary containing context, citations, and telemetry trace
        return json.dumps({
            "context": context_str,
            "citations": unique_citations,
            "citation_details": citation_details,
            "trace": trace_data
        })
        
    # Catch ImportError explicitly if optional search dependencies fail to load
    except ImportError as e:
        # Log error event details to stdout
        atomic_log("run_rag_search_error", {"error": str(e)})
        # Return JSON string payload containing error message
        return json.dumps({
            "error": str(e)
        })
        
    # Catch all generic exceptions during retrieval to prevent agent execution crashes
    except Exception as e:
        # Log unexpected error details to stdout
        atomic_log("run_rag_search_error", {"error": str(e)})
        # Return JSON string payload containing error message
        return json.dumps({
            "error": str(e)
        })


@tool("rag_search")
def rag_search_tool(query: str) -> str:
    """
    Search Northwind Gadgets policy documents (HR leave, product FAQ, returns 
    and refunds, warranty, pricing and discounts). Use for questions about 
    company policies, procedures, eligibility criteria, or how processes work.

    ARGUMENTS:
        query (str): The natural language policy search query string.

    RETURNS:
        str: JSON serialized string payload containing policy text context and citations.
    """
    # Delegates execution directly to the underlying run_rag_search engine function
    return run_rag_search(query)
