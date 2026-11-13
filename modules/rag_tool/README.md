# RAG Tool Module

The **RAG Tool** module serves as the primary unstructured document retrieval tool for the OmniRAG Enterprise ChatBot system. It encapsulates the two-tier retrieval pipeline—combining **Hybrid Search** (`hybrid_search.py`) and **Reranking Engine** (`reranking_engine.py`)—into a standardized, resilient LangChain `Tool` object (`rag_search_tool`).

---

## 🛠️ Technology Stack & Machine Learning Models

### 1. LangChain Tool Integration Framework (`@tool("rag_search")`)
- **What It Does:** Decorates the execution function `run_rag_search` into a schema-compliant LangChain `Tool` object that agentic frameworks can inspect and invoke autonomously.
- **Why Use It:** Provides seamless integration with LangChain agent loops, supplying function descriptions, parameter schemas (`query: str`), and error-isolated string returns.
- **Tool Inputs:** Natural language policy query string (`query: str`).
- **Tool Outputs:** JSON-serialized string containing formatted context passages, unique citation lists, and execution telemetry traces (`str`).

### 2. Layer 1 Hybrid Candidate Search Engine (`hybrid_search.py`)
- **What It Does:** Fetches 10 candidate document chunks from Pinecone using 3072-dimensional Gemini vector embeddings and in-memory Okapi BM25 scores fused via Reciprocal Rank Fusion ($k=60$).
- **Why Use It:** Ensures high-recall candidate retrieval across both semantic concepts and exact keyword terms.
- **Engine Inputs:** Query string (`query: str`), candidate count parameter `top_k=10`.
- **Engine Outputs:** List of 10 candidate chunk dictionaries containing vector IDs, metadata, and RRF scores.

### 3. Layers 2 & 3 Dual Reranking & Diversity Engine (`reranking_engine.py`)
- **What It Does:** Reranks the 10 candidate chunks using dual cross-encoder consensus models (`TinyBERT` and `MiniLM`), pins up to 3 consensus chunks, and seeds MMR ($\lambda=0.7$) to select 2 additional diverse chunks.
- **Why Use It:** Filters out noise, guarantees high-confidence precision, and eliminates semantic redundancy across returned policy chunks.
- **Engine Inputs:** Query string (`query: str`), 10 candidate chunk dictionaries, target count `top_n=5`.
- **Engine Outputs:** List of 5 pristine, non-redundant reranked chunk dictionaries.

---

## 🧮 Mathematical & Formatting Formulations

### 1. Citation String Formatting
For a retrieved document chunk $i$ with metadata attributes $\text{source}_i$ and $\text{section\_title}_i$:

$$\text{Citation}_i = \text{source}_i + \text{" - "} + \text{section\_title}_i$$

- **Example Output:** `"returns_policy.pdf - Standard Return Policy"`

### 2. Context Text Block Assembly
For each chunk text passage $T_i$ and its citation string $\text{Citation}_i$, the text block is formatted with a source header followed by the quoted passage text:

$$\text{ContextBlock}_i = \text{"[Source: "} + \text{Citation}_i + \text{"]"} + \text{HeaderSeparator} + \text{"\""} + T_i + \text{"\""}$$

The individual context blocks are then joined together using double newline separators:

$$\text{ContextString} = \text{ContextBlock}_1 + \text{BlockSeparator} + \text{ContextBlock}_2 + \dots + \text{ContextBlock}_k$$

### 3. Order-Preserving Citation Deduplication
To strip duplicate citations while maintaining original rank order:

$$\text{Citations}_{\text{unique}} = \text{list}(\text{dict.fromkeys}(\text{citations}))$$

---

## 🏗️ Implementation Details & End-to-End Data Pipeline Architecture

The `rag_tool` module executes an 8-step atomic data pipeline that transforms a search query string into a JSON-serialized context payload.

### 🔄 Step-by-Step Atomic Data Pipeline

- **Step 1: Tool Invocation & Parameter Extraction**
  - **Inputs:** Natural language search query `query` (e.g., `"What is the refund window?"`).
  - **Function Called:** `rag_search_tool(query: str)` or `run_rag_search(query: str)`.
  - **Processing:** Receives parameter string, logs event initiation via `atomic_log("run_rag_search_start")`, and opens safe execution context.
  - **Outputs:** Validated query parameter string.

- **Step 2: Telemetry Trace Initialization**
  - **Inputs:** Execution context.
  - **Processing:** Initializes empty `trace_data: dict[str, Any]` dictionary to accumulate metrics across downstream retrieval layers.
  - **Outputs:** Empty trace data dictionary reference.

- **Step 3: Layer 1 Candidate Retrieval (Hybrid Search)**
  - **Inputs:** Search query `query`, candidate limit `top_k=10`, `trace_data` reference.
  - **Function Called:** `hybrid_search.search(query, top_k=10, trace=trace_data)`.
  - **Processing:** Embeds query via Gemini, queries Pinecone dense index, calculates local BM25 scores, and fuses ranks using RRF ($k=60$).
  - **Outputs:** List of 10 RRF-fused candidate dictionaries (`candidates`).

- **Step 4: Layers 2 & 3 Candidate Refinement (Reranking Engine)**
  - **Inputs:** Search query `query`, 10 candidate dictionaries `candidates`, target output limit `top_n=5`, `trace_data` reference.
  - **Function Called:** `reranking_engine.rerank(query, candidates, top_n=5, trace=trace_data)`.
  - **Processing:** Executes Dual FlashRank cross-encoder scoring, pins consensus chunks ($\le 3$), and applies seeded MMR ($\lambda=0.7$) over remaining pool.
  - **Outputs:** List of 5 refined chunk dictionaries (`chunks`).

- **Step 5: Metadata Extraction & Citation Formatting**
  - **Inputs:** Refined chunks list `chunks`.
  - **Processing:** Iterates through `chunks`, extracts `source` (defaulting to `'unknown.pdf'`) and `section_title` (defaulting to `'Unknown Section'`), and builds citation string `f"{source} - {section}"`.
  - **Outputs:** Accumulator list of raw citation strings `citations: list[str]`.

- **Step 6: Context Block Formatting & Concatenation**
  - **Inputs:** Refined chunks list `chunks` and formatted citation strings.
  - **Processing:** Wraps chunk text passage inside quoted source block `f"[Source: {citation}]\n\"{text}\""` and joins blocks with double newlines (`"\n\n"`).
  - **Outputs:** Combined context text string `context_str: str`.

- **Step 7: Order-Preserving Citation Deduplication**
  - **Inputs:** Accumulator list `citations`.
  - **Processing:** Applies `list(dict.fromkeys(citations))` to eliminate duplicate section citations while strictly preserving initial rank order.
  - **Outputs:** Unique citations list `unique_citations: list[str]`.

- **Step 8: JSON Serialization & Error Handling Delivery**
  - **Inputs:** `context_str`, `unique_citations`, `trace_data`.
  - **Processing:** Logs success via `atomic_log("run_rag_search_success")` and serializes dictionary to JSON string. On exception, catches `ImportError` or generic exceptions and returns `json.dumps({"error": str(e)})`.
  - **Outputs:** JSON-serialized string payload returned to caller or agent.

---

## 💻 Implementation Guide & Code Examples

### 1. Direct Execution in Python Code
```python
import json
import os
from dotenv import load_dotenv
from app.tools.rag_tool import run_rag_search

# Load API credentials from environment
load_dotenv()

# Define user policy inquiry
query = "What is the return policy window for electronic gadgets?"

# Execute RAG search pipeline
raw_json = run_rag_search(query)

# Parse returned JSON payload
response = json.loads(raw_json)

# Check for execution errors
if "error" in response:
    print(f"RAG Retrieval Error: {response['error']}")
else:
    print("=== Unique Citations ===")
    for cit in response["citations"]:
        print(f"- {cit}")
        
    print("\n=== Formatted LLM Context String ===")
    print(response["context"])
```

### 2. Integrating `rag_search_tool` into LangChain Agent Frameworks
```python
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from app.tools.rag_tool import rag_search_tool

# Load API credentials
load_dotenv()

# Inspect LangChain Tool metadata
print(f"Tool Name: {rag_search_tool.name}")
print(f"Tool Description: {rag_search_tool.description}")

# Example: Binding tool to a LangChain model instance
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")
llm_with_tools = llm.bind_tools([rag_search_tool])

# Invoke model with policy question
response = llm_with_tools.invoke("How many days of annual leave do employees receive?")
print("Agent Tool Call Decision:")
print(response.tool_calls)
```

---

## 📁 Key System Files & Architecture Map

- **`backend/app/tools/rag_tool.py`:**
  - Contains `run_rag_search`, `rag_search_tool`, and `atomic_log` functions implementing context formatting, citation deduplication, and LangChain tool export.

- **`backend/tests/test_rag_tool.py`:**
  - Automated unit test suite verifying valid RAG search execution, citation formatting (`source - section`), LangChain tool export, and FlashRank `ImportError` fallback.

---

## 🧠 Key Architectural Decisions

- **JSON String Output Contract with Error Isolation:**
  - **Context:** Agent tool invocation failures throwing unhandled exceptions can break agent execution state loops.
  - **Decision:** Wrap the RAG execution engine in try-except blocks and return stringified JSON payloads containing `{"error": str(e)}` on failure.
  - **Outcome:** Guarantees tool resilience while allowing downstream agents to inspect error messages cleanly.

- **Hyphen Citation Separator Standard (`source - section`):**
  - **Context:** Section character symbols (such as `§`) previously caused parsing confusion in certain client environments.
  - **Decision:** Standardized citation formatting string to `f"{source} - {section}"`.
  - **Outcome:** Clean, human-readable citation references across client user interfaces.

- **Order-Preserving Citation Deduplication via `dict.fromkeys()`:**
  - **Context:** Multiple reranked chunks frequently originate from different paragraphs of the same policy document section, producing redundant citation entries.
  - **Decision:** Utilize Python `dict.fromkeys(citations)` to deduplicate citation strings while preserving their rank order.

---

## 🐛 Technical Issues Encountered & Resolved

- **FlashRank CPU Import Error Resilience:**
  - **Problem:** Running in environments missing FlashRank CPU binaries crashed the retrieval pipeline.
  - **Root Cause:** Direct unhandled `ImportError` in secondary reranker module.
  - **Resolution:** Wrapped retrieval execution in `run_rag_search` with explicit `ImportError` catch block returning `json.dumps({"error": str(e)})`.

- **Section Title Embedded Newline Cleanup:**
  - **Problem:** PDF text extraction attached newlines (`\n`) inside metadata `section_title` fields, breaking citation line formatting.
  - **Root Cause:** Raw PDF header text contained multiline layout wraps.
  - **Resolution:** Stripped embedded newlines at ingestion time in `data_ingestion.py`.

---

## 💡 Real-World Workflow Examples

- **Scenario 1: Customer Inquiry Regarding Returns & Refunds**
  - **User Query:** *"What is the refund window?"*
  - **Processing Flow:**
    - `hybrid_search` retrieves 10 candidate chunks from `returns_policy.pdf`.
    - `reranking_engine` pins top consensus chunks and selects 5 pristine chunks.
    - `rag_tool` formats context block: `[Source: returns_policy.pdf - Standard Return Policy]\n"Products purchased from Northwind Gadgets may be returned within 30 days..."`.
    - Citation list deduplicated to `["returns_policy.pdf - Standard Return Policy"]`.
  - **Outcome:** Returns JSON payload with 5 formatted context blocks and 1 clean citation string.

- **Scenario 2: Employee Inquiry Regarding Annual Leave Eligibility**
  - **User Query:** *"How many days of paid leave do employees get per year?"*
  - **Processing Flow:**
    - `hybrid_search` retrieves 10 candidates from `hr_leave_policy.pdf`.
    - `reranking_engine` pins 3 consensus chunks and MMR selects 2 diverse chunks.
    - `rag_tool` formats context blocks and deduplicates section citations.
  - **Outcome:** Returns JSON payload supplying exact HR policy figures to the calling agent.
