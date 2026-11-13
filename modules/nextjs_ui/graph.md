# Next.js UI Module Architecture

```mermaid
graph TD
    subgraph Browser Client Presentation Layer
        Page["Home Page (app/page.tsx)"] --> Health["Cold-Start Health Poller: GET /health"]
        Page --> Sidebar["Info Sidebar & Example Prompts"]
        Page --> Container["ChatContainer (components/chat/ChatContainer.tsx)"]
    end

    subgraph Component State Management
        Container --> State["React Message State Array (messages)"]
        State --> UserBubble["User Message Bubbles (Gradient)"]
        State --> AssistantBubble["Assistant Message Bubbles (Frosted Glass)"]
        State --> ReasoningBadge["Active Tool Reasoning Badges"]
        State --> TerminalBlock["SQL Query Terminal Viewer"]
        State --> CitationDrawer["Document Citations Tags"]
    end

    subgraph SSE Stream Reader Subsystem
        Container --> Fetch["HTTP POST fetch(/chat)"]
        Fetch --> Stream["ReadableStreamDefaultReader & TextDecoder"]
        Stream --> Buffer["Newline Line Buffer Splitter"]
        Buffer --> Parser["JSON Event Frame Parser (data: <JSON>)"]
        Parser --> Dispatcher["Event Type Dispatcher"]
    end

    subgraph Event Handling Dispatcher
        Dispatcher -->|type: token| TokenHandler["Append Text Tokens to Message Content"]
        Dispatcher -->|type: tool_call| ToolCallHandler["Set Active Tool Badge Indicator"]
        Dispatcher -->|type: tool_result| ToolResultHandler["Store SQL Query String & Clear Badge"]
        Dispatcher -->|type: done| DoneHandler["Set isGenerating=false & Attach Citations"]
        Dispatcher -->|type: error| ErrorHandler["Trigger Sonner Error Toast"]
    end

    subgraph Server Telemetry Proxy
        Container -.-> Logger["logger.ts Utility"]
        Logger -.-> Proxy["POST /api/log Server Route"]
        Proxy -.-> Console["Atomic JSON Log (sys.stdout)"]
    end

    style Container fill:#0369a1,stroke:#0284c7,color:#fff
    style Stream fill:#1e3a8a,stroke:#3b82f6,color:#fff
    style Dispatcher fill:#701a75,stroke:#d946ef,color:#fff
    style DoneHandler fill:#047857,stroke:#059669,color:#fff
```

---

## 🔀 Next.js SSE Stream Reader & State Management Subsystem Flow Diagram

```mermaid
flowchart TD
    subgraph Submission & Initialization
        S0["User Clicks Send / Example Prompt"] --> S1["Create User Message & Assistant Placeholder Message"]
        S1 --> S2["Append Messages to State & Set isLoading = true"]
        S2 --> S3["Dispatch Telemetry Log: logger.info('chat_submitted')"]
        S3 --> S4["Execute fetch('/chat', { method: 'POST', body })"]
    end

    subgraph Binary Chunk Reading & Line Buffering
        S4 --> R0["Obtain Stream Reader: response.body.getReader()"]
        R0 --> R1["Read Chunk: reader.read()"]
        R1 --> R2{"Is Stream Done?"}
        R2 -- Yes --> F0["Set isLoading = false"]
        R2 -- No --> R3["Decode Bytes: TextDecoder.decode(value, { stream: true })"]
        R3 --> R4["Append to Buffer: buffer += decodedChunk"]
        R4 --> R5["Split Buffer: lines = buffer.split('\n')"]
        R5 --> R6["Retain Trailing Partial Line: buffer = lines.pop() || ''"]
    end

    subgraph SSE Event Framing & State Dispatch
        R6 --> E0["Loop Lines Array"]
        E0 --> E1{"Line Starts With 'data: '?"}
        E1 -- No --> R1
        E1 -- Yes --> E2["Extract JSON String: line.substring(6).trim()"]
        E2 --> E3["Parse JSON: event = JSON.parse(dataStr)"]
        
        E3 --> E4{"event.type?"}
        E4 -- token --> D1["msg.content += event.content"]
        E4 -- tool_call --> D2["msg.activeTool = 'Searching...' / 'Querying...'"]
        E4 -- tool_result --> D3["msg.sql = event.sql, msg.activeTool = undefined"]
        E4 -- done --> D4["msg.isGenerating = false, msg.citations = event.citations"]
        E4 -- error --> D5["toast.error(event.message)"]
        
        D1 --> R1
        D2 --> R1
        D3 --> R1
        D4 --> R1
        D5 --> R1
    end

    style S0 fill:#1e293b,stroke:#475569,color:#fff
    style R0 fill:#1e3a8a,stroke:#3b82f6,color:#fff
    style E3 fill:#701a75,stroke:#d946ef,color:#fff
    style D4 fill:#065f46,stroke:#10b981,color:#fff
    style D5 fill:#991b1b,stroke:#ef4444,color:#fff
```

---

## 📖 Data Processing Pipeline Narrative

- **Submission Stage:**
  - `ChatContainer` creates user and assistant placeholder messages, updates state, logs submission telemetry via `/api/log`, and issues `POST /chat`.

- **Stream Reader & Buffer Stage:**
  - Binary UTF-8 chunks are read asynchronously, accumulated into a string buffer, and split by `\n`.
  - Trailing unparsed partial lines are retained in the buffer to prevent JSON syntax errors across TCP packet boundaries.

- **State Dispatch Stage:**
  - Parsed SSE event frames update assistant message state attributes (`content`, `activeTool`, `sql`, `citations`, `isGenerating`).
  - React components re-render automatically, and `scrollIntoView` smooth-scrolls the chat viewport.
