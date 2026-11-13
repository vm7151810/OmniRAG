"""
===============================================================================
MODULE: test_main.py
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
LAYER: Backend Test Suite Layer (Main Health Check Test)
===============================================================================

DESCRIPTION:
    Basic health check test for FastAPI application (`main.py`).

KEY RESPONSIBILITIES:
    1. Executing `GET /health` request via TestClient.
    2. Asserting status 200 OK and presence of `pinecone_connected` key.
===============================================================================
"""

from fastapi.testclient import TestClient

from app.main import app

# Instantiate TestClient wrapper
client = TestClient(app)


def test_health_check() -> None:
    """Test basic GET /health endpoint response code and status keys."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "pinecone_connected" in data
