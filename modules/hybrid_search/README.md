# Hybrid Search Module

The **Hybrid Search** module implements Layer 1 (Candidate Retrieval) of the advanced retrieval pipeline for the OmniRAG Enterprise ChatBot system. It fuses **Dense Vector Search** (Pinecone Cosine Distance over 3072-dimensional Gemini embeddings) and **Sparse Keyword Search** (In-Memory Okapi BM25 term frequency scoring) using **Reciprocal Rank Fusion (RRF $k=60$)**.

---

## 🛠️ Technology Stack & Machine Learning Models

### 1. Dense Embedding Model: Google Gemini Embedding 001 (`models/gemini-embedding-001`)
- **What It Does:** Converts natural language query strings into 3072-dimensional dense floating-point vector representations capturing deep semantic relationships, entity intent, and contextual similarity.
- **Why Use It:** Provides state-of-the-art semantic representation, long-context text handling, and 3072-dimensional vector precision required to differentiate subtle enterprise policy nuances (such as distinguishing return refund timelines from warranty replacement rules).
- **Model Inputs:** Raw natural language user search query strings (`query: str`).
- **Model Outputs:** 3072-dimensional dense vector array (`list[float]`).

### 2. Dense Vector Index: Pinecone Serverless Vector Database
- **What It Does:** Stores embedded document chunk vectors and executes high-speed approximate nearest neighbor (ANN) similarity search using Cosine distance metrics.
- **Why Use It:** Delivers sub-50ms query latency on serverless cloud infrastructure without vector index management overhead.
- **Index Inputs:** 3072-dimensional query vector, candidate search limit ($\text{fetch\_k}=50$), and metadata inclusion flags (`include_metadata=True`).
- **Index Outputs:** List of top-50 dense candidate objects containing vector IDs, cosine distance scores, and attached metadata dictionaries (`parent_id`, `parent_text`, `section_title`, `source`, `page_number`).

### 3. Sparse Lexical Search Engine: Okapi BM25
- **What It Does:** Computes probabilistic lexical term frequency ($f(q_i, D)$) and inverse document frequency ($\text{IDF}$) relevance scores across candidate document text passages.
- **Why Use It:** Captures exact keyword matches (such as product part numbers, specialized policy acronyms, and alphanumeric identifiers) that dense semantic embeddings may compress or obscure.
- **Engine Inputs:** Tokenized user search query and extracted candidate document text passages ($N=50$).
- **Engine Outputs:** List of 50 float BM25 relevance scores corresponding to each candidate document text.

### 4. Rank Fusion Engine: Reciprocal Rank Fusion ($k=60$)
- **What It Does:** Merges dense ordinal ranks and sparse ordinal ranks into a single, unified RRF relevance score for each candidate document chunk.
- **Why Use It:** Bypasses scale distortion between raw Cosine similarity scores (ranging from 0.0 to 1.0) and raw BM25 scores (ranging from 0.0 to 25.0), preventing either search modality from dominating the final candidate ranking.
- **Fusion Inputs:** Dense ordinal rank position ($1 \dots 50$) and Sparse ordinal rank position ($1 \dots 50$).
- **Fusion Outputs:** Combined float RRF score ($\text{RRF\_Score} \in [0.0, 0.0333]$) attached to each candidate chunk.

---

## 🧮 Mathematical Formulations

### 1. Okapi BM25 Scoring Algorithm
For an input query $Q$ containing terms $q_1, q_2, \dots, q_n$ and a candidate document text $D$:

$$\text{IDF}(q_i) = \ln \left( 1 + \frac{N - n(q_i) + 0.5}{n(q_i) + 0.5} \right)$$

$$\text{Score}_{\text{BM25}}(D, Q) = \sum_{i=1}^{n} \text{IDF}(q_i) \cdot \frac{f(q_i, D) \cdot (k_1 + 1)}{f(q_i, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avgdl}}\right)}$$

- **$N$:** Total number of candidate documents in the fetched pool ($N=50$).
- **$n(q_i)$:** Document frequency of query term $q_i$ across candidate documents.
- **$f(q_i, D)$:** Term frequency of $q_i$ inside candidate document text $D$.
- **$k_1$:** Term frequency saturation parameter ($k_1 = 1.5$).
- **$b$:** Document length normalization parameter ($b = 0.75$).
- **$\text{avgdl}$:** Average document character length across the candidate set.

### 2. Reciprocal Rank Fusion (RRF $k=60$) Formula
For each candidate chunk $d$ present in both dense and sparse candidate rankings:

$$\text{RRF\_Score}(d) = \frac{1}{60 + \text{Rank}_{\text{dense}}(d)} + \frac{1}{60 + \text{Rank}_{\text{sparse}}(d)}$$

- **$\text{Rank}_{\text{dense}}(d)$:** 1-indexed positional rank of candidate $d$ sorted by Pinecone Cosine similarity score descending.
- **$\text{Rank}_{\text{sparse}}(d)$:** 1-indexed positional rank of candidate $d$ sorted by Okapi BM25 score descending.

---

## 🏗️ Implementation Details & End-to-End Data Pipeline Architecture

The `hybrid_search` module executes a 10-step atomic data pipeline that transforms a user's natural language search query into an RRF-fused, highly relevant top-K document chunk set.

### 🔄 Step-by-Step Atomic Data & Model Pipeline

- **Step 1: Input Validation & Environment Setup**
  - **Inputs:** User query string `query` (e.g., `"What is the refund window?"`), requested candidate count `top_k` (default 10).
  - **Processing:** Validates environment variable `PINECONE_API_KEY`, normalizes `PINECONE_INDEX_NAME` via `.lower().strip()`, and generates a unique UUID `trace_id`. Returns empty list `[]` early if query is empty.
  - **Outputs:** Verified API credentials, trace ID string, normalized target index name `"northwind-gadgets"`.

- **Step 2: Dense Query Embedding Generation**
  - **Inputs:** Cleaned user search query string `query`.
  - **Model Called:** `GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")`.
  - **Processing:** Dispatches the query string to the Google Gemini API to generate a 3072-dimensional floating-point dense vector.
  - **Outputs:** Dense vector query array `query_vector` containing 3072 float values.

- **Step 3: Dense Candidate Vector Search**
  - **Inputs:** 3072-dimensional `query_vector`, expanded candidate limit $\text{fetch\_k} = \text{top\_k} \times 5 = 50$.
  - **Database Called:** Pinecone Serverless Index (`northwind-gadgets`).
  - **Processing:** Executes `index.query(vector=query_vector, top_k=50, include_metadata=True)` using Cosine similarity metrics.
  - **Outputs:** List of up to 50 match objects `matches`, each containing vector `id`, Cosine distance `score`, and metadata dictionary (`parent_id`, `parent_text`, `section_title`, `source`, `page_number`).

- **Step 4: Metadata Text Extraction & Fallback Processing**
  - **Inputs:** Matches array containing 50 candidate objects from Pinecone.
  - **Processing:** Iterates through `matches` and extracts text content using a strict fallback hierarchy: `parent_text` (full parent section text) $\rightarrow$ `text` $\rightarrow$ `section_title` (extracted line 1 header).
  - **Outputs:** Array of 50 candidate document text strings `docs_text: list[str]`.

- **Step 5: Query & Candidate Text Tokenization**
  - **Inputs:** User search query string `query` and candidate text strings `docs_text`.
  - **Function Called:** `tokenize(text: str) -> list[str]`.
  - **Processing:** Replaces periods and commas with spaces, converts text to lowercase, and splits on whitespace into clean term tokens.
  - **Outputs:** Tokenized candidate documents `tokenized_docs: list[list[str]]` and tokenized query `tokenized_query: list[str]`.

- **Step 6: In-Memory Okapi BM25 Lexical Scoring**
  - **Inputs:** `tokenized_query`, `tokenized_docs`, BM25 parameters $k_1 = 1.5, b = 0.75$.
  - **Function Called:** `compute_bm25(query, docs, k1=1.5, b=0.75) -> list[float]`.
  - **Processing:** Calculates Document Frequency (`df`) across candidate set, computes Inverse Document Frequency ($\text{IDF}$), computes length-normalized Term Frequency ($\text{TF}$) per document, and accumulates total BM25 relevance scores.
  - **Outputs:** Array of 50 float BM25 relevance scores `bm25_scores: list[float]`.

- **Step 7: Positional Rank Mapping Generation**
  - **Inputs:** Matches array (representing Dense Ranks 1 to 50) and `bm25_scores` array (representing Sparse Ranks).
  - **Processing:** Maps Dense Rank $\text{Rank}_{\text{dense}}(i)$ directly to positional index $i + 1$. Computes Sparse Ranks by sorting candidate indices by `bm25_scores` descending, mapping original index $i$ to its 1-indexed BM25 position $\text{Rank}_{\text{sparse}}(i)$.
  - **Outputs:** Dual rank mapping dictionaries for all 50 candidate chunks.

- **Step 8: Reciprocal Rank Fusion (RRF $k=60$) Calculation**
  - **Inputs:** Dense Rank $1 \dots 50$, Sparse Rank $1 \dots 50$, fusion constant $k = 60$.
  - **Processing:** Evaluates the RRF formula for each candidate $i$:
    $$\text{RRF\_Score}_i = \frac{1}{60 + \text{Rank}_{\text{dense}}(i)} + \frac{1}{60 + \text{Rank}_{\text{sparse}}(i)}$$
  - **Outputs:** Array of candidate dictionaries updated with fused float `score` attribute (RRF score $\in [0.0, 0.0333]$).

- **Step 9: Candidate Score Sorting & Top-K Truncation**
  - **Inputs:** Array of 50 RRF-scored candidate dictionaries.
  - **Processing:** Sorts candidate list descending by `score` attribute and slices top `top_k` items (`final_candidates = scored_candidates[:top_k]`).
  - **Outputs:** Ranked list of top-10 fused candidate dictionaries containing vector ID, document chunk text, metadata dictionary, and RRF score.

- **Step 10: Telemetry Logging & Response Delivery**
  - **Inputs:** `final_candidates` list length, execution trace, `trace_id`.
  - **Function Called:** `log_debug(action, trace_id, data)`.
  - **Processing:** Emits structured JSON log entry to standard output stream if `DEBUG=true`.
  - **Outputs:** Clean candidate dictionary list returned to caller.

---

## 💻 Implementation Guide & Code Examples

### Executing Hybrid Search in Python
```python
import os
from dotenv import load_dotenv
from app.retrieval.hybrid_search import search

# Load API credentials from environment
load_dotenv()

# Define user query string
query = "What is the return window for defective hardware?"

# Optional: Initialize telemetry dictionary to capture execution metrics
trace_metrics = {}

# Execute hybrid search returning top 10 fused candidate chunks
results = search(query=query, top_k=10, trace=trace_metrics)

# Print telemetry trace summary
print(f"Dense Matches Found: {trace_metrics.get('dense_matches')}")
print(f"Hybrid Candidates Extracted: {trace_metrics.get('hybrid_candidates_extracted')}")

# Iterate and inspect returned top candidate chunks
for rank, candidate in enumerate(results, start=1):
    print(f"\n--- Rank {rank} (RRF Score: {candidate['score']:.6f}) ---")
    print(f"Chunk ID: {candidate['id']}")
    print(f"Source: {candidate['metadata']['source']} (Page {candidate['metadata']['page_number']})")
    print(f"Section Title: {candidate['metadata']['section_title']}")
    print(f"Content: {candidate['text'][:120]}...")
```

---

## 📁 Key System Files & Architecture Map

- **`backend/app/retrieval/hybrid_search.py`:**
  - Implements `search`, `compute_bm25`, `tokenize`, and `log_debug` functions for dense vector retrieval, in-memory BM25 scoring, and RRF rank fusion.

- **`backend/tests/test_hybrid_search.py`:**
  - Integration test suite executing live queries against Pinecone and Gemini APIs.

---

## 🧠 Key Architectural Decisions

- **Simulated Local BM25 Scoring:**
  - **Context:** Pinecone serverless index did not contain native sparse vector values from Phase 0 ingestion.
  - **Decision:** Fetch an expanded dense candidate pool ($\text{fetch\_k}=50$), extract metadata text, and compute BM25 scores in-memory.
  - **Outcome:** Delivers strong hybrid search precision without requiring complex sparse-dense hybrid index setup in Pinecone.

- **Reciprocal Rank Fusion Parameter $k=60$:**
  - **Context:** Direct addition of Cosine similarity scores (0.0 to 1.0) and BM25 scores (0.0 to 25.0) causes scale distortion.
  - **Decision:** Convert raw scores to ordinal ranks and apply RRF with constant $k=60$.
  - **Outcome:** Provides scale-invariant fusion that balances semantic vector matches with exact keyword matches.

- **Index Name Case-Insensitive Normalization:**
  - **Context:** Pinecone index names are strictly lower-case in serverless clusters.
  - **Decision:** Added `.lower().strip()` normalization to `PINECONE_INDEX_NAME` extraction.

---

## 🐛 Technical Issues Encountered & Resolved

- **Vector Dimension Mismatch Error:**
  - **Problem:** Hybrid search queries threw dimensional mismatch exceptions during Pinecone index query calls.
  - **Root Cause:** Migration to `gemini-embedding-001` produced 3072-dimensional query vectors, while the old index was 768 dimensions.
  - **Resolution:** Re-triggered data ingestion to rebuild the Pinecone index with explicit `dimension=3072`.

- **Index Name Case Sensitivity Bug:**
  - **Problem:** Pinecone client threw `NotFoundException` when querying index target specified in `.env`.
  - **Root Cause:** Environment variable contained `OmniRAG` while Pinecone index was registered as `omnirag`.
  - **Resolution:** Updated `hybrid_search.py` to enforce `.lower().strip()` on environment variables.

---

## 💡 Real-World Workflow Examples

- **Scenario 1: Inquiring About Return Policy Window**
  - **User Query:** *"What is the refund window?"*
  - **Processing Flow:**
    - Query embedded into 3072-dimensional vector via Gemini.
    - Pinecone returns 50 candidate vectors matching semantic concepts ("return", "refund", "policy").
    - BM25 calculates term frequency scores for exact keywords ("refund", "window").
    - RRF combines Dense Rank (e.g., Rank 1) and Sparse Rank (e.g., Rank 3) yielding RRF Score $0.0322$.
  - **Outcome:** Returns top 10 ranked chunks containing exact policy refund timeframes.

- **Scenario 2: Technical Product Inquiry**
  - **User Query:** *"Webcam driver compatibility issue"*
  - **Processing Flow:**
    - Dense vector matches broad hardware sections ("accessories", "video cameras").
    - Sparse BM25 boosts specific candidate chunks containing exact keyword terms ("webcam", "driver", "compatibility").
    - RRF fuses semantic and exact matches.
  - **Outcome:** Pushes exact technical troubleshooting passage to Rank 1.
