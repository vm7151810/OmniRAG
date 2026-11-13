"""
===============================================================================
MODULE: test_sql_tool.py
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
LAYER: Backend Test Suite Layer (SQL Tool Unit & Security Tests)
===============================================================================

DESCRIPTION:
    Unit and security tests for `sql_tool.py`. Validates real SQLite database connectivity, 
    Text-to-SQL translation, Dual DML Security Guard interception (`DROP`, `DELETE`, `UPDATE`, 
    `INSERT`, `ALTER`, `TRUNCATE`), and LangChain Tool export mechanics.

KEY RESPONSIBILITIES:
    1. Verifying existence of real `orders.csv` and `orders.db` dataset files.
    2. Testing valid SQL SELECT query generation and execution.
    3. Testing Dual DML Security Guard blocking malicious input questions (e.g. 'DELETE all orders').
    4. Testing `sql_query_tool` LangChain Tool export and `invoke()` behavior.
===============================================================================
"""

import json
import os
from pathlib import Path

import pytest

from app.tools.sql_tool import run_sql_query, sql_query_tool


@pytest.fixture(scope="session")
def real_db_setup() -> Path:
    """
    Session-scoped fixture verifying real database and CSV dataset files exist on disk.
    """
    data_dir = Path(__file__).resolve().parent.parent / "data"
    csv_path = data_dir / "orders.csv"
    db_path = data_dir / "orders.db"
    
    # Fail test session if real dataset CSV is missing
    if not csv_path.exists():
        pytest.fail(
            f"Real data file not found at {csv_path}. "
            "Cannot run tests without real data."
        )
        
    # Fail test session if real SQLite database is missing
    if not db_path.exists():
        pytest.fail(
            f"Real database not found at {db_path}. "
            "Please initialize the database first."
        )
        
    return db_path


def test_run_sql_query_valid(real_db_setup: Path) -> None:
    """Test generating and executing a valid SQL SELECT query against real SQLite database."""
    question = "How many orders are there in total?"
    print(f"\n[test_run_sql_query_valid] Question: {question}")
    
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.fail("GOOGLE_API_KEY is not set. Cannot run LLM test.")

    # Execute SQL tool engine
    raw_result = run_sql_query(question)
    result = json.loads(raw_result)
    
    print(f"[test_run_sql_query_valid] Generated SQL: {result.get('sql')}")
    print(f"[test_run_sql_query_valid] Result: {str(result.get('result'))[:100]}...")
    
    # Assert JSON payload structure
    assert isinstance(result, dict)
    assert "result" in result
    assert "sql" in result
    assert "error" in result
    assert result["error"] is None
    
    # Assert non-empty row results and SELECT query generation
    assert len(str(result["result"])) > 0
    assert "SELECT" in result["sql"].upper()


def test_run_sql_query_dml_blocked(real_db_setup: Path) -> None:
    """Test that DML keywords (DELETE) are intercepted and blocked by the Dual DML Guard."""
    question = "DELETE all orders from the database."
    print(f"\n[test_run_sql_query_dml_blocked] Question: {question}")
    
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.fail("GOOGLE_API_KEY is not set. Cannot run LLM test.")
        
    # Execute SQL tool engine with malicious DML query
    raw_result = run_sql_query(question)
    result = json.loads(raw_result)
    
    print(f"[test_run_sql_query_dml_blocked] Generated SQL: {result.get('sql')}")
    print(f"[test_run_sql_query_dml_blocked] Error: {result.get('error')}")
    
    # Assert error field is populated and specifies security block message
    assert result["error"] is not None
    assert "Only SELECT queries are permitted" in result["error"]


def test_sql_query_tool_export(real_db_setup: Path) -> None:
    """Test LangChain tool export metadata and invoke() interface."""
    assert sql_query_tool.name == "sql_query"
    assert "Query the Northwind Gadgets orders database" in sql_query_tool.description
    
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.fail("GOOGLE_API_KEY is not set. Cannot run LLM test.")
        
    question = "Show me 1 order id"
    print(f"\n[test_sql_query_tool_export] Question: {question}")
    
    # Execute tool via invoke() interface
    raw_result = sql_query_tool.invoke({"question": question})
    result = json.loads(raw_result)
    print(f"[test_sql_query_tool_export] Generated SQL: {result.get('sql')}")
    print(f"[test_sql_query_tool_export] Result: {str(result.get('result'))[:100]}...")
    
    # Assert successful query execution
    assert "error" in result
    assert result["error"] is None
    assert len(str(result["result"])) > 0
