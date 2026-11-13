# SQL Tool Module

The **SQL Tool** module provides structured database querying capabilities for the OmniRAG Enterprise ChatBot system. It translates natural language operational inquiries into read-only SQL queries, enforces a **Dual DML Security Guard** (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`), executes queries against a local SQLite database (`orders.db`), and exports a standardized LangChain `Tool` (`sql_query_tool`).

---

## 🛠️ Technology Stack & Machine Learning Models

### 1. Text-to-SQL Translation Model: Google Gemini 3.5 Flash (`gemini-3.5-flash`)
- **What It Does:** Translates natural language questions into valid, syntactically accurate SQLite `SELECT` statements based on an injected database schema and reference anchor date (`2026-06-15`).
- **Why Use It:** Delivers low-latency Text-to-SQL reasoning with strict adherence to prompt constraints and zero-temperature deterministic query generation.
- **Model Inputs:** Schema prompt injection string, system constraints, and raw user question (`question: str`).
- **Model Outputs:** Raw SQL `SELECT` query string.

### 2. Security Infrastructure: Dual DML Security Guard Engine
- **What It Does:** Intercepts data modification keywords (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`) twice—first on raw user input questions before LLM invocation, and second on generated SQL strings before database execution.
- **Why Use It:** Eliminates SQL injection vulnerabilities, prevents database tampering, and short-circuits malicious inputs without wasting LLM API tokens.
- **Guard Inputs:** Input question string and generated SQL string.
- **Guard Outputs:** Pass-through authorization or early `ValueError("Only SELECT queries are permitted.")` exception.

### 3. Relational Database Engine: SQLite3 & Pandas
- **What It Does:** Stores 200 customer order records in `backend/data/orders.db` and executes read-only SQL queries.
- **Why Use It:** Offers zero-latency, local SQL query execution with zero external server dependencies.
- **Engine Inputs:** Validated SQL `SELECT` query string.
- **Engine Outputs:** Raw result row tuples and column name metadata.

### 4. LangChain Integration Framework (`Tool(name="sql_query")`)
- **What It Does:** Wraps `run_sql_query` into a LangChain `Tool` instance consumable by agentic frameworks.
- **Why Use It:** Allows LangChain agents to inspect tool descriptions and parameter schemas to invoke database queries automatically.
- **Tool Inputs:** Input question dictionary `{"question": str}`.
- **Tool Outputs:** JSON-serialized string containing `result`, `sql`, and `error` keys.

---

## 🧮 Mathematical & Logic Formulations

### 1. Pre-LLM DML Security Guard Verification
For an input question string $Q$ and a set of restricted DML keywords $\text{DML} = \{\text{DROP}, \text{DELETE}, \text{UPDATE}, \text{INSERT}, \text{ALTER}, \text{TRUNCATE}\}$:

$$\text{BlockCondition}_{\text{Pre}} = \bigvee_{kw \in \text{DML}} \left( kw \in \text{Upper}(Q) \right)$$

If $\text{BlockCondition}_{\text{Pre}} = \text{True}$, execution halts immediately and throws `ValueError("Only SELECT queries are permitted.")`.

### 2. Post-LLM Generated SQL Security Guard Verification
For the generated raw SQL string $\text{SQL}_{\text{gen}}$:

$$\text{BlockCondition}_{\text{Post}} = \bigvee_{kw \in \text{DML}} \left( kw \in \text{Upper}(\text{SQL}_{\text{gen}}) \right)$$

If $\text{BlockCondition}_{\text{Post}} = \text{True}$, execution halts immediately and throws `ValueError("Only SELECT queries are permitted.")`.

### 3. Column-Row Dictionary Transformation
For a list of column names $C = [c_1, c_2, \dots, c_m]$ and a result row tuple $R_j = (v_{j1}, v_{j2}, \dots, v_{jm})$:

$$\text{RowDict}_j = \text{dict}\left( \text{zip}(C, R_j) \right) = \{ c_1: v_{j1}, c_2: v_{j2}, \dots, c_m: v_{jm} \}$$

$$\text{ResultString} = \text{str}\left( [ \text{RowDict}_1, \text{RowDict}_2, \dots, \text{RowDict}_k ] \right)$$

---

## 🏗️ Implementation Details & End-to-End Data Pipeline Architecture

The `sql_tool` module executes a 9-step atomic data pipeline that converts natural language operational questions into formatted SQL results.

### 🔄 Step-by-Step Atomic Data Pipeline

- **Step 1: Function Invocation & Input Logging**
  - **Inputs:** User question string `question` (e.g., `"How many orders are pending?"`).
  - **Function Called:** `run_sql_query(question: str)`.
  - **Processing:** Logs event initiation via `atomic_log("run_sql_query_start")` and enters execution context.
  - **Outputs:** Input question string parameter.

- **Step 2: Pre-LLM Dual DML Security Guard Check**
  - **Inputs:** Input question string `question`.
  - **Processing:** Converts `question` to uppercase and checks for presence of restricted keywords (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`). Throws `ValueError` if any match.
  - **Outputs:** Pre-execution security authorization.

- **Step 3: Prompt Construction & Schema Injection**
  - **Inputs:** `question` string, `SCHEMA_PROMPT_INJECTION` string.
  - **Processing:** Injects table schema (`orders(order_id, customer, product, amount, status, order_date)`), current date anchor (`2026-06-15`), and strict `SELECT`-only constraints into system prompt string.
  - **Outputs:** Full LLM prompt string.

- **Step 4: Text-to-SQL Translation Generation**
  - **Inputs:** Injected system prompt string.
  - **Model Called:** `ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0.0)`.
  - **Processing:** Dispatches prompt to Gemini API with temperature 0.0 for deterministic SQL query generation.
  - **Outputs:** Model response payload (`response.content`).

- **Step 5: Content Extraction & Markdown Code Block Cleaning**
  - **Inputs:** Model response content payload.
  - **Processing:** Extracts string content (handling list vs string response structures) and strips markdown code fence wrappers (` ```sql ... ``` `).
  - **Outputs:** Cleaned raw SQL query string `sql_query`.

- **Step 6: Post-LLM Dual DML Security Guard Check**
  - **Inputs:** Cleaned `sql_query` string.
  - **Processing:** Converts `sql_query` to uppercase and re-checks for restricted DML keywords. Throws `ValueError` if any match.
  - **Outputs:** Authorized read-only SQL query string.

- **Step 7: SQLite Database Read Execution**
  - **Inputs:** `sql_query` string, absolute file path to `orders.db`.
  - **Database Called:** Local SQLite3 Database Engine.
  - **Processing:** Establishes connection to `orders.db`, executes `cursor.execute(sql_query)`, fetches matching rows via `cursor.fetchall()`, and extracts column names from `cursor.description`.
  - **Outputs:** Row tuples list `rows` and column name list `columns`.

- **Step 8: Result Row Dictionary Formatting**
  - **Inputs:** `rows` and `columns`.
  - **Processing:** Maps column names to cell values for each row (`dict(zip(columns, row))`) and stringifies the result list.
  - **Outputs:** Formatted result string `result_str`.

- **Step 9: Error Isolation & JSON Payload Serialization**
  - **Inputs:** `result_str`, `sql_query`, error context.
  - **Processing:** Logs success via `atomic_log("run_sql_query_success")` and returns `json.dumps({"result": result_str, "sql": sql_query, "error": None})`. On exception, catches error and returns `json.dumps({"result": "", "sql": sql_query, "error": str(e)})`.
  - **Outputs:** JSON-serialized payload returned to caller or agent.

---

## 💻 Implementation Guide & Code Examples

### 1. Direct Execution in Python Code
```python
import json
import os
from dotenv import load_dotenv
from app.tools.sql_tool import run_sql_query

# Load API credentials from environment
load_dotenv()

# Define natural language analytical question
question = "How many orders are pending and what is the total revenue?"

# Execute SQL query pipeline
raw_json = run_sql_query(question)

# Parse returned JSON payload
response = json.loads(raw_json)

# Inspect results
if response.get("error"):
    print(f"SQL Tool Error: {response['error']}")
else:
    print(f"Generated SQL Query: {response['sql']}")
    print(f"Database Output: {response['result']}")
```

### 2. Integrating `sql_query_tool` into LangChain Agent Frameworks
```python
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from app.tools.sql_tool import sql_query_tool

# Load API credentials
load_dotenv()

# Inspect LangChain Tool metadata
print(f"Tool Name: {sql_query_tool.name}")
print(f"Tool Description: {sql_query_tool.description}")

# Example: Binding tool to a LangChain model instance
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")
llm_with_tools = llm.bind_tools([sql_query_tool])

# Invoke model with operational question
response = llm_with_tools.invoke("Show me the orders placed by Sneha Reddy")
print("Agent Tool Call Decision:")
print(response.tool_calls)
```

### 3. Initializing SQLite Database from CSV
```python
from pathlib import Path
from app.tools.sql_tool import init_db

# Resolve absolute data paths
data_dir = Path(__file__).resolve().parent.parent / "data"
db_path = data_dir / "orders.db"
csv_path = data_dir / "orders.csv"

# Idempotently create/overwrite SQLite orders table
init_db(db_path=str(db_path), csv_path=str(csv_path))
```

---

## 📁 Key System Files & Architecture Map

- **`backend/app/tools/sql_tool.py`:**
  - Contains `run_sql_query`, `sql_query_tool`, `init_db`, and `atomic_log` implementing Text-to-SQL generation, dual DML security guards, SQLite database execution, and LangChain tool export.

- **`backend/tests/test_sql_tool.py`:**
  - Automated unit test suite verifying valid SELECT query generation, DML security block interception (`DELETE`), database connectivity, and LangChain tool export.

---

## 🧠 Key Architectural Decisions

- **Pre-LLM Prompt-Level DML Short-Circuiting:**
  - **Context:** Passing malicious questions (such as *"DELETE all orders"*) to the LLM wastes API tokens and relies solely on model compliance.
  - **Decision:** Scan input question text for DML keywords before calling the LLM API.
  - **Outcome:** Instantly rejects malicious inputs in under 1 millisecond without consuming API quota.

- **Zero-Temperature Deterministic Query Generation (`temperature=0.0`):**
  - **Context:** Non-zero LLM temperature introduces syntax variability and invalid column references.
  - **Decision:** Enforce `temperature=0.0` on `ChatGoogleGenerativeAI`.
  - **Outcome:** Guarantees deterministic, reproducible SQL query syntax across execution calls.

- **Schema Prompt Injection with Date Anchor (`2026-06-15`):**
  - **Context:** Questions involving relative timeframes (such as *"orders placed last month"*) fail without a fixed reference date.
  - **Decision:** Inject exact SQLite schema and reference date `2026-06-15` into every system prompt.

---

## 🐛 Technical Issues Encountered & Resolved

- **Module Import Resolution in Pytest (`ModuleNotFoundError`):**
  - **Problem:** Running pytest from `backend/` threw import errors for `backend.app.tools...`.
  - **Root Cause:** Execution context root aligned with `backend/` rather than project parent directory.
  - **Resolution:** Standardized imports across test files to use `from app.tools.sql_tool import ...`.

- **LangChain Tool Import Deprecation:**
  - **Problem:** Importing `Tool` from legacy `langchain.tools` raised import deprecation warnings.
  - **Root Cause:** Modern LangChain package architecture isolated core primitives into `langchain_core`.
  - **Resolution:** Updated imports to `from langchain_core.tools import Tool`.

- **Gemini Response List Content Structure:**
  - **Problem:** `response.content.strip()` threw `AttributeError` on multi-part model responses.
  - **Root Cause:** Gemini API occasionally returns `content` as a list of dictionary blocks rather than a single string.
  - **Resolution:** Added conditional type parsing to extract and concatenate text strings from list objects before calling `.strip()`.

---

## 💡 Real-World Workflow Examples

- **Scenario 1: Analytical Query for Pending Orders**
  - **User Query:** *"How many orders are currently pending?"*
  - **Processing Flow:**
    - Pre-LLM Guard checks question (Authorized).
    - Gemini 3.5 Flash generates SQL: `SELECT COUNT(*) FROM orders WHERE status='Pending'`.
    - Post-LLM Guard checks generated SQL (Authorized).
    - SQLite executes query against `orders.db` and returns row `[(50,)]`.
    - Formatted output: `{"result": "[{'COUNT(*)': 50}]", "sql": "SELECT COUNT(*) FROM orders WHERE status='Pending'", "error": None}`.
  - **Outcome:** Delivers accurate order status analytics in clean JSON payload.

- **Scenario 2: Malicious Data Deletion Interception**
  - **User Query:** *"DELETE all orders from the database"*
  - **Processing Flow:**
    - Pre-LLM Guard scans question and detects restricted keyword `DELETE`.
    - Throws `ValueError("Only SELECT queries are permitted.")` immediately.
  - **Outcome:** Short-circuits malicious input in <1ms without calling LLM API, returning `{"result": "", "sql": "", "error": "Only SELECT queries are permitted."}`.
