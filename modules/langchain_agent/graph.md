# LangChain Agent Module Architecture

```mermaid
graph TD
    subgraph Natural Language Input
        A["User Search Query & Session Thread ID"] --> B["run_agent Async Generator"]
    end

    subgraph Pre-Routing & Prompt Construction
        B --> C["analyse_intent Pre-Router (<0.5ms)"]
        C --> D["Yield Event: intent"]
        C --> E["build_system_prompt Function"]
        E --> F["Inject Intent Soft Hints into BASE_SYSTEM_PROMPT"]
    end

    subgraph LangGraph State Machine Execution
        F --> G["graph.astream_events(version='v2')"]
        G <-->|Load / Save History via thread_id| H[("MemorySaver Checkpointer")]
        G --> I["call_model Node"]
    end

    subgraph 3-Tier Fallback LLM Chain
        I --> J{"Primary Model: gemini-3.5-flash"}
        J -- Rate Limit / Error --> K{"Fallback 1: gemini-3.1-pro"}
        K -- Rate Limit / Error --> L{"Fallback 2: gemini-3.1-flash-lite"}
        J --> M["AIMessage Output"]
        K --> M
        L --> M
    end

    subgraph Conditional Routing & Tool Execution
        M --> N{"should_continue Edge Check"}
        N -- Contains tool_calls --> O["call_tool Node"]
        O -->|Execute Query| P["rag_search_tool"]
        O -->|Execute Query| Q["sql_query_tool"]
        P -->|JSON String| I
        Q -->|JSON String| I
        N -- No tool_calls --> R["END Node"]
    end

    subgraph SSE Async Event Yield Stream
        G --> S1["Yield Event: token"]
        O --> S2["Yield Event: tool_call"]
        O --> S3["Yield Event: tool_result & rag_trace"]
        R --> S4["Yield Event: done"]
    end

    style B fill:#0369a1,stroke:#0284c7,color:#fff
    style J fill:#1e3a8a,stroke:#3b82f6,color:#fff
    style N fill:#701a75,stroke:#d946ef,color:#fff
    style S4 fill:#047857,stroke:#059669,color:#fff
```

---

## 🔀 LangGraph StateMachine & SSE Event Streaming Subsystem Flow Diagram

```mermaid
flowchart TD
    subgraph Event Generator Entry
        E0["run_agent(query, session_id)"] --> E1["analyse_intent(query)"]
        E1 --> E2["Yield SSE Event: {'type': 'intent', 'labels': intent}"]
        E2 --> E3["build_system_prompt(BASE_SYSTEM_PROMPT, intent)"]
    end

    subgraph LangGraph AST Event Stream Loop
        E3 --> G0["graph.astream_events(inputs, version='v2', config)"]
        G0 --> G1["Loop AST Event Stream (v2)"]
        
        G1 -->|kind == 'on_chat_model_stream'| T1["Extract Content Chunk"]
        T1 --> T2{"Chunk Content is List?"}
        T2 -- Yes --> T3["Iterate Parts & Extract text"]
        T2 -- No --> T4["Extract String Content"]
        T3 --> T5["Yield SSE Event: {'type': 'token', 'content': token}"]
        T4 --> T5
        
        G1 -->|kind == 'on_tool_start'| TC1["Extract Tool Name & Input Query"]
        TC1 --> TC2["Yield SSE Event: {'type': 'tool_call', 'tool': name, 'query': input}"]
        
        G1 -->|kind == 'on_tool_end'| TR1["Parse Output JSON String"]
        TR1 --> TR2{"Tool Name?"}
        TR2 -- sql_query --> TR3["Yield SSE Event: {'type': 'tool_result', 'sql': sql}"]
        TR2 -- rag_search --> TR4["Accumulate Citations & Yield SSE Event: {'type': 'rag_trace', 'details': trace}"]
        
        G1 -->|kind == 'on_chat_model_end'| M1["Extract Telemetry model_name"]
    end

    subgraph Final Delivery & Exception Handling
        G1 --> D1["Deduplicate Citations: list(dict.fromkeys(citations))"]
        D1 --> D2["Yield SSE Event: {'type': 'done', 'tool_used': tools, 'citations': citations, 'model_used': model}"]
        
        G0 -.->|On Exception| ERR1["Catch Exception in try-except block"]
        ERR1 -.-> ERR2["Yield SSE Event: {'type': 'error', 'code': 'TOOL_FAILURE', 'message': str(e)}"]
    end

    style E0 fill:#1e293b,stroke:#475569,color:#fff
    style J fill:#1e3a8a,stroke:#3b82f6,color:#fff
    style D2 fill:#065f46,stroke:#10b981,color:#fff
    style ERR2 fill:#991b1b,stroke:#ef4444,color:#fff
```

---

## 📖 Data Processing Pipeline Narrative

- **Pre-Routing & Prompt Stage:**
  - Intent router classifies query in <0.5ms and yields an `intent` SSE event.
  - Soft prompt hints are appended to `BASE_SYSTEM_PROMPT` for the current execution turn.

- **State Graph & Fallback LLM Stage:**
  - LangGraph executes `call_model`, using the 3-tier fallback LLM chain (`gemini-3.5-flash` $\rightarrow$ `gemini-3.1-pro` $\rightarrow$ `gemini-3.1-flash-lite`).
  - `should_continue` routes to node `tools` if tool calls are requested, returning `ToolMessage` outputs back to `agent`.

- **Event Streaming Stage:**
  - `run_agent` listens to AST stream events (`v2`), yielding `token`, `tool_call`, `tool_result`, `rag_trace`, and `done` events in real-time.