# FastAPI Service Module

The **FastAPI Service** module provides the HTTP API backend layer for the OmniRAG Enterprise ChatBot system. Built on **FastAPI** and **Uvicorn**, it exposes a readiness healthcheck endpoint (`GET /health`), orchestrates asynchronous **Server-Sent Events (SSE)** streaming for the Next.js frontend (`POST /chat`), handles Cross-Origin Resource Sharing (CORS), and enforces the **Atomic Logging Standard** via `structlog`.

---

## 🛠️ Technology Stack & Machine Learning Models

### 1. High-Performance Web Framework: FastAPI & Uvicorn
- **What It Does:** Serves HTTP REST endpoints and handles asynchronous client requests with high concurrency.
- **Why Use It:** Provides automatic OpenAPI documentation, async event loop native support, and Pydantic request body validation.
- **Framework Inputs:** HTTP REST requests (`GET /health`, `POST /chat`).
- **Framework Outputs:** JSON responses and asynchronous SSE streaming responses.

### 2. Server-Sent Events (SSE) Streaming Engine (`StreamingResponse`)
- **What It Does:** Streams real-time asynchronous agent events (`intent`, `token`, `tool_call`, `tool_result`, `rag_trace`, `done`, `error`) as newline-delimited SSE data frames (`data: <JSON>\n\n`).
- **Why Use It:** Delivers token-by-token client UI rendering and unbuffered proxy streaming using the `X-Accel-Buffering: no` header.
- **Engine Inputs:** `ChatRequest(query: str, session_id: str)` and async generator events from `run_agent`.
- **Engine Outputs:** `text/event-stream` response stream.

### 3. Structured Telemetry Engine: `structlog` & Atomic Logger
- **What It Does:** Formats all backend events into single-line JSON log strings containing ISO-8601 UTC timestamps, module names, action titles, trace IDs, and custom data objects.
- **Why Use It:** Enables production observability and log aggregation while remaining completely silent when `DEBUG=false`.
- **Logger Inputs:** Action title (`action: str`), trace ID (`trace_id: str`), and telemetry dictionary (`data: dict`).
- **Logger Outputs:** Standardized single-line JSON strings written to `sys.stdout`.

### 4. Pydantic Event Payload Serializer (`jsonable_encoder`)
- **What It Does:** Encodes complex or nested Pydantic model objects returned by `run_agent` into standard JSON-compatible Python dictionaries before string serialization.
- **Why Use It:** Prevents `TypeError: Object of type IntentAnalysis is not JSON serializable` crashes during event streaming.
- **Serializer Inputs:** Arbitrary agent event payload dictionaries.
- **Serializer Outputs:** JSON-serializable dictionary objects.

---

## 🧮 Mathematical & Formatting Formulations

### 1. SSE Data Frame Packaging Protocol
For an agent event object $E_{\text{event}}$ yielded by `run_agent`:

$$\text{EncodedDict} = \text{jsonable\_encoder}(E_{\text{event}})$$

$$\text{SSEFrame} = \text{"data: "} + \text{json.dumps}(\text{EncodedDict}) + \text{FrameTerminator}$$

- **Example Output Frame:**
  `data: {"type": "token", "content": "Products purchased within 30 days..."}\n\n`

### 2. Atomic Structured JSON Log Schema
For a telemetry event with module name $M$, action title $A$, trace ID $T$, and payload dictionary $D$:

$$\text{LogObject} = \{ \text{"timestamp"}: \text{ISO8601\_UTC}(), \text{"module"}: M, \text{"action"}: A, \text{"trace\_id"}: T, \text{"data"}: D \}$$

$$\text{LogString} = \text{json.dumps}(\text{LogObject})$$

---

## 🏗️ Implementation Details & End-to-End Data Pipeline Architecture

The `fastapi_service` module executes a 9-step atomic data pipeline that routes client requests and streams AI responses.

### 🔄 Step-by-Step Atomic Data Pipeline

- **Step 1: Request Reception & CORS Middleware Processing**
  - **Inputs:** Incoming HTTP request from client frontend.
  - **Processing:** FastAPI CORS middleware validates request headers, methods, and origins.
  - **Outputs:** Authorized HTTP request context.

- **Step 2: Pydantic Request Body Parsing (`ChatRequest`)**
  - **Inputs:** `POST /chat` JSON payload.
  - **Processing:** Parses and validates `query: str` and `session_id: str` fields.
  - **Outputs:** Validated `ChatRequest` model instance.

- **Step 3: Unique Trace ID Generation & Telemetry Logging**
  - **Inputs:** Request context.
  - **Processing:** Generates unique UUID string (`trace_id = str(uuid.uuid4())`) and emits structured log `logger.info("chat_endpoint_invoked", trace_id=trace_id, ...)`.
  - **Outputs:** `trace_id` string and stdout log entry.

- **Step 4: Async SSE Event Generator Initialization**
  - **Inputs:** `request.query`, `request.session_id`, `trace_id`.
  - **Processing:** Opens async generator function `event_generator()` to process streaming yields.
  - **Outputs:** Async event iterator.

- **Step 5: LangChain Agent Event Loop Invocation**
  - **Inputs:** `request.query` and `request.session_id`.
  - **Function Called:** `run_agent(request.query, request.session_id)`.
  - **Processing:** Subscribes to `astream_events` from the underlying agent graph.
  - **Outputs:** Streamed event dictionaries (`intent`, `token`, `tool_call`, `tool_result`, `rag_trace`, `done`).

- **Step 6: Pydantic Event Payload Encoding**
  - **Inputs:** Raw event payload dictionary.
  - **Processing:** Passes payload to `jsonable_encoder(event)` to safely handle nested dataclasses or Pydantic models.
  - **Outputs:** Encoded JSON-compatible dictionary object.

- **Step 7: SSE Data Frame Packaging & Yielding**
  - **Inputs:** Encoded event dictionary.
  - **Processing:** Formats frame string `f"data: {json.dumps(encoded_event)}\n\n"` and yields to client stream connection.
  - **Outputs:** SSE formatted data frame string.

- **Step 8: Health & Readiness Endpoint Servicing (`GET /health`)**
  - **Inputs:** `GET /health` request.
  - **Processing:** Checks service readiness and returns status payload `{"status": "ok", "pinecone_connected": True, "sqlite_rows": 200, "model": "gemini-3.5-flash"}`.
  - **Outputs:** HTTP 200 JSON response.

- **Step 9: Stream Exception Interception & Error Frame Delivery**
  - **Inputs:** Uncaught stream exception.
  - **Processing:** Logs error via `logger.info("chat_endpoint_error", ...)` and yields error frame `data: {"type": "error", "code": "TOOL_FAILURE", "message": str(e)}\n\n`.
  - **Outputs:** SSE error event frame closing stream.

---

## 💻 Implementation Guide & Code Examples

### 1. Launching the Backend FastAPI Uvicorn Server
```bash
# Navigate to backend directory
cd backend

# Launch Uvicorn dev server on port 8000 with hot reload
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Testing `GET /health` Readiness Endpoint
```bash
# Execute cURL request to verify backend readiness
curl -X GET http://localhost:8000/health
```

**Expected JSON Response:**
```json
{
  "status": "ok",
  "pinecone_connected": true,
  "sqlite_rows": 200,
  "model": "gemini-3.5-flash"
}
```

### 3. Consuming `POST /chat` SSE Stream in Python Client
```python
import httpx
import asyncio

async def consume_chat_stream():
    url = "http://localhost:8000/chat"
    payload = {
        "query": "What is the return policy window for headphones?",
        "session_id": "python_demo_session"
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, json=payload) as response:
            print(f"HTTP Response Status: {response.status_code}")
            print(f"Content-Type Header: {response.headers.get('content-type')}\n")
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    # Extract JSON payload string after 'data: ' prefix
                    json_str = line[6:]
                    print(f"[SSE EVENT] {json_str}")

# Execute async stream test
asyncio.run(consume_chat_stream())
```

---

## 📁 Key System Files & Architecture Map

- **`backend/app/main.py`:**
  - Contains FastAPI app instance, CORS middleware configuration, `ChatRequest` Pydantic model, `GET /health` healthcheck, and `POST /chat` SSE streaming endpoint.

- **`backend/app/logger.py`:**
  - Configures `structlog` pipeline (`rename_event_to_action`, `drop_level`, `sys.stdout` stream handler, `NullHandler` silencer).

- **`backend/tests/test_api.py`:**
  - Automated test suite verifying healthcheck endpoint, SSE `/chat` stream event frames (`intent`, `token`, `done`), and logger silencing behavior.

---

## 🧠 Key Architectural Decisions

- **FastAPI `jsonable_encoder` Payload Serialization:**
  - **Context:** `run_agent` yielded nested Pydantic models (such as `IntentAnalysis`) that caused standard `json.dumps()` to throw type errors.
  - **Decision:** Wrap every yielded event in FastAPI's `jsonable_encoder` before string serialization.
  - **Outcome:** Guarantees error-free JSON serialization across all SSE event types.

- **Unbuffered Proxy Headers (`X-Accel-Buffering: no`):**
  - **Context:** Reverse proxies (such as NGINX or Render) buffer HTTP response streams by default, breaking real-time token streaming.
  - **Decision:** Attach `headers={"X-Accel-Buffering": "no"}` to the `StreamingResponse`.
  - **Outcome:** Ensures instant, zero-delay token streaming to client browsers.

- **Custom `drop_if_not_debug` Logger Silencer:**
  - **Context:** Print statements clutter test output and violate production logging standards.
  - **Decision:** Configure `structlog` with `NullHandler` when `DEBUG=false` and `sys.stdout` when `DEBUG=true`.
  - **Outcome:** Completely silent execution in production/tests unless explicitly requested.

---

## 🐛 Technical Issues Encountered & Resolved

- **Missing `structlog` Dependency in TDD Phase:**
  - **Problem:** Running initial logger tests threw `ModuleNotFoundError: No module named 'structlog'`.
  - **Root Cause:** Package manager had not installed `structlog` in virtual environment.
  - **Resolution:** Ran `uv add structlog` to install dependency into `pyproject.toml`.

- **Pydantic Model SSE Stream Serialization Crash:**
  - **Problem:** `/chat` stream crashed with `TypeError: Object of type IntentAnalysis is not JSON serializable`.
  - **Root Cause:** `IntentAnalysis` dataclass returned inside `intent` events could not be serialized directly by standard `json.dumps`.
  - **Resolution:** Wrapped all events in `jsonable_encoder()` before calling `json.dumps()`.

- **Duplicate Logger Handlers in Test Runners:**
  - **Problem:** Running pytest repeatedly produced duplicate stdout log entries.
  - **Root Cause:** Root logger accumulated handlers across test function invocations.
  - **Resolution:** Cleared `root_logger.handlers` in `get_logger()` before attaching new handlers.

---

## 💡 Real-World Workflow Examples

- **Scenario 1: Healthcheck Cold-Start Poll**
  - **Client Action:** Deployment platform (Render) sends `GET /health` to verify service readiness.
  - **Processing Flow:** FastAPI handler checks database connectivity and returns `200 OK` JSON payload.
  - **Outcome:** Returns `{"status": "ok", "pinecone_connected": true, "sqlite_rows": 200, "model": "gemini-3.5-flash"}` in <5ms.

- **Scenario 2: Real-Time SSE Chat Session Streaming**
  - **Client Action:** Frontend posts `POST /chat` with query `"What is the refund window?"`.
  - **Processing Flow:**
    - FastAPI generates trace ID and logs endpoint invocation.
    - Agent runs, yielding `intent`, `tool_call`, `tool_result`, `token`, and `done` events.
    - SSE stream packages each event into `data: <JSON>\n\n` data frames.
  - **Outcome:** Streams real-time tokens to browser UI, enabling instant typing animations.
