"""
===============================================================================
MODULE: test_data_ingestion.py
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
LAYER: Backend Test Suite Layer (Data Ingestion & DB Loading Tests)
===============================================================================

DESCRIPTION:
    Integration tests for PDF parent-child text splitting, SQLite orders.db 
    idempotent initialization, and Pinecone serverless index connectivity.

KEY RESPONSIBILITIES:
    1. Verifying SQLite `init_db` idempotency (running twice does not duplicate rows).
    2. Asserting 200 operational rows and verifying sample record ('ORD-1001' -> 'Sneha Reddy').
    3. Testing `process_pdf` chunking logic on real policy PDF documents (`hr_leave_policy.pdf`).
    4. Testing Pinecone index existence and connectivity.
===============================================================================
"""

import os
import sqlite3
from collections.abc import Generator
from pathlib import Path

import pandas as pd  # type: ignore
import pytest

# Resolve absolute paths to data directory, orders.db, and orders.csv
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "orders.db"
CSV_PATH = DATA_DIR / "orders.csv"


@pytest.fixture(scope="session", autouse=True)
def setup_dummy_data() -> Generator[None, None, None]:
    """
    Session-scoped fixture ensuring dataset directory and orders.csv exist.
    """
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate fallback dummy CSV if orders.csv is missing
    if not CSV_PATH.exists():
        data = {
            "order_id": [f"ORD-{i:03d}" for i in range(1, 201)],
            "customer": [f"Customer {i}" for i in range(1, 201)],
            "product": ["Widget", "Gadget", "Doohickey", "Thingamajig"] * 50,
            "amount": [10 * i for i in range(1, 201)],
            "status": ["Shipped", "Pending", "Delivered", "Cancelled"] * 50,
            "order_date": pd.date_range(start="2026-01-01", periods=200)
            .strftime("%Y-%m-%d")
            .tolist()
        }
        df = pd.DataFrame(data)
        df.to_csv(CSV_PATH, index=False)
        
    yield


def test_init_db() -> None:
    """Test idempotent database initialization from orders.csv into SQLite orders.db."""
    from app.tools.sql_tool import init_db
    
    # Run init_db twice to test idempotency semantics (if_exists="replace")
    init_db(str(DB_PATH), str(CSV_PATH))
    init_db(str(DB_PATH), str(CSV_PATH))
    
    # Connect to SQLite database and verify contents
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Verify row count is exactly 200
    cursor.execute("SELECT COUNT(*) FROM orders")
    count = cursor.fetchone()[0]
    assert count == 200
    
    # Verify sample record ORD-1001 for customer Sneha Reddy
    cursor.execute("SELECT customer, amount FROM orders WHERE order_id='ORD-1001'")
    record = cursor.fetchone()
    assert record[0] == "Sneha Reddy"
    assert record[1] == 4999
    
    conn.close()


def test_hybrid_chunking() -> None:
    """Test Parent-Child hierarchical PDF chunking logic on hr_leave_policy.pdf."""
    from app.retrieval.ingest import process_pdf
    
    # Resolve file path to real policy PDF
    pdf_path = DATA_DIR / "hr_leave_policy.pdf"
    
    # Process PDF into Document objects
    chunks = process_pdf(str(pdf_path))
    
    # Verify child chunks were extracted
    assert len(chunks) > 0
    # Verify metadata keys required by spec are attached to all chunks
    for chunk in chunks:
        assert "source" in chunk.metadata
        assert "section_title" in chunk.metadata
        assert "page_number" in chunk.metadata
        assert "parent_id" in chunk.metadata
        assert "parent_text" in chunk.metadata


def test_pinecone_connection() -> None:
    """Test Pinecone serverless index connectivity and index existence."""
    from dotenv import load_dotenv
    from pinecone import Pinecone
    
    load_dotenv()
    
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key or "mock" in api_key.lower():
        pytest.skip("Valid PINECONE_API_KEY is not configured. Skipping live Pinecone test.")

    index_name = os.getenv("PINECONE_INDEX_NAME") or "northwind-gadgets"
    index_name = index_name.lower().strip()
    
    pc = Pinecone(api_key=api_key)
    
    # Assert Pinecone index exists on the serverless cluster
    assert pc.has_index(index_name)
