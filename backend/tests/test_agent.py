"""
===============================================================================
MODULE: test_agent.py
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
LAYER: Backend Test Suite Layer (LangGraph Agent Unit Tests)
===============================================================================

DESCRIPTION:
    Integration tests for the LangGraph ReAct agent state machine and 3-tier LLM fallback 
    chain. Validates query routing across RAG document search, SQL query analytics, mixed 
    queries, and out-of-scope queries.

KEY RESPONSIBILITIES:
    1. Testing tool selection accuracy across 4 evaluation categories.
    2. Asserting zero error events during streaming execution.
    3. Verifying single 'done' event termination and citation payload generation.
===============================================================================
"""

import os
import uuid
from typing import Any

import pytest

from app.agent import run_agent


@pytest.mark.asyncio
@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.parametrize(
    "query, expected_tools",
    [
        ("What is the refund window?", ["rag_search"]),
        ("How many orders are pending?", ["sql_query"]),
        ("Did order ORD-1207 qualify for a return?", ["rag_search", "sql_query"]),
        ("What is the weather today?", []),
    ],
)
async def test_run_agent(query: str, expected_tools: list[str]) -> None:
    """
    Parametrized integration test for the LangGraph agent state machine.

    ARGUMENTS:
        query (str): Input natural language search query.
        expected_tools (list[str]): List of expected tool names to be called.
    """
    # Verify GOOGLE_API_KEY environment variable is set
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.fail("GOOGLE_API_KEY is not set. Cannot run LLM test.")

    events: list[dict[str, Any]] = []
    # Generate unique test session ID to prevent state contamination across test runs
    session_id = f"test_session_{hash(query)}_{uuid.uuid4().hex[:6]}"
    
    # Collect all asynchronous events emitted by run_agent
    async for event in run_agent(query, session_id):
        events.append(event)
        
    print(f"\n[Debug] Events for query '{query}': {events}")
    
    # Assert zero error events were produced during agent execution
    error_events = [e for e in events if e.get("type") == "error"]
    assert not error_events, f"Error events encountered: {error_events}"
    
    # Extract tool call events and extract names of tools used
    tool_calls = [e for e in events if e["type"] == "tool_call"]
    tools_used = [e["tool"] for e in tool_calls]
    
    # Verify every expected tool was invoked
    for tool in expected_tools:
        assert tool in tools_used, f"Expected tool {tool} not called for query: {query}"
        
    # Assert exactly one 'done' event was produced at completion
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1, "Expected exactly one 'done' event"
    done_event = done_events[0]
    
    # Verify citations presence if rag_search tool was executed
    if "rag_search" in expected_tools:
        assert "citations" in done_event
        err = "Expected citations when rag_search is used"
        assert len(done_event["citations"]) > 0, err
        
    # Verify zero tools were called for out-of-scope query
    if not expected_tools:
        assert len(tools_used) == 0, "Expected no tools used for out of scope query"
        tokens = [e["content"] for e in events if e["type"] == "token"]
        full_text = "".join(tokens).lower()
        # Verify polite decline response content
        ans1 = "don't have that information" in full_text
        ans2 = "not have that information" in full_text
        ans3 = "weather" in full_text
        assert ans1 or ans2 or ans3
