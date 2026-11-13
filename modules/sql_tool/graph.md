# SQL Tool Module Architecture

```mermaid
graph TD
    subgraph Natural Language Input
        A["User / Agent Question String"] --> B["Pre-LLM Security Guard"]
    end

    subgraph Pre-LLM Validation Stage
        B -->|Scan Restricted Keywords| C{"Question Contains DML?"}
        C -- Yes --> D["Raise ValueError: Only SELECT queries permitted"]
        C -- No --> E["System Prompt Builder"]
    end

    subgraph Text-to-SQL Translation Stage
        E -->|Inject Schema & Date Anchor 2026-06-15| F["Google Gemini 3.5 Flash (temp=0.0)"]
        F --> G["Raw Model Response Payload"]
        G --> H["Strip Markdown Code Fences (```sql)"]
        H --> I["Post-LLM Security Guard"]
    end

    subgraph Post-LLM Validation Stage
        I -->|Scan Generated SQL String| J{"Generated SQL Contains DML?"}
        J -- Yes --> D
        J -- No --> K["SQLite3 orders.db Database Connection"]
    end

    subgraph Query Execution & Payload Assembly
        K --> L["Execute SELECT Query"]
        L --> M["Fetch Rows & Extract Column Names"]
        M --> N["Format Dictionary List: dict(zip(columns, row))"]
        N --> O["Serialize Output: json.dumps({result, sql, error})"]
    end

    D --> P["Serialize Error Payload: json.dumps({result: '', sql: '', error})"]

    style B fill:#0369a1,stroke:#0284c7,color:#fff
    style F fill:#1e3a8a,stroke:#3b82f6,color:#fff
    style I fill:#047857,stroke:#059669,color:#fff
    style D fill:#991b1b,stroke:#ef4444,color:#fff
```

---

## 🔀 Dual DML Security Guard & SQL Translation Subsystem Flow Diagram

```mermaid
flowchart TD
    subgraph Engine Execution Start
        S0["run_sql_query(question)"] --> S1["Log Event: atomic_log('run_sql_query_start')"]
        S1 --> S2["Define DML Blocklist: DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE"]
    end

    subgraph Pre-LLM Dual Guard Check
        S2 --> G1["Convert question to UPPERCASE"]
        G1 --> G2{"Any Keyword in Upper Question?"}
        G2 -- True --> E1["Raise ValueError('Only SELECT queries are permitted.')"]
        G2 -- False --> L1["Initialize ChatGoogleGenerativeAI(model='gemini-3.5-flash', temp=0.0)"]
    end

    subgraph Prompt Injection & Translation
        L1 --> L2["Construct System Prompt: Inject Table Schema & Reference Date 2026-06-15"]
        L2 --> L3["Invoke LLM: llm.invoke(prompt)"]
        L3 --> L4["Parse Content & Strip Markdown Code Wrappers (```sql)"]
    end

    subgraph Post-LLM Dual Guard Check
        L4 --> G3["Convert Generated SQL to UPPERCASE"]
        G3 --> G4{"Any Keyword in Upper SQL?"}
        G4 -- True --> E1
        G4 -- False --> DB1["Resolve Absolute Path: backend/data/orders.db"]
    end

    subgraph SQLite Read Execution & Formatting
        DB1 --> DB2["Connect SQLite: sqlite3.connect(db_path)"]
        DB2 --> DB3["Execute Query: cursor.execute(sql_query)"]
        DB3 --> DB4["Fetch Rows & Extract Cursor Column Description"]
        DB4 --> DB5["Map Rows: [dict(zip(columns, row)) for row in rows]"]
        DB5 --> DB6["Log Success: atomic_log('run_sql_query_success')"]
        DB6 --> DB7["Return JSON: json.dumps({result, sql, error: None})"]
    end

    E1 -.-> E2["Catch Exception & Log Error: atomic_log('run_sql_query_error')"]
    E2 -.-> E3["Return Error JSON: json.dumps({result: '', sql, error: str(e)})"]

    style S0 fill:#1e293b,stroke:#475569,color:#fff
    style L3 fill:#1e3a8a,stroke:#3b82f6,color:#fff
    style DB3 fill:#065f46,stroke:#10b981,color:#fff
    style E3 fill:#991b1b,stroke:#ef4444,color:#fff
```

---

## 📖 Data Processing Pipeline Narrative

- **Dual Security Guard Path:**
  - Input question text is scanned for restricted DML keywords before calling LLM API.
  - Generated SQL text is re-scanned for restricted DML keywords before executing database query.
  - Any security violation short-circuits execution into a clean JSON error response.

- **Translation & Read-Only Execution Path:**
  - System prompt injects exact table schema (`orders`) and anchor date (`2026-06-15`).
  - Gemini 3.5 Flash generates read-only `SELECT` query with zero temperature.
  - SQLite database executes query, extracts column headers, and formats rows into key-value dictionaries.
