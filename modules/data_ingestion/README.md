# Data Ingestion Module

The **Data Ingestion** module serves as the foundational ETL data pipeline for the OmniRAG Enterprise ChatBot system. It processes unstructured enterprise policy documents in PDF format alongside structured transactional order datasets in CSV format, transforming raw files into high-performance vector indices and relational database tables.

---

## 🛠️ Technology Stack & Machine Learning Models

### 1. Dense Embedding Model: Google Gemini Embedding 001 (`models/gemini-embedding-001`)
- **What It Does:** Converts raw text passages into 3072-dimensional dense floating-point vector representations capturing semantic concepts and contextual intent.
- **Why Use It:** Delivers state-of-the-art semantic precision, multi-lingual support, and high-dimensional vector capacity required for complex policy document search.
- **Model Inputs:** Child document text strings (`text: str`).
- **Model Outputs:** 3072-dimensional floating-point vector array (`list[float]`).

### 2. Dense Vector Index: Pinecone Serverless Vector Database
- **What It Does:** Stores 3072-dimensional document chunk vectors alongside rich JSON metadata dictionaries (`parent_id`, `parent_text`, `section_title`, `source`, `page_number`).
- **Why Use It:** Low-latency serverless vector indexing scaling automatically without cluster maintenance overhead.
- **Index Inputs:** Vector UUID string, 3072-dimensional vector embedding, and metadata dictionary payload.
- **Index Outputs:** Success status and indexed vector count.

### 3. Structured Data Engine: Pandas & SQLite3
- **What It Does:** Parses structured CSV order datasets into a local SQLite database (`orders.db`).
- **Why Use It:** Provides zero-latency, local SQL query execution for structured transactional inquiries.
- **Engine Inputs:** CSV file path (`backend/data/orders.csv`).
- **Engine Outputs:** SQLite database table `orders` populated with 200 operational order records.

---

## 🧩 Custom Character Splitter Implementation Details

The `SimpleTextSplitter` class in `backend/app/retrieval/ingest.py` is a lightweight custom text chunking engine developed to replace external character splitters. It provides precise sliding-window character boundary slicing, token bound guarantees, and non-lossy metadata preservation.

### 📐 Sliding-Window Stride Algorithm
The splitter calculates chunk boundaries dynamically using an iterative character pointer index `i`:
- **Target Chunk Size (`C`):** Maximum character capacity of each chunk.
- **Chunk Overlap (`O`):** Number of overlapping characters preserved from the preceding chunk.
- **Net Pointer Stride (`S`):** Advance step computed as `S = C - O`.

For each iteration step:
$$\text{Chunk}_k = \text{Text}[i : i + C]$$
$$i_{k+1} = i_k + (C - O)$$

The loop continues until pointer index $i$ reaches or exceeds the total string length. If an edge case produces zero chunks for a non-empty string, a fallback guard appends the complete text string.

### 🌲 Hierarchical Two-Tier Chunking Parameters

1. **Tier 1 Parent Section Splitter:**
   - **Chunk Size (`C_parent`):** 2000 characters (approximately 400 to 500 tokens).
   - **Chunk Overlap (`O_parent`):** 200 characters (approximately 40 tokens).
   - **Net Stride:** 1800 characters.
   - **Purpose:** Preserves broad section-level context, headers, and surrounding policy rules.

2. **Tier 2 Child Chunk Splitter:**
   - **Chunk Size (`C_child`):** 500 characters (approximately 100 to 150 tokens).
   - **Chunk Overlap (`O_child`):** 50 characters (approximately 10 tokens).
   - **Net Stride:** 450 characters.
   - **Purpose:** Generates tight, focused text passages for precise vector embedding and high-similarity retrieval.

---

## 🏗️ Implementation Details & End-to-End Data Pipeline Architecture

The `data_ingestion` module executes a 6-step atomic data pipeline for PDF policy processing and a 3-step atomic pipeline for CSV order processing.

### 🔄 Step-by-Step Atomic Unstructured PDF Pipeline

- **Step 1: PDF Document Parsing & Extraction**
  - **Inputs:** PDF file path (e.g., `backend/data/hr_leave_policy.pdf`).
  - **Function Called:** `process_pdf(file_path: str) -> list[Document]`.
  - **Processing:** PyPDF `PdfReader` extracts page-level raw text strings and attaches page numbers (1-indexed) and base filenames to metadata.
  - **Outputs:** List of raw page-level LangChain `Document` objects.

- **Step 2: Tier 1 Parent Section Splitting**
  - **Inputs:** Page-level `Document` objects.
  - **Object Called:** `SimpleTextSplitter(chunk_size=2000, chunk_overlap=200)`.
  - **Processing:** Divides page text into 2000-character parent sections with 1800-character stride.
  - **Outputs:** List of parent section `Document` objects (`parent_docs`).

- **Step 3: Tier 2 Child Chunking & Parent Context Binding**
  - **Inputs:** `parent_docs` list.
  - **Object Called:** `SimpleTextSplitter(chunk_size=500, chunk_overlap=50)`.
  - **Processing:** Generates a unique UUID `parent_id` for each parent section, extracts section title from line 1 (up to 50 chars), splits parent section into 500-character child chunks, and injects `parent_id`, `parent_text`, and `section_title` into child metadata.
  - **Outputs:** Enriched child chunk `Document` objects (`child_docs`).

- **Step 4: Vector Embedding Computation**
  - **Inputs:** Child chunk text passages (`page_content`).
  - **Model Called:** `GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")`.
  - **Processing:** Embeds child text passages in batches of 100 via Google Gemini API.
  - **Outputs:** 3072-dimensional vector arrays (`embeds: list[list[float]]`).

- **Step 5: Pinecone Index Verification & Creation**
  - **Inputs:** Target index name (`northwind-gadgets`), API key.
  - **Database Called:** Pinecone Serverless Client.
  - **Processing:** Checks `pc.has_index(index_name)`. If missing, creates serverless index with `dimension=3072` and `metric="cosine"` in `us-east-1`.
  - **Outputs:** Verified Pinecone index instance.

- **Step 6: Batch Vector Upsertion**
  - **Inputs:** Chunk UUIDs, 3072-dimensional vector embeddings, and metadata dictionaries.
  - **Processing:** Zips inputs into upsert tuples and uploads to Pinecone in 100-item batches (`index.upsert(vectors=vectors)`).
  - **Outputs:** Populated serverless vector database ready for real-time similarity search.

---

## 💻 Implementation Guide & Code Examples

### 1. Ingesting Policy PDFs into Pinecone
```python
import os
from pathlib import Path
from dotenv import load_dotenv
from app.retrieval.ingest import ingest_pdfs, process_pdf

# Load API credentials from environment
load_dotenv()

# Resolve absolute path to data directory
data_dir = Path(__file__).resolve().parent.parent / "data"

# Example 1: Ingesting all policy PDFs in backend/data/ into Pinecone
ingest_pdfs(data_dir=str(data_dir), index_name="northwind-gadgets")

# Example 2: Parsing a single PDF into chunked Document objects
pdf_path = data_dir / "returns_policy.pdf"
child_chunks = process_pdf(str(pdf_path))

# Inspect first child chunk payload
first_chunk = child_chunks[0]
print(f"Child Content: {first_chunk.page_content[:100]}...")
print(f"Parent Section ID: {first_chunk.metadata['parent_id']}")
print(f"Section Title: {first_chunk.metadata['section_title']}")
```

### 2. Initializing Local SQLite Orders Database
```python
from pathlib import Path
from app.tools.sql_tool import init_db

# Resolve data file paths
data_dir = Path(__file__).resolve().parent.parent / "data"
db_path = data_dir / "orders.db"
csv_path = data_dir / "orders.csv"

# Idempotently load CSV rows into SQLite orders.db
init_db(db_path=str(db_path), csv_path=str(csv_path))
print("Database initialized successfully with 200 order rows.")
```

---

## 📁 Key System Files & Architecture Map

- **`backend/app/retrieval/ingest.py`:**
  - Contains core functions `ingest_pdfs` and `process_pdf` implementing PDF text extraction, `SimpleTextSplitter` character splitting, Gemini embedding calls, and Pinecone vector upsertion.

- **`backend/app/tools/sql_tool.py`:**
  - Contains database initialization function `init_db` implementing CSV parsing and SQLite table loading.

- **`backend/tests/test_data_ingestion.py`:**
  - Automated integration test suite validating SQLite table row counts, record values, and Pinecone serverless index connectivity.

---

## 🧠 Key Architectural Decisions

- **Custom Character Splitter Implementation:**
  - Standard third-party text splitting packages required additional external dependencies.
  - Developing a lightweight `SimpleTextSplitter` class eliminated third-party package overhead while providing precise control over sliding window character boundaries and token limits.

- **Idempotent Database Initialization Strategy:**
  - Using `replace` mode during table creation ensures that re-running initialization scripts cleanly resets table state without requiring manual database resets or risking primary key collision errors.

- **Vector Dimension Alignment to 3072 Floating Point Values:**
  - Upgrading the default embedding model to Google Gemini Embedding 001 required expanding the Pinecone index vector dimension parameter to 3072.
  - Matching vector dimensions between the embedding model and vector index prevents runtime API dimensional mismatch exceptions.

---

## 🐛 Technical Issues Encountered & Resolved

- **Pinecone SDK Package Rename Issue:**
  - **Problem:** The legacy `pinecone-client` package caused import resolution failures during initialization.
  - **Root Cause:** Official Pinecone Python SDK v6 migrated from `pinecone-client` to `pinecone`.
  - **Resolution:** Uninstalled legacy package and installed Pinecone SDK `v6.0.0`.

- **Working Directory File Path Resolution Issue:**
  - **Problem:** Running scripts from subdirectories created duplicated `backend/data` directory structures on disk.
  - **Root Cause:** Hardcoded relative file path strings resolved differently depending on process working directory.
  - **Resolution:** Refactored all path resolutions across `ingest.py` and test files to use `Path(__file__)` resolve parent references.

- **Vector Index Dimension Mismatch Error:**
  - **Problem:** Pinecone index rejected vector upsert requests with an HTTP dimension error.
  - **Root Cause:** Vector index was configured for 768 dimensions while Gemini Embedding 001 produced 3072-dimensional vectors.
  - **Resolution:** Updated index creation parameters to dimension 3072 and re-indexed all document chunks.

---

## 💡 Real-World Workflow Examples

- **Scenario 1: Ingesting Corporate HR Leave Policy**
  - **Input File:** `data/hr_leave_policy.pdf`
  - **Processing Flow:**
    - PyPDF extracts raw text across page 1 and page 2.
    - Parent splitter divides text into 2000-character sections with 200-character overlaps.
    - Child splitter divides each parent section into 500-character chunks with 50-character overlaps.
    - Unique UUID parent identifiers are generated and attached to each child chunk metadata dictionary.
    - Gemini embedding generator generates 3072-dimensional float vectors for every child chunk.
    - Vector payloads containing parent section text, page numbers, and source filenames are upserted to Pinecone.
  - **Outcome:** Pinecone vector database contains indexed vectors ready for real-time cosine similarity retrieval.

- **Scenario 2: Loading Customer Orders Dataset**
  - **Input File:** `data/orders.csv`
  - **Processing Flow:**
    - Pandas reads 200 order rows from `orders.csv`.
    - Data types are assigned mapping `order_id` to `TEXT`, `customer` to `TEXT`, `product` to `TEXT`, `amount` to `INTEGER`, `status` to `TEXT`, and `order_date` to `DATE`.
    - SQLite database connection opens `orders.db` and writes data using `replace` mode.
  - **Outcome:** Local SQLite database `orders.db` contains 200 structured records ready for analytical SQL queries.

---

## 🔍 Data Quality Observations

- **Non-Sequential Order Identifiers:**
  - Dataset file `orders.csv` contains non-sequential order identifier `ORD-1207` alongside sequential identifiers `ORD-1001` to `ORD-1200`.
  - Text-to-SQL generator queries non-sequential order identifiers successfully without throwing schema or indexing exceptions.
