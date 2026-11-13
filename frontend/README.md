# Next.js UI Module

The **Next.js UI** module provides the frontend web interface for the OmniRAG Enterprise ChatBot system. Built on **Next.js 15 (App Router)**, **React 19**, **Tailwind CSS**, and **shadcn/ui**, it features a dark-mode glassmorphism aesthetic, a cold-start backend health polling loop, real-time Server-Sent Events (SSE) stream parsing, interactive markdown rendering, SQL query viewers, and document citation drawers.

---
## How to run it
```bash
cd frontend
pnpm run dev
```

## Configuration
- `BACKEND_URL`: URL of the FastAPI backend for proxying API requests (defaults to `http://localhost:8000`).

---

## 🛠️ Technology Stack & Machine Learning Models

### 1. Web Presentation Framework: Next.js 15 (App Router) & React 19
- **What It Does:** Serves the client-side single-page application (SPA), manages layout structures, client state transitions, and server-side logging routes.
- **Why Use It:** Delivers fast page loads, automatic code splitting, optimized asset bundling, and clean React 19 hook APIs.
- **Framework Inputs:** User browser interactions and example prompt button clicks.
- **Framework Outputs:** Interactive HTML5 DOM nodes and Server-Sent Events stream consumer logic.

### 2. Design System & Styling: Tailwind CSS & shadcn/ui
- **What It Does:** Renders a floating frosted-glass user interface (`backdrop-blur`, semi-transparent backgrounds, subtle glowing borders, custom scrollbars) with animated loading spinners, terminal code blocks, and pill badge indicators.
- **Why Use It:** Provides responsive, accessible UI components with zero CSS bloat and smooth micro-animations.
- **Styling Inputs:** Theme design tokens and component props.
- **Styling Outputs:** Styled DOM elements with glassmorphism visual aesthetics.

### 3. SSE Stream Reader Engine (`ReadableStreamDefaultReader` & `TextDecoder`)
- **What It Does:** Consumes binary HTTP response streams from `POST /chat`, decodes UTF-8 byte chunks, splits text buffers by newlines, parses JSON event objects (`data: <JSON>\n\n`), and dispatches state updates across 6 discrete event types (`intent`, `token`, `tool_call`, `tool_result`, `done`, `error`).
- **Why Use It:** Enables token-by-token typewriter text animation and transparent tool reasoning indicators without page refreshes.
- **Engine Inputs:** `text/event-stream` response from backend `/chat` endpoint.
- **Engine Outputs:** Real-time state updates for active tools, tokens, SQL blocks, and citation lists.

### 4. Client Telemetry Engine (`logger.ts` & `/api/log`)
- **What It Does:** Captures user actions and streaming events in the browser and dispatches structured JSON log payloads to the server proxy `/api/log` when `process.env.DEBUG=true`.
- **Why Use It:** Conforms strictly to the project Atomic Logging Standard without polluting client browser consoles.
- **Logger Inputs:** Log payload containing `module`, `action`, `trace_id`, and `data`.
- **Logger Outputs:** JSON POST payload sent to server logging proxy.

---

## 🧮 Mathematical & Formatting Formulations

### 1. SSE Stream Line Buffer Splitting Algorithm
For an incoming decoded stream chunk $V_k$ and prior buffer string $B_{k-1}$:

$$B_{\text{temp}} = B_{k-1} + \text{Decode}(V_k)$$

$$\text{Lines} = \text{SplitByNewline}(B_{\text{temp}})$$

$$B_k = \text{Lines}.\text{pop}() \quad \text{(Retain partial incomplete line for next iteration)}$$

$$\forall L \in \text{Lines} \mid L.\text{startsWith}(\text{"data: "}) \implies \text{ParseEvent}(L.\text{substring}(6))$$

### 2. Non-Mutative Message State Update Formulation
For a token event carrying text $T_{\text{token}}$ target message ID $\text{id}_{\text{target}}$:

$$S_{\text{next}} = S_{\text{prev}}.\text{map}\left( M_i \mapsto \begin{cases} M_i \text{ with } \text{content} = M_i.\text{content} + T_{\text{token}} & \text{if } M_i.\text{id} = \text{id}_{\text{target}} \\ M_i & \text{otherwise} \end{cases} \right)$$

---

## 🏗️ Implementation Details & End-to-End Data Pipeline Architecture

The `nextjs_ui` module executes a 10-step atomic data pipeline that drives the user interface.

### 🔄 Step-by-Step Atomic Data Pipeline

- **Step 1: Healthcheck Cold-Start Polling Loop**
  - **Inputs:** Mount event of `Home` page component (`page.tsx`).
  - **Processing:** `useEffect` hook pings `GET ${NEXT_PUBLIC_API_URL}/health` every 2 seconds. Displays `"Waking up the AI engine..."` screen until backend responds HTTP 200 OK.
  - **Outputs:** Transition state `healthStatus = 'ready'`.

- **Step 2: User Query Submission & State Setup**
  - **Inputs:** User text input or example prompt click.
  - **Function Called:** `handleSend(text: string)` in `ChatContainer.tsx`.
  - **Processing:** Creates user `Message` object and placeholder assistant `Message` object (`isGenerating: true`), appending both to `messages` state.
  - **Outputs:** Updated `messages` state array.

- **Step 3: Client Telemetry Event Dispatch**
  - **Inputs:** Message payload and generated request trace ID (`req-timestamp`).
  - **Function Called:** `logger.info({ module: 'ChatContainer.tsx', action: 'chat_submitted', ... })`.
  - **Processing:** Dispatches POST request to `/api/log` proxy endpoint.
  - **Outputs:** Server-side JSON log line.

- **Step 4: Asynchronous HTTP Fetch Dispatch**
  - **Inputs:** User query string and session ID (`default`).
  - **Processing:** Issues `fetch(`${apiUrl}/chat`, { method: 'POST', body: ... })` with `Content-Type: application/json`.
  - **Outputs:** HTTP 200 `StreamingResponse` stream object.

- **Step 5: UTF-8 Stream Reader Initialization**
  - **Inputs:** `response.body`.
  - **Processing:** Obtains stream reader (`response.body.getReader()`) and instantiates `TextDecoder()`.
  - **Outputs:** Reader reference and decoder instance.

- **Step 6: Binary Chunk Decoding & Buffer Splitting**
  - **Inputs:** Binary stream value chunks.
  - **Processing:** Decodes bytes to string, appends to `buffer`, splits buffer by `\n`, and pops remaining incomplete partial line into `buffer`.
  - **Outputs:** Complete SSE line array `lines`.

- **Step 7: SSE Event Frame Parsing**
  - **Inputs:** Lines starting with `data: `.
  - **Processing:** Strips prefix (`line.substring(6).trim()`) and parses JSON payload via `JSON.parse(dataStr)`.
  - **Outputs:** Event dictionary (`type`, `content`, `tool`, `sql`, `citations`, `message`).

- **Step 8: Discrete Event Type Handling**
  - **Inputs:** Event dictionary.
  - **Processing:**
    - `token`: Appends `event.content` to active assistant message text.
    - `tool_call`: Updates `activeTool` string (e.g. `"🔍 Searching policy documents..."`).
    - `tool_result`: Captures `event.sql` string for terminal viewer and clears `activeTool`.
    - `done`: Sets `isGenerating: false` and attaches `event.citations` list.
    - `error`: Triggers `toast.error()` toast notification.
  - **Outputs:** Updated message state object.

- **Step 9: Real-Time Component Rendering**
  - **Inputs:** Updated `messages` state array.
  - **Processing:** Renders user bubbles (vibrant gradient), assistant bubbles (frosted glass with `ReactMarkdown`), active reasoning badges, terminal SQL viewer blocks, and document citation tags.
  - **Outputs:** Updated DOM visual interface.

- **Step 10: Smooth Auto-Scroll Execution**
  - **Inputs:** DOM ref `scrollRef`.
  - **Processing:** `useEffect` triggers `scrollRef.current.scrollIntoView({ behavior: 'smooth' })` whenever `messages` updates.
  - **Outputs:** Smoothly scrolled viewport centered on latest tokens.

---

## 💻 Implementation Guide & Code Examples

### 1. Launching the Next.js Frontend Development Server
```bash
# Navigate to frontend directory
cd frontend

# Install package dependencies
pnpm install

# Launch Next.js dev server on port 3000
pnpm dev
```

### 2. Environment Configuration (`.env.local`)
Create `.env.local` inside `frontend/` directory:
```bash
# Backend FastAPI Service Base URL
NEXT_PUBLIC_API_URL=http://localhost:8000

# Enable Client/Server Telemetry Logging
DEBUG=true
```

### 3. Consuming Chat SSE Stream via Custom Hook Pattern
```typescript
import { useState } from "react";

export function useChatStream() {
  const [content, setContent] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);

  const streamQuery = async (query: string) => {
    setIsStreaming(true);
    setContent("");

    const response = await fetch("http://localhost:8000/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, session_id: "demo_user" }),
    });

    if (!response.body) return;

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const event = JSON.parse(line.substring(6));
          if (event.type === "token") {
            setContent((prev) => prev + event.content);
          }
        }
      }
    }
    setIsStreaming(false);
  };

  return { content, isStreaming, streamQuery };
}
```

---

## 📁 Key System Files & Architecture Map

- **`frontend/src/app/page.tsx`:**
  - Landing page component managing cold-start health check polling (`GET /health`), project architecture explanation card, system date badge (`15 June 2026`), and example prompt triggers.

- **`frontend/src/components/chat/ChatContainer.tsx`:**
  - Core chat interface handling user message submissions, SSE stream parsing, active reasoning badge displays, SQL terminal blocks, document citations, and auto-scrolling.

- **`frontend/src/lib/logger.ts`:**
  - Client/server logging utility formatting telemetry objects and forwarding client logs to `/api/log`.

- **`frontend/src/lib/utils.ts`:**
  - Class name merging utility combining `clsx` and `tailwind-merge` (`cn`).

---

## 🧠 Key Architectural Decisions

- **Glassmorphism Dark Mode Aesthetic & System Date Badge (`15 June 2026`):**
  - **Context:** Standard white enterprise templates lack visual distinction.
  - **Decision:** Designed a floating frosted-glass theme (`backdrop-blur-md`, subtle glowing borders) featuring an explicit date badge (`15 June 2026`).
  - **Outcome:** Delivers a premium, state-of-the-art user interface.

- **Streaming Line Buffer Splitting for Multiline Chunk Parsing:**
  - **Context:** Network chunks frequently arrive split across SSE data lines or contain multiple event frames in a single read.
  - **Decision:** Implement buffer accumulation (`buffer += decoder.decode`) and split by `\n`, preserving unparsed trailing fragments (`buffer = lines.pop()`).
  - **Outcome:** Eliminates JSON parse crashes during high-speed token streaming.

- **Client Telemetry Proxying via Server API Route (`/api/log`):**
  - **Context:** Direct browser `console.log` statements pollute developer consoles and fail to record server-side logs.
  - **Decision:** Proxy client log events to a Next.js server route that outputs single-line JSON logs when `DEBUG=true`.
  - **Outcome:** Enforces the Atomic Logging Standard seamlessly across client and server runtimes.

---

## 🐛 Technical Issues Encountered & Resolved

- **Partial JSON Frame Parse Errors:**
  - **Problem:** `JSON.parse()` threw syntax errors on long tokens.
  - **Root Cause:** Stream chunks broke in the middle of a `data: {...}` line across network TCP frames.
  - **Resolution:** Implemented trailing line buffer retainment (`buffer = lines.pop() || ""`) to defer parsing until complete lines arrive.

- **Auto-Scroll Screen Jitter:**
  - **Problem:** Smooth scrolling triggered on every token frame caused screen jitter during rapid token generation.
  - **Root Cause:** Excessive `scrollIntoView` invocations per second.
  - **Resolution:** Attached `scrollIntoView` to `messages` array state updates with `behavior: "smooth"`.

- **Hydration Mismatch on Initial Render:**
  - **Problem:** Server and client HTML output differed on initial page load.
  - **Root Cause:** Date generation and window checks executing during SSR.
  - **Resolution:** Enforced `"use client"` directive on interactive components and moved window-dependent logic into `useEffect` hooks.

---

## 💡 Real-World Workflow Examples

- **Scenario 1: Cold-Start Readiness Handshake**
  - **User Experience:** User opens chatbot URL while backend container is cold-starting on Render.
  - **Processing Flow:** `page.tsx` displays `"Waking up the AI engine..."` with an animated spinner, polling `GET /health` every 2s until HTTP 200 OK is returned.
  - **Outcome:** Automatically transitions to full chat interface once backend is warm without requiring page refreshes.

- **Scenario 2: Multi-Tool Mixed Query Execution**
  - **User Query:** *"Did order ORD-1207 qualify for a return?"*
  - **Processing Flow:**
    - User submits query; `ChatContainer` appends user bubble and assistant placeholder bubble.
    - SSE stream receives `tool_call` for `sql_query` $\rightarrow$ Displays `"🗃️ Querying order database..."` badge.
    - SSE stream receives `tool_result` with SQL string $\rightarrow$ Renders SQL code terminal block.
    - SSE stream receives `tool_call` for `rag_search` $\rightarrow$ Displays `"🔍 Searching policy documents..."` badge.
    - SSE stream receives `token` events $\rightarrow$ Types out synthesized answer in real time.
    - SSE stream receives `done` event with citations $\rightarrow$ Appends document citations list.
  - **Outcome:** Visually guides the user through each step of the multi-tool reasoning process.
