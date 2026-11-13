# FastAPI Service Module Architecture

```mermaid
graph TD
    subgraph Client Application Layer
        UI["Next.js Web Frontend / API Client"]
    end

    subgraph FastAPI Service Endpoints
        UI -->|GET /health| H["GET /health Endpoint"]
        UI -->|POST /chat| C["POST /chat Endpoint"]
    end

    subgraph FastAPI Internal Pipeline
        C --> T1["Generate Trace ID: uuid.uuid4()"]
        T1 --> T2["Log Invocation: logger.info('chat_endpoint_invoked')"]
        T2 --> T3["Initialize Async Event Generator: event_generator()"]
        T3 --> A1["Invoke LangChain Agent: run_agent(query, session_id)"]
    end

    subgraph Agent Event Streaming Loop
        A1 --> E1["Receive Agent Async Events"]
        E1 --> E2["Encode Payload: jsonable_encoder(event)"]
        E2 --> E3["Format SSE Data Frame: data: <JSON>\n\n"]
        E3 --> E4["Stream Response Chunk (StreamingResponse)"]
        E4 --> UI
    end

    subgraph Observability Layer
        T2 -.-> L1["structlog Telemetry Logger"]
        L1 -.->|DEBUG=true| L2["JSON Stream Output (sys.stdout)"]
        L1 -.->|DEBUG=false| L3["NullHandler (Silent Overhead)"]
    end

    style C fill:#0369a1,stroke:#0284c7,color:#fff
    style A1 fill:#1e3a8a,stroke:#3b82f6,color:#fff
    style E4 fill:#047857,stroke:#059669,color:#fff
```

---

## 🔀 FastAPI SSE Streaming & Structlog Logging Subsystem Flow Diagram

```mermaid
flowchart TD
    subgraph Request Intake
        R0["Client Request: POST /chat"] --> R1["Parse Pydantic Body: ChatRequest(query, session_id)"]
        R1 --> R2["Generate Request Trace ID: trace_id = str(uuid.uuid4())"]
        R2 --> R3["Log Invocation: logger.info('chat_endpoint_invoked', trace_id, data)"]
    end

    subgraph Structlog Processor Pipeline
        R3 --> L0["structlog.get_logger(__name__)"]
        L0 --> L1["TimeStamper(fmt='iso')"]
        L1 --> L2["rename_event_to_action (event -> action, logger -> module)"]
        L2 --> L3["drop_level (removes level key)"]
        L3 --> L4{"settings.DEBUG == True?"}
        L4 -- True --> L5["JSONRenderer() -> sys.stdout"]
        L4 -- False --> L6["logging.NullHandler() (Silent)"]
    end

    subgraph SSE Stream Framing Loop
        R2 --> S0["Open StreamingResponse(event_generator(), media_type='text/event-stream')"]
        S0 --> S1["Set Header: X-Accel-Buffering = 'no'"]
        S1 --> S2["async for event in run_agent(query, session_id)"]
        S2 --> S3["FastAPI jsonable_encoder(event)"]
        S3 --> S4["json.dumps(encoded_event)"]
        S4 --> S5["Format Frame: f'data: {json_str}\n\n'"]
        S5 --> S6["Yield SSE Frame to HTTP Stream"]
    end

    subgraph Error Interception
        S2 -.->|On Exception| E1["logger.info('chat_endpoint_error', trace_id, data)"]
        E1 -.-> E2["Format Error Event: {'type': 'error', 'code': 'TOOL_FAILURE', 'message': str(e)}"]
        E2 -.-> E3["Yield SSE Frame: data: {'type': 'error', ...}\n\n"]
    end

    style R0 fill:#1e293b,stroke:#475569,color:#fff
    style S0 fill:#1e3a8a,stroke:#3b82f6,color:#fff
    style S6 fill:#065f46,stroke:#10b981,color:#fff
    style E3 fill:#991b1b,stroke:#ef4444,color:#fff
```

---

## 📖 Data Processing Pipeline Narrative

- **Request Handling & Middleware Stage:**
  - FastAPI handles CORS headers and parses request bodies using the `ChatRequest` schema.
  - Generates a unique request `trace_id` for end-to-end tracing.

- **Streaming & Encoding Stage:**
  - Invokes `run_agent` async generator and encodes yielded payloads via `jsonable_encoder`.
  - Packages events into standard SSE data frames (`data: <JSON>\n\n`) and streams them with unbuffered headers (`X-Accel-Buffering: no`).

- **Structured Logging Stage:**
  - `structlog` pipeline attaches ISO-8601 UTC timestamps, renames fields, strips levels, and writes single-line JSON logs to `sys.stdout` when `DEBUG=true`.
