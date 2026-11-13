# Intent Router Module Architecture

```mermaid
graph TD
    subgraph Natural Language Input
        A["User Query String"] --> B["analyse_intent Engine (<0.5ms)"]
    end

    subgraph Microsecond In-Memory Analysis
        B --> C["Normalize Text: Lowercase"]
        C --> D["Set Intersections: Static Keyword Matching"]
        C --> E["Dynamic Customer Lookup: _dynamic_customers"]
        C --> F["Regex Match: ORD_REGEX r'\bord-\d+\b'"]
    end

    subgraph Intent Classification Matrix
        D --> G{"Evaluate Intent Matrix"}
        E --> G
        F --> G
        G -->|Both Signals or ORD ID| H["MIXED_QUERY_DETECTED (conf=0.95)"]
        G -->|Data Signals Only| I["STRUCTURED_DATA (conf=0.90)"]
        G -->|Policy Signals Only| J["POLICY_DOCUMENT (conf=0.90)"]
        G -->|Off-topic Match| K["OUT_OF_SCOPE (conf=0.99)"]
    end

    subgraph Soft System Prompt Injection
        H --> L["build_system_prompt Function"]
        I --> L
        J --> L
        K --> L
        L --> M["Injected System Prompt with Soft Hints"]
        M --> N["Downstream Agent Execution"]
    end

    style B fill:#0369a1,stroke:#0284c7,color:#fff
    style G fill:#701a75,stroke:#d946ef,color:#fff
    style M fill:#047857,stroke:#059669,color:#fff
```

---

## 🔀 Dynamic Customer Lookup & Intent Analysis Subsystem Flow Diagram

```mermaid
flowchart TD
    subgraph Startup Initialization
        M0["Module Load / Startup"] --> M1["_initialize_customers Function"]
        M1 --> M2{"SQLite orders.db Exists?"}
        M2 -- Yes --> M3["SELECT customer FROM orders"]
        M2 -- No --> M4{"orders.csv Exists?"}
        M4 -- Yes --> M5["Parse CSV Customer Header Column"]
        M3 --> M6["Populate _dynamic_customers set"]
        M5 --> M6
    end

    subgraph Query Execution Stage
        Q0["analyse_intent(query)"] --> Q1["Convert query to Lowercase"]
        Q1 --> Q2["Extract Keyword Substrings: data, policy, out_of_scope"]
        Q1 --> Q3["Evaluate Customer Name Match: any(cust in query_lower)"]
        Q1 --> Q4["Evaluate Regex Match: bool(ORD_REGEX.search(query_lower))"]
    end

    subgraph Decision Tree Logic
        Q2 --> D1{"is_mixed == True?"}
        Q3 --> D1
        Q4 --> D1
        D1 -- True --> R1["Create IntentAnalysis: MIXED_QUERY_DETECTED, conf=0.95"]
        D1 -- False --> D2{"len(data_matches) > 0?"}
        D2 -- True --> R2["Create IntentAnalysis: STRUCTURED_DATA, conf=0.90"]
        D2 -- False --> D3{"len(policy_matches) > 0?"}
        D3 -- True --> R3["Create IntentAnalysis: POLICY_DOCUMENT, conf=0.90"]
        D3 -- False --> D4{"len(out_of_scope) > 0?"}
        D4 -- True --> R4["Create IntentAnalysis: OUT_OF_SCOPE, conf=0.99"]
        D4 -- False --> R5["Create IntentAnalysis: OUT_OF_SCOPE, conf=0.50"]
    end

    subgraph Prompt Builder Integration
        R1 --> B1["build_system_prompt(base_prompt, intent)"]
        R2 --> B1
        R3 --> B1
        R4 --> B1
        R5 --> B1
        B1 --> B2["Return Enhanced System Prompt String"]
    end

    style M6 fill:#065f46,stroke:#10b981,color:#fff
    style Q0 fill:#1e293b,stroke:#475569,color:#fff
    style D1 fill:#701a75,stroke:#d946ef,color:#fff
    style B2 fill:#1e3a8a,stroke:#3b82f6,color:#fff
```

---

## 📖 Data Processing Pipeline Narrative

- **Dynamic Startup Phase:**
  - `orders.db` (or `orders.csv` fallback) is read at startup to extract unique customer full names into `_dynamic_customers`.

- **Intent Analysis Phase:**
  - Query string is lowercased and matched against static keyword sets, dynamic customer sets, and `ORD_REGEX` patterns.
  - Returns `IntentAnalysis` data object with labels, actionable hint text, and confidence score in <0.5ms.

- **System Prompt Injection Phase:**
  - `build_system_prompt` formats soft hint blocks and appends them to the base agent system prompt.
  - The downstream agent uses enriched prompt context to make autonomous tool choices.
