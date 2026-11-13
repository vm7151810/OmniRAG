# Hybrid Search Module Architecture

```mermaid
graph TD
    subgraph Input Query Stage
        A["User Natural Language Query"] --> B["Google Gemini Embedding Engine"]
        B -->|models/gemini-embedding-001| C["3072-dim Query Vector"]
    end

    subgraph Dense Search Stage
        C -->|Dense Vector Query| D["Pinecone Serverless Index"]
        D -->|Fetch top_k * 5 = 50 Candidates| E["Dense Candidates Pool"]
    end

    subgraph Sparse BM25 Search Stage
        E -->|Extract Metadata Text| F["Candidate Document Texts"]
        A --> G["Custom Tokenizer Engine"]
        F --> G
        G -->|Okapi BM25 Scoring k1=1.5 b=0.75| H["In-Memory BM25 Scores"]
    end

    subgraph Reciprocal Rank Fusion Stage
        E -->|Dense Positional Order| I["Dense Rank Mapping (1..50)"]
        H -->|BM25 Descending Order| J["Sparse Rank Mapping (1..50)"]
        I --> K["RRF Fusion Engine (k=60)"]
        J --> K
        K -->|Sort RRF Score Descending| L["Top-K Ranked Candidates"]
    end

    style D fill:#0369a1,stroke:#0284c7,color:#fff
    style H fill:#047857,stroke:#059669,color:#fff
    style K fill:#701a75,stroke:#d946ef,color:#fff
```

---

## 🔀 BM25 Tokenization & RRF Rank Fusion Subsystem Flow Diagram

```mermaid
flowchart TD
    subgraph Search Trigger
        S0["Search Function Invoked: search(query, top_k=10)"] --> S1["Generate Trace UUID & Validate Environment Keys"]
        S1 --> S2["Embed Query Vector using gemini-embedding-001 (3072 dim)"]
    end

    subgraph Pinecone Dense Retrieval
        S2 --> P1["Index Query: index.query(vector, top_k=50, include_metadata=True)"]
        P1 --> P2["Extract Matches & Metadata Text (parent_text -> text -> section_title)"]
    end

    subgraph Local Okapi BM25 Calculation
        P2 --> B1["Tokenize Query & Document Texts: lowercase, strip punctuation"]
        B1 --> B2["Calculate Document Frequency (DF) across candidate pool"]
        B2 --> B3["Compute Term IDF & BM25 Scores (k1=1.5, b=0.75)"]
        B3 --> B4["Generate Sparse Ranks: 1-indexed dictionary by BM25 score descending"]
    end

    subgraph Reciprocal Rank Fusion Computation
        B4 --> R1["Loop Candidate Matches (1..50)"]
        R1 --> R2["Compute RRF Score: (1 / (60 + Dense_Rank)) + (1 / (60 + Sparse_Rank))"]
        R2 --> R3["Sort Candidates by RRF Score Descending"]
        R3 --> R4["Slice Top-K Candidates (Default top_k=10)"]
    end

    style S0 fill:#1e293b,stroke:#475569,color:#fff
    style P1 fill:#1e3a8a,stroke:#3b82f6,color:#fff
    style B3 fill:#065f46,stroke:#10b981,color:#fff
    style R4 fill:#701a75,stroke:#d946ef,color:#fff
```

---

## 📖 Data Processing Pipeline Narrative

- **Dense Vector Search Path:**
  - User query string is converted to a 3072-dimensional vector embedding.
  - Pinecone vector database executes dense cosine distance retrieval, returning 50 top vector candidates.

- **Sparse BM25 Keyword Search Path:**
  - Candidate document texts are extracted from metadata dictionaries.
  - Custom tokenizer cleans punctuation and computes term frequency and inverse document frequency across the candidate pool.

- **Reciprocal Rank Fusion Path:**
  - Dense and sparse positional ranks are mapped onto a 1-indexed scale.
  - Reciprocal Rank Fusion formula calculates combined score using constant $k=60$.
  - Candidates are sorted by final RRF score and sliced to return top-10 candidate chunks.
