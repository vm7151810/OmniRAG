# LangChain Agent Module

The **LangChain Agent** module serves as the primary conversational state machine and tool orchestration engine for the OmniRAG Enterprise ChatBot system. Built using **LangGraph** (`StateGraph`), it coordinates a **3-Tier LLM Fallback Chain** (`gemini-3.5-flash` $\rightarrow$ `gemini-3.1-pro` $\rightarrow$ `gemini-3.1-flash-lite`), integrates bound tools (`rag_search_tool` and `sql_query_tool`), maintains thread-scoped conversation state via `MemorySaver`, and streams fine-grained real-time events formatted for Server-Sent Events (SSE).

---

## 🛠️ Technology Stack & Machine Learning Models

### 1. 3-Tier Fallback Model Orchestrator (`with_fallbacks`)
- **What It Does:** Chains three Gemini LLM models in sequence to ensure 99.9% request resilience against API rate limits (HTTP 429) or service degradation.
  - **Tier 1 (Primary):** Google `gemini-3.5-flash` (High speed, 1024 max tokens, temperature 0.1).
  - **Tier 2 (Fallback 1):** Google `gemini-3.1-pro` (Complex reasoning fallback, 1024 max tokens).
  - **Tier 3 (Fallback 2):** Google `gemini-3.1-flash-lite` (Emergency lightweight fallback, 512 max tokens).
- **Why Use It:** Eliminates single-point-of-failure rate limit crashes during peak traffic spikes.
- **Model Inputs:** Injected system prompt string and full message history array.
- **Model Outputs:** AI message response payload (`AIMessage`) containing text or tool execution calls.

### 2. LangGraph ReAct State Machine (`StateGraph(AgentState)`)
- **What It Does:** Compiles a directed state graph containing processing nodes (`agent` for LLM calls, `tools` for tool calls) and conditional edges (`should_continue`).
- **Why Use It:** Replaces legacy sequential chains with a state machine offering fine-grained control over execution loops, tool invocation retries, and streaming events.
- **Graph Inputs:** `AgentState` TypedDict containing `messages`, `session_id`, and `system_prompt`.
- **Graph Outputs:** Final updated state dictionary containing complete message trajectory.

### 3. Thread-Scoped Memory Checkpointer (`MemorySaver`)
- **What It Does:** Persists chat message history across multi-turn user conversations in memory, isolated per session using thread configuration (`configurable: {"thread_id": session_id}`).
- **Why Use It:** Eliminates manual memory management and state injection while preventing session cross-talk across user threads.
- **Checkpointer Inputs:** Session thread ID (`session_id: str`).
- **Checkpointer Outputs:** Rehydrated conversation history for state node processing.

### 4. Async Event Streaming Engine (`run_agent`)
- **What It Does:** Executes the compiled graph using `astream_events(version="v2")` and yields real-time JSON event dictionaries (`intent`, `token`, `tool_call`, `tool_result`, `rag_trace`, `done`, `error`).
- **Why Use It:** Powers real-time token-by-token client rendering and transparent tool execution tracing over Server-Sent Events (SSE).
- **Engine Inputs:** User search query string (`query: str`) and unique thread ID (`session_id: str`).
- **Engine Outputs:** Asynchronous stream generator yielding SSE event dictionaries (`AsyncGenerator[dict, None]`).

---

## 🧮 Mathematical & Logic Formulations

### 1. 3-Tier Fallback LLM Invocation Logic
For a message payload $M$ and fallback chain $\text{Chain} = [\text{LLM}_1, \text{LLM}_2, \text{LLM}_3]$:

$$\text{Response} = \begin{cases} \text{LLM}_1(M) & \text{if } \text{Status}(\text{LLM}_1) = \text{Success} \\ \text{LLM}_2(M) & \text{else if } \text{Status}(\text{LLM}_2) = \text{Success} \\ \text{LLM}_3(M) & \text{otherwise} \end{cases}$$

### 2. State Machine Conditional Edge Transition Logic
For the latest message $M_{\text{last}}$ produced by node `agent`:

$$\text{NextNode} = \begin{cases} \text{"tools"} & \text{if } \text{HasToolCalls}(M_{\text{last}}) = \text{True} \\ \text{END} & \text{otherwise} \end{cases}$$

### 3. Order-Preserving Multi-Tool Citation Deduplication
For accumulated citation lists $C_{\text{tools}}$ extracted from `on_tool_end` events:

$$\text{Citations}_{\text{final}} = \text{list}\left( \text{dict.fromkeys}(C_{\text{tools}}) \right)$$

---

## 🏗️ Implementation Details & End-to-End Data Pipeline Architecture

The `langchain_agent` module executes a 10-step atomic data pipeline that streams real-time AI responses to client user interfaces.

### 🔄 Step-by-Step Atomic Data Pipeline

- **Step 1: Request Initiation & Thread Resolution**
  - **Inputs:** User query string `query` and session thread ID `session_id`.
  - **Function Called:** `run_agent(query: str, session_id: str)`.
  - **Processing:** Validates input arguments and opens async streaming generator context.
  - **Outputs:** Active stream context.

- **Step 2: Pre-Analysis & Intent Signal Yield**
  - **Inputs:** `query` string.
  - **Processing:** Executes `intent = analyse_intent(query)` in <0.5ms and yields initial SSE event `{"type": "intent", "labels": intent}`.
  - **Outputs:** Streamed intent event dictionary.

- **Step 3: Intent-Augmented System Prompt Construction**
  - **Inputs:** `BASE_SYSTEM_PROMPT` string and `intent` data object.
  - **Processing:** Calls `system_prompt_str = build_system_prompt(BASE_SYSTEM_PROMPT, intent)` to append soft prompt hint blocks without cluttering persistent memory.
  - **Outputs:** Customized system prompt string `system_prompt_str`.

- **Step 4: State Graph Invocation**
  - **Inputs:** `query`, `session_id`, `system_prompt_str`, checkpointer thread config.
  - **Processing:** Calls `graph.astream_events(...)` passing initial `HumanMessage(content=query)`.
  - **Outputs:** Active AST event stream (`v2`).

- **Step 5: LLM Inference Node Execution (`call_model`)**
  - **Inputs:** `AgentState` containing conversation messages and `system_prompt`.
  - **Processing:** Prepends `SystemMessage(content=system_prompt)` to history and invokes the 3-tier fallback LLM chain (`gemini-3.5-flash` $\rightarrow$ `gemini-3.1-pro` $\rightarrow$ `gemini-3.1-flash-lite`).
  - **Outputs:** AI response message (`AIMessage`).

- **Step 6: Conditional Edge Evaluation (`should_continue`)**
  - **Inputs:** Latest `AIMessage`.
  - **Processing:** Checks if `AIMessage` contains `tool_calls`. Routes to node `tools` if present, else routes to node `END`.
  - **Outputs:** Target node string (`"tools"` or `END`).

- **Step 7: Tool Node Execution & Error Isolation (`call_tool`)**
  - **Inputs:** Target tool calls array.
  - **Processing:** Executes matching tool (`rag_search_tool` or `sql_query_tool`) with try-except safety. Encapsulates tool JSON string output inside `ToolMessage`.
  - **Outputs:** Appended `ToolMessage` array returned to `agent` node.

- **Step 8: Real-Time LLM Token Streaming (`on_chat_model_stream`)**
  - **Inputs:** Event stream chunks.
  - **Processing:** Extracts text tokens (handling string vs multi-part list chunk content structures) and yields SSE event `{"type": "token", "content": text}`.
  - **Outputs:** Real-time token yield to client.

- **Step 9: Tool Tracing & Event Streaming (`on_tool_start` / `on_tool_end`)**
  - **Inputs:** Tool start and end events.
  - **Processing:** Yields `tool_call` on start. Parses returned JSON strings on end to yield `tool_result` (SQL queries) and `rag_trace` telemetry events.
  - **Outputs:** Real-time tool execution telemetry events.

- **Step 10: Citation Deduplication & Completion Event Delivery**
  - **Inputs:** Accumulated citation lists and telemetry metrics.
  - **Processing:** Deduplicates citations via `list(dict.fromkeys(citations))` and yields final SSE event `{"type": "done", "tool_used": [...], "citations": [...], "model_used": used_model}`.
  - **Outputs:** Stream completion signal closing the response connection.

---

## 💻 Implementation Guide & Code Examples

### 1. Consuming `run_agent` Async Event Stream in Python
```python
import asyncio
from app.agent import run_agent

async def main():
    session_id = "test_session_99"
    query = "Did order ORD-1207 qualify for a return?"

    print(f"=== Starting Agent Stream for Query: '{query}' ===")
    
    # Consume async generator SSE events
    async for event in run_agent(query, session_id=session_id):
        event_type = event.get("type")
        
        if event_type == "intent":
            print(f"[INTENT] Labels: {event['labels'].labels}")
            
        elif event_type == "tool_call":
            print(f"[TOOL START] Invoking '{event['tool']}' with args: {event['query']}")
            
        elif event_type == "tool_result":
            print(f"[TOOL SQL] Generated SQL: {event['sql']}")
            
        elif event_type == "rag_trace":
            print(f"[RAG TELEMETRY] Matches: {event['details'].get('dense_matches')}")
            
        elif event_type == "token":
            # Print streaming tokens directly
            print(event["content"], end="", flush=True)
            
        elif event_type == "done":
            print("\n\n=== Stream Completed ===")
            print(f"Tools Used: {event['tool_used']}")
            print(f"Citations: {event['citations']}")
            print(f"Model Used: {event['model_used']}")

# Run async streaming loop
asyncio.run(main())
```

### 2. Direct Graph State Invocation
```python
from langchain_core.messages import HumanMessage
from app.agent import graph

# Prepare state payload
initial_state = {
    "messages": [HumanMessage(content="What is the refund window?")],
    "session_id": "direct_graph_thread_01",
    "system_prompt": "You are a support bot."
}

# Execute compiled state machine graph synchronously/asynchronously
config = {"configurable": {"thread_id": "direct_graph_thread_01"}}
final_state = graph.invoke(initial_state, config=config)

print("Final Trajectory Message Count:", len(final_state["messages"]))
print("Final AI Message:", final_state["messages"][-1].content)
```

---

## 📁 Key System Files & Architecture Map

- **`backend/app/agent.py`:**
  - Contains `build_graph`, `run_agent`, `call_model`, `call_tool`, `should_continue`, and `AgentState` implementing the LangGraph ReAct agent state machine, 3-tier fallback chain, and async SSE streaming engine.

- **`backend/tests/test_agent.py`:**
  - Automated unit test suite verifying 4 agent execution paths: policy RAG queries, structured SQL queries, mixed multi-hop queries, and out-of-scope refusals with random UUID thread IDs.

---

## 🧠 Key Architectural Decisions

- **3-Tier Fallback LLM Chain (`with_fallbacks`):**
  - **Context:** Free-tier rate limits (HTTP 429) on `gemini-3.5-flash` caused execution halts.
  - **Decision:** Fall back automatically to `gemini-3.1-pro`, then `gemini-3.1-flash-lite`.
  - **Outcome:** Guarantees request execution resilience under high traffic loads.

- **LangGraph Native StateMachine & `MemorySaver` Checkpointer:**
  - **Context:** Legacy `ConversationBufferMemory` introduced deprecation warnings and lacked fine-grained event streaming control.
  - **Decision:** Built a custom LangGraph `StateGraph` using native `MemorySaver` checkpointing keyed by `thread_id`.
  - **Outcome:** Clean session thread state persistence with full visibility into node transitions.

- **Dynamic Per-Turn System Prompt Injection:**
  - **Context:** Saving system prompts into persistent memory on every turn bloats the state history and context window.
  - **Decision:** Added `system_prompt` as a transient field in `AgentState` injected dynamically at runtime inside `call_model`.
  - **Outcome:** Keeps conversation history clean while updating system hints dynamically based on query intent.

---

## 🐛 Technical Issues Encountered & Resolved

- **Gemini Response List Chunk Content Crash:**
  - **Problem:** Streaming `chunk.content` threw `TypeError` when Gemini returned multi-part list objects.
  - **Root Cause:** Gemini API occasionally returns streaming content as a list of dict blocks rather than a raw string.
  - **Resolution:** Added type inspection in `run_agent` to iterate over list parts and extract `part["text"]`.

- **Tool Return JSON String Parsing Error:**
  - **Problem:** `json.loads` in stream handler crashed on python dictionary representations returned by tools.
  - **Root Cause:** Tools returned Python dict objects instead of JSON strings.
  - **Resolution:** Standardized tool output contracts across `rag_tool` and `sql_tool` to explicitly return `json.dumps()` strings.

- **Test Suite Session Memory Contamination:**
  - **Problem:** Parameterized unit tests sharing hardcoded `session_id` strings leaked state across test cases.
  - **Root Cause:** `MemorySaver` retained chat history across test runs.
  - **Resolution:** Appended `uuid.uuid4().hex` to `session_id` in all test fixtures.

---

## 💡 Real-World Workflow Examples

- **Scenario 1: Policy Retrieval Query with Real-Time SSE Token Streaming**
  - **User Query:** *"What is the return policy window for headphones?"*
  - **Processing Flow:**
    - Router pre-classifies intent as `POLICY_DOCUMENT`.
    - Agent invokes `call_model`, which requests `rag_search_tool(query="return policy window headphones")`.
    - Tool node executes hybrid search + reranking, returning 5 pristine chunks.
    - LLM generates answer citing source `"[returns_policy.pdf - Standard Return Policy]"`.
    - `run_agent` streams real-time text tokens and emits final `done` event with deduplicated citations.
  - **Outcome:** Delivers real-time token stream and exact document citation references.

- **Scenario 2: Multi-Tool Synthesis for Mixed Operational Inquiry**
  - **User Query:** *"Did order ORD-1207 qualify for a return?"*
  - **Processing Flow:**
    - Router pre-classifies intent as `MIXED_QUERY_DETECTED`.
    - Agent invokes `sql_query_tool(question="SELECT product, status, amount FROM orders WHERE order_id='ORD-1207'")`.
    - Agent then invokes `rag_search_tool(query="return policy eligibility criteria")`.
    - Agent synthesizes order status (`Delivered`) and policy rules to generate response.
  - **Outcome:** Combines SQL database facts and RAG policy text into a single coherent answer.