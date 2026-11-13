"""
===============================================================================
MODULE: agent.py
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
LAYER: Backend Agent Orchestration Layer (LangGraph ReAct Agent)
===============================================================================

DESCRIPTION:
    This module builds and executes the LangGraph ReAct Agent state machine (`graph`) 
    and async event streaming engine (`run_agent`). It manages the 3-tier LLM fallback 
    chain (`gemini-3.5-flash` -> `gemini-3.1-pro` -> `gemini-3.1-flash-lite`), state 
    checkpointing via `MemorySaver`, tool binding (`rag_search_tool`, `sql_query_tool`), 
    and real-time token/tool event yields for SSE streaming.

KEY RESPONSIBILITIES:
    1. Defining `AgentState` TypedDict for LangGraph state management.
    2. Constructing the 3-Tier Fallback LLM chain using Google Gemini models.
    3. Compiling the LangGraph ReAct StateGraph with nodes (`agent`, `tools`), 
       conditional routing (`should_continue`), and thread-scoped `MemorySaver` checkpointer.
    4. Executing `run_agent` async generator to stream real-time events (`intent`, `token`, 
       `tool_call`, `tool_result`, `rag_trace`, `done`, `error`) via AST events (`v2`).
===============================================================================
"""

import json
import os
from collections.abc import AsyncGenerator, Sequence
from typing import Annotated, Any, TypedDict

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables.config import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from app.config import settings
from app.routing.intent_router import analyse_intent, build_system_prompt
from app.tools.rag_tool import rag_search_tool
from app.tools.sql_tool import sql_query_tool


class AgentState(TypedDict):
    """
    TypedDict representing the state object passed across LangGraph nodes.

    ATTRIBUTES:
        messages (Sequence[BaseMessage]): Accumulated list of chat messages using add_messages reducer.
        session_id (str): Unique thread identifier for session persistence.
        system_prompt (str): Injected system prompt string tailored by intent router.
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    session_id: str
    system_prompt: str


# Base system prompt defining assistant identity, rules, date anchor, and schema constraints
BASE_SYSTEM_PROMPT = """You are the Northwind Gadgets AI support assistant.
Today's date is 15 June 2026.

You have two tools:
- rag_search: for questions about company policies (returns, warranty, HR leave,
  pricing, product FAQ)
- sql_query: for questions about specific orders, revenue totals, order counts,
  or customer order history

Rules:
1. Always cite sources using the numeric brackets. Place the bracket AFTER
   the punctuation (e.g., "end of sentence.[1]"). Do not write file names inline.
2. CRITICAL RULE: NEVER output the raw SQL query in your text response.
   Answer naturally; the UI will render the SQL separately.
3. For mixed questions (involving both a policy and an order), call BOTH tools
4. If a question is outside your knowledge, respond:
   "I don't have that information."
5. Never hallucinate policy text or SQL column names that don't exist
   in the schema
6. The orders table columns are: order_id, customer, product, amount,
   status, order_date"""


def build_graph() -> Any:
    """
    Constructs and compiles the 3-tier fallback LangGraph ReAct agent state machine.

    RETURNS:
        CompiledStateGraph: Compiled LangGraph executable graph with MemorySaver checkpointer.
    """
    # List of executable tools available to the agent
    tools = [rag_search_tool, sql_query_tool]

    # Resilient 4-tier Gemini fallback architecture using verified active endpoints:
    # Tier 1: Primary Model — Gemini 2.5 Flash for high speed, reasoning, and tool calling
    # Tier 2: First Fallback — Gemini 2.5 Flash-Lite for fast, low-latency fallback
    # Tier 3: Second Fallback — Gemini 3.5 Flash-Lite for high-throughput document extraction
    # Tier 4: Emergency Fallback — Gemini 3.1 Flash-Lite for high-availability backup
    fallback_candidates = [
        ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            api_key=settings.GOOGLE_API_KEY,
            temperature=0.1,
            max_output_tokens=1024,
            max_retries=2,
        ),
        ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            api_key=settings.GOOGLE_API_KEY,
            temperature=0.1,
            max_output_tokens=1024,
            max_retries=2,
        ),
        ChatGoogleGenerativeAI(
            model="gemini-3.5-flash-lite",
            api_key=settings.GOOGLE_API_KEY,
            temperature=0.1,
            max_output_tokens=1024,
            max_retries=2,
        ),
        ChatGoogleGenerativeAI(
            model="gemini-3.1-flash-lite",
            api_key=settings.GOOGLE_API_KEY,
            temperature=0.1,
            max_output_tokens=1024,
            max_retries=2,
        ),
    ]

    # Explicitly bind tools to EACH model instance before chaining with with_fallbacks
    models_with_tools = [model.bind_tools(tools) for model in fallback_candidates]
    llm_with_tools = models_with_tools[0].with_fallbacks(models_with_tools[1:])
    
    def call_model(state: AgentState) -> dict[str, Any]:
        """Node: Invokes the LLM with system prompt and accumulated conversation history."""
        messages = state['messages']
        # Fetch injected system prompt or fall back to BASE_SYSTEM_PROMPT
        sys_prompt = state.get("system_prompt", BASE_SYSTEM_PROMPT)
        # Prepend SystemMessage header to the messages sequence
        full_messages = [SystemMessage(content=sys_prompt)] + list(messages)
        # Invoke LLM model with complete message sequence
        response = llm_with_tools.invoke(full_messages)
        return {"messages": [response]}
        
    def call_tool(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        """Node: Executes requested tool calls from the last AI message."""
        messages = state['messages']
        last_message = messages[-1]
        
        tool_messages: list[ToolMessage] = []
        # Verify last message contains tool_calls attribute
        if hasattr(last_message, "tool_calls"):
            for tool_call in last_message.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                # Find matching tool instance by name
                tool = next(t for t in tools if t.name == tool_name)
                try:
                    # Execute tool invocation
                    result = tool.invoke(tool_args, config=config)
                    tool_messages.append(ToolMessage(
                        content=json.dumps(result),
                        tool_call_id=tool_call["id"],
                        name=tool_name
                    ))
                except Exception as e:
                    # Safely capture tool execution exception into ToolMessage
                    tool_messages.append(ToolMessage(
                        content=json.dumps({"error": str(e)}),
                        tool_call_id=tool_call["id"],
                        name=tool_name
                    ))
                
        return {"messages": tool_messages}
        
    def should_continue(state: AgentState) -> str:
        """Conditional Edge: Decides whether to route to 'tools' or finish at END."""
        messages = state['messages']
        last_message = messages[-1]
        # Check if last AI message requested tool execution calls
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        # Otherwise terminate loop and transition to END node
        return END

    # Step 1: Initialize StateGraph with AgentState schema
    workflow = StateGraph(AgentState)
    # Step 2: Add 'agent' and 'tools' processing nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", call_tool)
    # Step 3: Add graph edges
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent", should_continue, {"tools": "tools", END: END}
    )
    workflow.add_edge("tools", "agent")
    
    # Step 4: Initialize in-memory thread checkpointer
    checkpointer = MemorySaver()
    # Step 5: Compile graph with checkpointer
    return workflow.compile(checkpointer=checkpointer)

# Instantiate global compiled agent graph
graph = build_graph()


async def run_agent(
    query: str, session_id: str
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Executes agent loop asynchronously, streaming fine-grained events for SSE response handling.

    ARGUMENTS:
        query (str): Input natural language search query string.
        session_id (str): Unique thread ID for state checkpointing.

    YIELDS:
        dict[str, Any]: Streamed event dictionaries ('intent', 'token', 'tool_call', 
                        'tool_result', 'rag_trace', 'done', 'error').
    """
    # Step 1: Pre-classify intent using microsecond zero-LLM router
    intent = analyse_intent(query)
    # Yield intent classification event
    yield {"type": "intent", "labels": intent}
    # Build customized system prompt with injected intent soft hints
    system_prompt_str = build_system_prompt(BASE_SYSTEM_PROMPT, intent)
    
    used_tools: list[str] = []
    citations: list[str] = []
    citation_details: list[dict[str, Any]] = []
    ai_response_content = ""
    used_model = "unknown"
    
    try:
        # Step 2: Stream graph events asynchronously using astream_events v2
        async for event in graph.astream_events(
            {
                "messages": [HumanMessage(content=query)], 
                "session_id": session_id,
                "system_prompt": system_prompt_str
            }, 
            version="v2",
            config={
                "configurable": {"thread_id": session_id},
                "metadata": {
                    "agent_id": os.getenv("LANGSMITH_AGENT_ID", "omnirag"),
                    "environment": os.getenv("LANGSMITH_AGENT_ENVIRONMENT", "local"),
                },
                "tags": [
                    "omnirag",
                    os.getenv("LANGSMITH_AGENT_ENVIRONMENT", "local"),
                ],
                "run_name": "omnirag-agent",
            }
        ):
            kind = event["event"]
            
            # Event 1: LLM Token Streaming
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if hasattr(chunk, "content") and chunk.content:
                    if isinstance(chunk.content, list):
                        for part in chunk.content:
                            part_text = ""
                            if isinstance(part, str):
                                part_text = part
                            elif isinstance(part, dict) and "text" in part:
                                part_text = part["text"]
                            
                            if part_text:
                                ai_response_content += part_text
                                yield {"type": "token", "content": part_text}
                    else:
                        ai_response_content += chunk.content
                        yield {"type": "token", "content": chunk.content}
                        
            # Event 2: Tool Execution Start
            elif kind == "on_tool_start":
                tool_name = event["name"]
                query_sent = event["data"].get("input", {})
                used_tools.append(tool_name)
                yield {"type": "tool_call", "tool": tool_name, "query": str(query_sent)}
                
            # Event 3: Tool Execution Complete
            elif kind == "on_tool_end":
                tool_name = event["name"]
                output = event["data"].get("output", {})
                content_str = (
                    output.content if hasattr(output, "content") else str(output)
                )
                
                try:
                    result_dict = json.loads(content_str)
                    # Extract SQL string from sql_query tool result
                    if tool_name == "sql_query" and "sql" in result_dict:
                        yield {
                            "type": "tool_result",
                            "tool": tool_name,
                            "sql": result_dict["sql"]
                        }
                    # Extract citations and telemetry trace from rag_search tool result
                    if tool_name in ("rag_search", "rag_search_tool"):
                        if "citations" in result_dict:
                            citations.extend(result_dict["citations"])
                        if "citation_details" in result_dict:
                            citation_details.extend(result_dict["citation_details"])
                        if "trace" in result_dict:
                            yield {
                                "type": "rag_trace",
                                "details": result_dict["trace"]
                            }
                except Exception:  # noqa: S110
                    pass
                    
            # Event 4: LLM Inference Complete (capture model telemetry name)
            elif kind == "on_chat_model_end":
                try:
                    output = event.get("data", {}).get("output")
                    if hasattr(output, "response_metadata") and output.response_metadata:
                        used_model = output.response_metadata.get(
                            "model_name", "unknown"
                        )
                    elif isinstance(output, dict) and "response_metadata" in output:
                        used_model = output["response_metadata"].get(
                            "model_name", "unknown"
                        )
                    if used_model in ("unknown", "", None):
                        used_model = (
                            event.get("metadata", {}).get("ls_model_name")
                            or event.get("name", "gemini-2.5-flash")
                        )
                except Exception:  # noqa: S110
                    pass
                print(f"\n[Agent] LLM Call complete. Model used: {used_model}")
        
        # Step 3: Deduplicate citations and citation_details while preserving rank order
        unique_citations = list(dict.fromkeys(citations))
        seen_sources: set[str] = set()
        unique_details = []
        for cd in citation_details:
            key = f"{cd.get('source')}-{cd.get('title')}"
            if key not in seen_sources:
                seen_sources.add(key)
                unique_details.append(cd)

        # Yield final execution completion event
        yield {
            "type": "done",
            "tool_used": list(set(used_tools)),
            "citations": unique_citations,
            "citation_details": unique_details,
            "model_used": used_model
        }
        
    # Step 4: Handle agent errors gracefully and stream error event
    except Exception as e:
        print(f"Agent Error: {e}")
        yield {"type": "error", "code": "TOOL_FAILURE", "message": str(e)}
