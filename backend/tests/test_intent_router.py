"""
===============================================================================
MODULE: test_intent_router.py
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
LAYER: Backend Test Suite Layer (Intent Router Unit Tests)
===============================================================================

DESCRIPTION:
    Unit tests for the zero-LLM microsecond intent classification router (`intent_router.py`). 
    Validates classification across POLICY_DOCUMENT, STRUCTURED_DATA, MIXED_QUERY_DETECTED, 
    and OUT_OF_SCOPE categories.

KEY RESPONSIBILITIES:
    1. Setting up mock dataset fixtures for dynamic customer name testing.
    2. Parametrized testing of `analyse_intent` across 12 diverse test queries.
    3. Testing Order ID regex word boundaries (`ORD-\\d+`).
    4. Testing `build_system_prompt` injection formatting.
===============================================================================
"""

import os
import sys

# Ensure parent directory is on sys.path for direct module import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import csv
import sqlite3
from typing import Any

import pytest

from app.routing.intent_router import (
    IntentAnalysis,
    analyse_intent,
    build_system_prompt,
)


@pytest.fixture(autouse=True)
def setup_mock_data(tmp_path: Any, monkeypatch: Any) -> Any:
    """
    Autouse fixture creating temporary mock orders.db and orders.csv datasets for customer lookup testing.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    
    # Step 1: Create mock orders.db table
    db_path = data_dir / "orders.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE orders (Customer_Name TEXT)")
    
    # Insert mock customer records
    mock_customers = [("Test User DB",), ("Sneha Reddy",)]
    cursor.executemany("INSERT INTO orders (Customer_Name) VALUES (?)", mock_customers)
    conn.commit()
    conn.close()

    # Step 2: Create mock orders.csv file
    csv_path = data_dir / "orders.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Customer_Name", "other_col"])
        writer.writerow(["Test User CSV", "123"])
        writer.writerow(["John Doe", "456"])

    # Patch DATA_DIR path in intent_router module to point to temporary directory
    monkeypatch.setattr("app.routing.intent_router.DATA_DIR", str(data_dir))
    
    # Re-initialize customer lookup set with mock data
    import app.routing.intent_router as ir
    ir._initialize_customers()
    yield


@pytest.mark.parametrize("query, expected_label", [
    ("what is the return policy?", "POLICY_DOCUMENT"),
    ("my item is defective", "POLICY_DOCUMENT"),
    ("my webcam is defective", "MIXED_QUERY_DETECTED"),
    ("can I use my PTO next week?", "POLICY_DOCUMENT"),
    ("how many orders are pending?", "STRUCTURED_DATA"),
    ("status of my speaker", "STRUCTURED_DATA"),
    ("Sneha Reddy ordered something", "STRUCTURED_DATA"), 
    ("is order ORD-12345 returned?", "MIXED_QUERY_DETECTED"), 
    ("return status of keyboard", "MIXED_QUERY_DETECTED"), 
    ("what is the weather today?", "OUT_OF_SCOPE"),
    ("who is the president?", "OUT_OF_SCOPE"),
    ("hello there", "OUT_OF_SCOPE"), 
])
def test_analyse_intent_labels(query: str, expected_label: str) -> None:
    """Parametrized test asserting correct intent classification labels across queries."""
    analysis = analyse_intent(query)
    assert expected_label in analysis.labels
    assert isinstance(analysis.confidence, float)
    assert analysis.hint_text != ""


def test_ord_regex_boundaries() -> None:
    """Test Order ID regex word boundary matching (ORD-12345 vs WORD-12345)."""
    # Verify non-matching prefix does not trigger MIXED_QUERY_DETECTED
    assert "MIXED_QUERY_DETECTED" not in analyse_intent("WORD-12345 is my id").labels
    # Verify valid ORD-12345 triggers MIXED_QUERY_DETECTED
    assert "MIXED_QUERY_DETECTED" in analyse_intent("where is ORD-12345").labels


def test_build_system_prompt() -> None:
    """Test system prompt injection formatting."""
    base = "You are an AI."
    intent = IntentAnalysis(
        labels=["POLICY_DOCUMENT"], 
        hint_text="Use RAG.", 
        confidence=0.9
    )
    prompt = build_system_prompt(base, intent)
    
    # Verify prompt contains base prompt, signals, and hint text
    assert "You are an AI." in prompt
    assert "--- INTENT ANALYSIS ---" in prompt
    assert "Detected signals: POLICY_DOCUMENT" in prompt
    assert "Use RAG." in prompt
    assert "--- END INTENT ANALYSIS ---" in prompt
