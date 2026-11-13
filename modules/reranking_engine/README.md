# Reranking Engine Module

The **Reranking Engine** module implements Layer 2 (Consensus Filtering) and Layer 3 (Seeded Diversity Selection) of the advanced retrieval pipeline for the OmniRAG Enterprise ChatBot system. It refines candidate chunks from hybrid search using **Dual Cross-Encoder Consensus Pinning** (`ms-marco-TinyBERT-L-2-v2` and `ce-esci-MiniLM-L12-v2`) and **Maximal Marginal Relevance (MMR $\lambda=0.7$)** seeded with pinned chunk embeddings to eliminate semantic redundancy.

---

## 🛠️ Technology Stack & Machine Learning Models

### 1. Cross-Encoder Model 1: `ms-marco-TinyBERT-L-2-v2` (via FlashRank)
- **What It Does:** Evaluates deep token-level joint cross-attention between the query string and candidate document chunk text to compute raw semantic relevance scores.
- **Why Use It:** Provides high-speed, general-domain semantic relevance scoring optimized for lightweight CPU execution.
- **Model Inputs:** Query string (`query: str`) and candidate passages payload (`passages: list[dict]`).
- **Model Outputs:** Raw floating-point relevance scores per candidate document chunk.

### 2. Cross-Encoder Model 2: `ce-esci-MiniLM-L12-v2` (via FlashRank)
- **What It Does:** Evaluates joint cross-attention relevance specifically trained on e-commerce search and customer inquiry datasets.
- **Why Use It:** Adds domain-specific relevance validation for order statuses, product specifications, and transactional inquiries.
- **Model Inputs:** Query string (`query: str`) and candidate passages payload (`passages: list[dict]`).
- **Model Outputs:** Raw floating-point e-commerce relevance scores per candidate document chunk.

### 3. Diversity Engine: Seeded Maximal Marginal Relevance (MMR $\lambda=0.7$)
- **What It Does:** Selects candidate document chunks from the remaining pool by balancing query vector similarity against semantic redundancy relative to already pinned consensus chunks.
- **Why Use It:** Prevents the system from returning duplicate or near-identical policy paragraphs, ensuring that the final candidate set covers diverse aspects of the user inquiry.
- **Engine Inputs:** 3072-dimensional query vector, 3072-dimensional remaining candidate embeddings, 3072-dimensional seeded pinned embeddings, and trade-off parameter $\lambda = 0.7$.
- **Engine Outputs:** List of selected candidate indices guaranteeing global semantic diversity.

---

## 🧮 Mathematical Formulations

### 1. Min-Max Score Normalization Formula
For a list of raw cross-encoder scores $S = [s_1, s_2, \dots, s_n]$:

$$\text{Norm\_Score}_i = \begin{cases} 1.0 & \text{if } S_{\text{max}} = S_{\text{min}} \\ \frac{s_i - S_{\text{min}}}{S_{\text{max}} - S_{\text{min}}} & \text{otherwise} \end{cases}$$

- **$S_{\text{min}}$:** Minimum raw score across the candidate set.
- **$S_{\text{max}}$:** Maximum raw score across the candidate set.
- **Zero-Variance Guard:** If $S_{\text{max}} = S_{\text{min}}$, assigns $1.0$ to prevent division by zero.

### 2. Combined Average Consensus Score
For each candidate chunk $d$:

$$\text{Score}_{\text{avg}}(d) = \frac{\text{Norm\_Score}_{\text{TinyBERT}}(d) + \text{Norm\_Score}_{\text{MiniLM}}(d)}{2}$$

### 3. Seeded Maximal Marginal Relevance (MMR $\lambda=0.7$) Formula
For selecting the next candidate chunk $d$ from the remaining unselected pool $U$, given the already selected set $S$ (initialized with pinned consensus chunk embeddings $S_{\text{pinned}}$):

$$\text{MMR\_Score}(d) = \lambda \cdot \text{Sim}(d, Q) - (1 - \lambda) \cdot \max_{d_s \in S} \text{Sim}(d, d_s)$$

- **$\text{Sim}(d, Q)$:** Cosine similarity between candidate embedding $d$ and query embedding $Q$.
- **$\text{Sim}(d, d_s)$:** Cosine similarity between candidate embedding $d$ and already selected/pinned embedding $d_s$.
- **$\lambda = 0.7$:** Trade-off parameter weighting query relevance ($70\%$) against diversity ($30\%$).

---

## 🏗️ Implementation Details & End-to-End Data Pipeline Architecture

The `reranking_engine` module executes an 8-step atomic data pipeline that transforms candidate chunks into a refined top-N set.

### 🔄 Step-by-Step Atomic Data & Model Pipeline

- **Step 1: Input Validation & Trace Initialization**
  - **Inputs:** User search query `query`, candidate chunks list `candidates` ($N=10$), target output count `top_n` (default 5).
  - **Processing:** Validates environment parameters, generates unique UUID `trace_id`, and verifies FlashRank SDK availability. Returns `[]` if `candidates` is empty.
  - **Outputs:** Trace ID string and verified input payload.

- **Step 2: Dual Cross-Encoder Scoring**
  - **Inputs:** Candidate passages payload `passages`.
  - **Models Called:** `Ranker(model_name="ms-marco-TinyBERT-L-2-v2")` and `Ranker(model_name="ce-esci-MiniLM-L12-v2")`.
  - **Processing:** Formulates `RerankRequest` and dispatches inference across both FlashRank cross-encoder models concurrently on CPU.
  - **Outputs:** Two raw score dictionaries `scores1_dict` and `scores2_dict`.

- **Step 3: Min-Max Score Normalization**
  - **Inputs:** Raw score arrays `raw_scores1` and `raw_scores2`.
  - **Function Called:** `_normalize_scores(scores: list[float]) -> list[float]`.
  - **Processing:** Applies Min-Max scaling onto $[0.0, 1.0]$ with zero-variance safeguards.
  - **Outputs:** Normalized score arrays `norm_scores1` and `norm_scores2`.

- **Step 4: Average Score Calculation**
  - **Inputs:** `norm_scores1` and `norm_scores2`.
  - **Processing:** Computes average score `c["score"] = (norm1 + norm2) / 2.0` for every candidate chunk.
  - **Outputs:** Candidate dictionaries updated with unified float `score` attribute.

- **Step 5: Top-5 Set Extraction & Consensus Intersection**
  - **Inputs:** Candidates list with model-specific normalized scores.
  - **Processing:**
    - Sorts candidates by `_norm1` descending and extracts top 5 chunk IDs `m1_top5_ids`.
    - Sorts candidates by `_norm2` descending and extracts top 5 chunk IDs `m2_top5_ids`.
    - Computes set intersection `intersection = m1_top5_ids & m2_top5_ids`.
  - **Outputs:** Consensus intersection candidate ID set.

- **Step 6: Consensus Chunk Pinning**
  - **Inputs:** Consensus intersection candidate chunks.
  - **Processing:** Sorts intersection chunks by `score` descending and pins up to the top 3 chunks (`pinned_chunks = intersection_chunks[:3]`).
  - **Outputs:** Pinned consensus chunks list `pinned_chunks` ($0 \le |P| \le 3$).

- **Step 7: Seeded MMR Execution on Remaining Pool**
  - **Inputs:** Remaining candidates pool (excluding pinned chunks), target slots needed $\text{num\_needed} = \text{top\_n} - |P|$.
  - **Model Called:** `GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")`.
  - **Processing:**
    - Embeds query text, pinned chunk texts, and remaining pool chunk texts into 3072-dimensional vectors.
    - Executes `_mmr()` seeding the `already_selected` vector array with `pinned_embs`.
    - Computes MMR scores using $\lambda=0.7$ and selects `num_needed` non-redundant candidates.
  - **Outputs:** Diverse remaining candidates list `diverse_chunks`.

- **Step 8: Final Merged Output & Telemetry Emission**
  - **Inputs:** `pinned_chunks` and `diverse_chunks`.
  - **Processing:** Combines `final_results = pinned_chunks + diverse_chunks` (exactly `top_n=5` chunks). Emits JSON telemetry log if `DEBUG=true`.
  - **Outputs:** Pristine, non-redundant, consensus-verified candidate list returned to caller.

---

## 💻 Implementation Guide & Code Examples

### Executing Reranking Engine Pipeline in Python
```python
import os
from dotenv import load_dotenv
from app.retrieval.hybrid_search import search
from app.retrieval.reranking_engine import rerank

# Load API credentials from environment
load_dotenv()

# Step 1: Execute Hybrid Search to get initial candidate pool (top_k = 10)
query = "What is the return window and how do I ship defective items?"
hybrid_candidates = search(query=query, top_k=10)

# Step 2: Initialize telemetry dictionary for reranker tracing
rerank_trace = {}

# Step 3: Execute Reranking Engine pipeline returning top 5 pristine chunks
final_chunks = rerank(
    query=query,
    candidates=hybrid_candidates,
    top_n=5,
    trace=rerank_trace
)

# Print reranker telemetry metrics
print(f"Models Executed: {rerank_trace.get('models_run')}")
print(f"Chunks Pinned by Consensus: {rerank_trace.get('chunks_pinned_by_consensus')}")
print(f"Chunks Added by Seeded MMR: {rerank_trace.get('chunks_added_by_mmr')}")

# Inspect final top-5 reranked chunks
for rank, chunk in enumerate(final_chunks, start=1):
    print(f"\n--- Final Rank {rank} (Normalized Consensus Score: {chunk['score']:.4f}) ---")
    print(f"ID: {chunk['id']}")
    print(f"Source: {chunk['metadata']['source']} (Page {chunk['metadata']['page_number']})")
    print(f"Section Title: {chunk['metadata']['section_title']}")
    print(f"Text Passage: {chunk['text'][:140]}...")
```

---

## 📁 Key System Files & Architecture Map

- **`backend/app/retrieval/reranking_engine.py`:**
  - Contains core functions `rerank`, `_mmr`, `_normalize_scores`, and `log_debug` implementing dual cross-encoder scoring, consensus pinning, and seeded MMR diversity.

- **`backend/tests/test_reranking_engine.py`:**
  - Unit test suite verifying score normalization guards, MMR seeding logic, candidate deduplication, and atomic logging.

---

## 🧠 Key Architectural Decisions

- **Dual Cross-Encoder Consensus Pinning Architecture:**
  - **Context:** Single cross-encoder models can exhibit domain bias or false positive spikes on specific queries.
  - **Decision:** Score candidates across both general-domain (`TinyBERT`) and e-commerce-domain (`MiniLM`) cross-encoders, requiring agreement in their top-5 sets for pinning.
  - **Outcome:** Ensures that pinned chunks have exceptionally high semantic relevance confidence.

- **MMR Seeding with Pinned Embeddings for Global Diversity:**
  - **Context:** Standard MMR only diversifies remaining candidate chunks among themselves, ignoring similarity to already pinned chunks.
  - **Decision:** Seed the `already_selected` array in `_mmr` with the vector embeddings of `pinned_chunks`.
  - **Outcome:** Guarantees true global diversity across the final `top_n` output set.

- **Min-Max Score Normalization with Zero-Variance Guard:**
  - **Context:** Raw logit outputs from different cross-encoder models operate on different numerical scales.
  - **Decision:** Min-Max normalize scores onto $[0.0, 1.0]$ before averaging, with a fallback assigning $1.0$ if $S_{\text{max}} = S_{\text{min}}$.

---

## 🐛 Technical Issues Encountered & Resolved

- **MMR Diversity Scope Defect:**
  - **Problem:** MMR selected remaining chunks that were semantically redundant with the pinned consensus chunks.
  - **Root Cause:** Original MMR implementation only tracked remaining candidate selections.
  - **Resolution:** Updated `_mmr` signature to accept `seeded_embeddings` containing pinned chunk vector embeddings.

---

## 💡 Real-World Workflow Examples

- **Scenario 1: High-Confidence Order Status Inquiry**
  - **User Query:** *"Did order ORD-1207 qualify for a return?"*
  - **Processing Flow:**
    - Dual Cross-Encoders score 10 hybrid candidates.
    - Both TinyBERT and MiniLM score Chunk A (`ORD-1207 delivery confirmation`) in their top 5.
    - Chunk A is pinned by consensus to Rank 1.
    - Seeded MMR selects 4 additional non-redundant policy chunks.
  - **Outcome:** Exact order status chunk is pinned at Rank 1.

- **Scenario 2: Broad Policy Overview Inquiry**
  - **User Query:** *"Explain the shipping, return, and warranty policies"*
  - **Processing Flow:**
    - Cross-encoders pin Return Policy overview (Rank 1).
    - Seeded MMR penalizes candidate chunks semantically similar to Return Policy.
    - MMR picks Shipping Policy (Rank 2) and Warranty Policy (Rank 3).
  - **Outcome:** Returns a balanced, diverse top-5 set covering all 3 requested policy areas.
