"""
===============================================================================
MODULE: test_api.py
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
LAYER: Backend Test Suite Layer (FastAPI API & SSE Endpoint Tests)
===============================================================================

DESCRIPTION:
    Integration tests for FastAPI endpoints (`GET /health` and `POST /chat`). 
    Validates health response payloads, CORS headers, SSE response stream headers 
    (`text/event-stream`, `X-Accel-Buffering: no`), and structlog DEBUG behavior.

KEY RESPONSIBILITIES:
    1. Testing `GET /health` status code and JSON payload keys.
    2. Testing `POST /chat` streaming response format and SSE `data: ` line encoding.
    3. Testing structlog DEBUG=false (silenced) vs DEBUG=true (JSON rendering) behavior.
===============================================================================
"""

import json
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agent import graph
from app.logger import get_logger
from app.main import app

# Instantiate TestClient with FastAPI app
client = TestClient(app)


def test_health_endpoint() -> None:
    """Test the GET /health endpoint for Render cold-start status polling."""
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    expected_status = "ok"
    assert data["status"] == expected_status
    
    # Assert pinecone_connected indicator key is present
    pinecone_key = "pinecone_connected"
    assert pinecone_key in data


def test_chat_endpoint_streaming(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test the POST /chat endpoint SSE streaming response format.
    Monkeypatches ChatGoogleGenerativeAI to avoid real LLM calls during endpoint testing.
    """
    # Define fake astream_events async generator to mock LLM event streaming
    async def fake_astream_events(
        *args: Any,
        **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        # Create dummy chunk object with content attribute
        chunk_obj = type("Chunk", (), {"content": "Hello"})()
        yield {"event": "on_chat_model_stream", "data": {"chunk": chunk_obj}}

    # Monkeypatch the graph's astream_events method to use the mock generator
    monkeypatch.setattr(graph, "astream_events", fake_astream_events)
        
    payload = {"query": "test query", "session_id": "test_session"}
    # Stream POST request to /chat endpoint
    with client.stream("POST", "/chat", json=payload) as response:
        assert response.status_code == 200
        
        # Verify Content-Type header specifies text/event-stream
        actual_content_type = response.headers.get("content-type")
        is_event_stream = "text/event-stream" in str(actual_content_type)
        assert is_event_stream
        
        # Verify X-Accel-Buffering header is set to 'no'
        no_buffer = "no"
        assert response.headers.get("x-accel-buffering") == no_buffer
        
        # Read the first line of the event stream
        for line in response.iter_lines():
            if line:
                decoded_line = line
                prefix = "data: "
                has_prefix = decoded_line.startswith(prefix)
                assert has_prefix
                
                # Verify payload line is valid JSON
                json_str = decoded_line[len(prefix):]
                event_data = json.loads(json_str)
                type_key = "type"
                assert type_key in event_data
                assert event_data[type_key] != "error", (
                    f"Stream returned an error: {event_data}"
                )
                break


def test_logging_behavior_debug_false(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str]
) -> None:
    """Test that setting DEBUG=false silences log output to stdout."""
    monkeypatch.setattr("app.config.settings.DEBUG", False)
    
    logger = get_logger("test_silent")
    logger.info("test_action", trace_id="123", data={})
    
    captured = capsys.readouterr()
    empty_str = ""
    assert captured.out == empty_str


def test_logging_behavior_debug_true(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str]
) -> None:
    """Test that setting DEBUG=true produces valid JSON logs on stdout."""
    monkeypatch.setattr("app.config.settings.DEBUG", True)
    
    logger = get_logger("test_json")
    action_name = "test_action"
    logger.info(action_name, trace_id="123", data={})
    
    captured = capsys.readouterr()
    
    # Parse the captured stdout JSON log string
    log_entry = json.loads(captured.out)
    
    action_key = "action"
    assert log_entry[action_key] == action_name
