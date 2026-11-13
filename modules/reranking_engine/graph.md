# Reranking Engine Module Architecture

```mermaid
graph TD
    subgraph Input Candidate Stage
        A["Hybrid Search Candidate Chunks (N=10)"] --> B["FlashRank Cross-Encoder 1: ms-marco-TinyBERT-L-2-v2"]
        A --> C["FlashRank Cross-Encoder 2: ce-esci-MiniLM-L12-v2"]
    end

    subgraph Dual Scoring & Normalization
        B --> D["Min-Max Score Normalization [0.0, 1.0]"]
        C --> E["Min-Max Score Normalization [0.0, 1.0]"]
        D --> F["Compute Average Score"]
        E --> F
    end

    subgraph Consensus Pinning Stage
        F --> G["Extract Top-5 Sets per Model"]
        G --> H["Consensus Intersection (Top-5 Model 1 ∩ Top-5 Model 2)"]
        H --> I["Pin Top Consensus Chunks (≤3 Chunks)"]
    end

    subgraph Seeded MMR Diversity Stage
        I -->|Seed Embeddings| J["Maximal Marginal Relevance Engine (λ=0.7)"]
        A -->|Remaining Pool| J
        J --> K["Diverse MMR Chunks"]
    end

    subgraph Output Stage
        I --> L["Final Refined Output (Top-N Chunks)"]
        K --> L
    end

    style B fill:#0369a1,stroke:#0284c7,color:#fff
    style C fill:#0369a1,stroke:#0284c7,color:#fff
    style H fill:#047857,stroke:#059669,color:#fff
    style J fill:#701a75,stroke:#d946ef,color:#fff
```

---

## 🔀 Dual Cross-Encoder Consensus & Seeded MMR Subsystem Flow Diagram

```mermaid
flowchart TD
    subgraph Trigger & Payload Structuring
        R0["rerank(query, candidates, top_n=5)"] --> R1["Format Passages Payload & Initialize FlashRank Models"]
        R1 --> R2["Execute Inference: TinyBERT & MiniLM"]
    end

    subgraph Score Normalization & Ranking
        R2 --> N1["Min-Max Normalize Raw Scores per Model"]
        N1 --> N2["Compute Combined Average Score: (Norm1 + Norm2) / 2"]
        N2 --> P1["Extract Top-5 Candidate IDs from TinyBERT"]
        N2 --> P2["Extract Top-5 Candidate IDs from MiniLM"]
    end

    subgraph Consensus Pinning Loop
        P1 --> I1["Set Intersection: TinyBERT Top-5 ∩ MiniLM Top-5"]
        P2 --> I1
        I1 --> I2["Sort Intersection Chunks by Average Score Descending"]
        I2 --> I3["Pin Top ≤3 Consensus Chunks"]
    end

    subgraph Seeded MMR Execution
        I3 --> M1["Isolate Remaining Candidate Pool (Excluding Pinned IDs)"]
        I3 -->|Embed Pinned Chunk Texts| M2["Seeded Pinned Embeddings Array"]
        M1 -->|Embed Remaining Chunk Texts| M3["Remaining Pool Embeddings Array"]
        M2 --> M4["Execute _mmr(lambda=0.7, top_n = top_n - len(pinned))"]
        M3 --> M4
        M4 --> M5["Select Diverse Remaining Candidate Chunks"]
    end

    subgraph Output Payload Assembly
        I3 --> F1["Combine: Pinned Consensus Chunks + MMR Diverse Chunks"]
        M5 --> F1
        F1 --> F2["Return Top-N Pristine Candidate Dictionaries (top_n=5)"]
    end

    style R0 fill:#1e293b,stroke:#475569,color:#fff
    style N2 fill:#1e3a8a,stroke:#3b82f6,color:#fff
    style I3 fill:#065f46,stroke:#10b981,color:#fff
    style F2 fill:#701a75,stroke:#d946ef,color:#fff
```

---

## 📖 Data Processing Pipeline Narrative

- **Dual Cross-Encoder Scoring Path:**
  - Hybrid search candidate chunks are scored in parallel by `ms-marco-TinyBERT-L-2-v2` and `ce-esci-MiniLM-L12-v2`.
  - Raw scores are Min-Max normalized onto $[0.0, 1.0]$ and averaged.

- **Consensus Pinning Path:**
  - Candidates present in both top-5 sets are intersected and sorted by average score.
  - Up to 3 top consensus chunks are pinned directly to the output head.

- **Seeded MMR Diversity Path:**
  - Remaining candidate chunks are evaluated using Maximal Marginal Relevance ($\lambda=0.7$).
  - Vector embeddings of pinned chunks seed the MMR algorithm, penalizing candidates semantically redundant with pinned context.
  - The merged top-5 result set is returned.
