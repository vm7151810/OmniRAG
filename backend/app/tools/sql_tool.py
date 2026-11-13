"""
===============================================================================
MODULE: sql_tool.py
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
LAYER: Backend Tools Layer (SQL Tool & Security Guards)
===============================================================================

DESCRIPTION:
    This module provides the LangChain tool wrapper (`sql_query_tool`), database 
    initialization engine (`init_db`), and Text-to-SQL execution engine (`run_sql_query`) 
    for querying structured order analytics from SQLite `orders.db`.

KEY RESPONSIBILITIES:
    1. Idempotently initializing SQLite `orders.db` from `orders.csv` at startup.
    2. Enforcing a Pre-LLM Dual DML Security Guard to intercept data modification keywords 
       in raw user questions (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`).
    3. Translating natural language questions into valid SQL `SELECT` queries using Gemini 3.5 Flash 
       with schema prompt injection and fixed reference date anchor `2026-06-15`.
    4. Enforcing a Post-LLM Dual DML Security Guard on generated SQL strings.
    5. Executing read-only queries against SQLite and returning stringified JSON payloads.

SECURITY & RESILIENCE:
    - Dual DML Guard prevents SQL injection attacks and accidental database mutations.
    - Explicit database connections with closing guarantees in try-finally semantics.
===============================================================================
"""

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore
from langchain_core.tools import Tool
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings

# Constant system prompt injection string defining exact SQLite schema and date anchor
SCHEMA_PROMPT_INJECTION = (
    "Table: orders(order_id TEXT, customer TEXT, product TEXT, "
    "amount INTEGER, status TEXT, order_date DATE). Current date: 2026-06-15."
)


def init_db(db_path: str, csv_path: str) -> None:
    """
    Idempotently initializes the SQLite database table from a source CSV dataset file.

    ARGUMENTS:
        db_path (str): Absolute file path where SQLite orders.db file should be created/updated.
        csv_path (str): Absolute file path to the source orders.csv dataset file.

    RETURNS:
        None: Creates or overwrites the SQLite table 'orders' on disk.
    """
    # Check if the source CSV dataset file exists on the filesystem
    if not Path(csv_path).exists():
        # Print warning to stdout and return early if source file is missing
        print(f"CSV file {csv_path} not found. Skipping DB initialization.")
        return

    # Step 1: Load the source CSV file into a pandas DataFrame object
    df = pd.read_csv(csv_path)

    # Step 2: Establish a connection to SQLite database (creates DB file if missing)
    conn = sqlite3.connect(db_path)
    
    # Step 3: Define explicit SQLite column data type mapping dictionary
    dtype_mapping = {
        "order_id": "TEXT",
        "customer": "TEXT",
        "product": "TEXT",
        "amount": "INTEGER",
        "status": "TEXT",
        "order_date": "DATE"
    }
    
    # Step 4: Write DataFrame records into SQLite table 'orders'
    # if_exists="replace" guarantees idempotency by dropping and recreating table on reload
    df.to_sql("orders", conn, if_exists="replace", index=False, dtype=dtype_mapping)
    
    # Commit changes to disk
    conn.commit()
    
    # Close database connection cleanly
    conn.close()
    
    # Log successful DB initialization count to stdout
    print(f"Database {db_path} successfully initialized with {len(df)} rows.")


def atomic_log(action: str, data: dict[str, Any]) -> None:
    """
    Emits structured JSON log entries to stdout when DEBUG mode is enabled.

    ARGUMENTS:
        action (str): Identifier for the logged event/step.
        data (dict[str, Any]): Arbitrary key-value telemetry data to serialize.

    RETURNS:
        None: Side-effect logger that prints to stdout.
    """
    # Check if the environment variable DEBUG is explicitly set to string "true"
    if os.getenv("DEBUG") == "true":
        # Construct a standardized structured JSON log dictionary
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),  # ISO-8601 UTC timestamp string
            "module": "sql_tool.py",                     # Source file name for tracing
            "action": action,                           # Log action event title
            "trace_id": "N/A",                          # Optional trace ID placeholder
            "data": data                                # Telemetry dictionary payload
        }
        # Print JSON serialized string to standard output stream
        print(json.dumps(log_entry))


def run_sql_query(question: str) -> str:
    """
    Translates a natural language question into SQL, applies dual security guards, and executes read-only query.

    ARGUMENTS:
        question (str): The natural language query string from the user or agent.

    RETURNS:
        str: A JSON-serialized string containing three keys:
             - 'result': String representation of database row dictionaries.
             - 'sql': The generated raw SQL SELECT query string.
             - 'error': Error message string if validation or execution failed, else None.
    """
    # Log initiation of SQL query engine with input user question
    atomic_log("run_sql_query_start", {"question": question})
    
    try:
        # Define blocklist array of forbidden Data Modification Language (DML) keywords
        restricted_keywords = [
            "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"
        ]
        
        # Step 1: Pre-LLM DML Guard - Intercept malicious input question text before LLM invocation
        upper_question = question.upper()
        for kw in restricted_keywords:
            # Check if any restricted keyword exists in uppercase question string
            if kw in upper_question:
                # Raise ValueError immediately to block token usage and halt execution
                raise ValueError("Only SELECT queries are permitted.")
                
        # Step 2: Initialize 4-tier fallback Gemini models for resilient Text-to-SQL generation
        sql_models = [
            ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                api_key=settings.GOOGLE_API_KEY,
                temperature=0.0,
                max_retries=2,
            ),
            ChatGoogleGenerativeAI(
                model="gemini-2.5-flash-lite",
                api_key=settings.GOOGLE_API_KEY,
                temperature=0.0,
                max_retries=2,
            ),
            ChatGoogleGenerativeAI(
                model="gemini-3.5-flash-lite",
                api_key=settings.GOOGLE_API_KEY,
                temperature=0.0,
                max_retries=2,
            ),
            ChatGoogleGenerativeAI(
                model="gemini-3.1-flash-lite",
                api_key=settings.GOOGLE_API_KEY,
                temperature=0.0,
                max_retries=2,
            ),
        ]
        llm = sql_models[0].with_fallbacks(sql_models[1:])
        
        # Step 3: Construct strict SQL translation prompt with schema injection and date anchor
        prompt = (
            f"{SCHEMA_PROMPT_INJECTION}\n"
            "You are a SQL expert. Translate the following user question into a valid "
            "SQL SELECT query.\n"
            "Return ONLY the raw SQL query, with no markdown formatting or "
            "explanation.\n"
            "Only generate SELECT queries. Never use DROP, DELETE, UPDATE, "
            "INSERT, ALTER, or TRUNCATE.\n"
            f"Question: {question}"
        )
        
        # Step 4: Invoke LLM model to generate SQL query string
        response = llm.invoke(prompt)
        content = response.content
        
        # Extract string content from LLM response payload (handles string vs content block list)
        if isinstance(content, list):
            sql_query = "".join(
                [c.get("text", "") if isinstance(c, dict) else str(c) for c in content]
            )
        else:
            sql_query = str(content)
        sql_query = sql_query.strip()
        
        # Step 5: Clean markdown code block wrappers if generated by LLM (```sql ... ```)
        if sql_query.startswith("```sql"):
            sql_query = sql_query[6:]
        if sql_query.startswith("```"):
            sql_query = sql_query[3:]
        if sql_query.endswith("```"):
            sql_query = sql_query[:-3]
        
        # Strip trailing/leading whitespace again after markdown code block removal
        sql_query = sql_query.strip()
        
        # Log successfully generated raw SQL query string
        atomic_log("sql_generated", {"sql": sql_query})
        
        # Step 6: Post-LLM DML Guard - Re-verify generated SQL query string before execution
        upper_sql = sql_query.upper()
        for kw in restricted_keywords:
            # Check if any restricted DML keyword exists in generated uppercase SQL query string
            if kw in upper_sql:
                # Raise ValueError immediately to prevent database mutation
                raise ValueError("Only SELECT queries are permitted.")
                
        # Step 7: Resolve absolute file path to SQLite orders.db file
        data_dir = Path(__file__).resolve().parent.parent.parent / "data"
        db_path = data_dir / "orders.db"
        
        # Step 8: Connect to SQLite database and execute SELECT query
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(sql_query)
        
        # Fetch all matching result rows
        rows = cursor.fetchall()
        
        # Extract column names from cursor description metadata
        columns = (
            [desc[0] for desc in cursor.description] if cursor.description else []
        )
        
        # Close SQLite database connection cleanly
        conn.close()
        
        # Step 9: Format row tuples into list of dictionaries mapping column name to row cell value
        results_list = [dict(zip(columns, row)) for row in rows]
        result_str = str(results_list)
        
        # Log successful SQL execution along with returned row count
        atomic_log("run_sql_query_success", {"rows_returned": len(rows)})
        
        # Return JSON serialized payload containing results string, raw SQL query, and null error
        return json.dumps({
            "result": result_str,
            "sql": sql_query,
            "error": None
        })
        
    # Catch any validation, LLM generation, or SQL execution exceptions
    except Exception as e:
        # Log execution failure details to stdout
        atomic_log("run_sql_query_error", {"error": str(e)})
        # Return JSON serialized error payload safely without crashing the agent
        return json.dumps({
            "result": "",
            "sql": sql_query if 'sql_query' in locals() else "",
            "error": str(e)
        })

# Instantiate LangChain Tool object for database query tool
sql_query_tool = Tool(
    name="sql_query",
    description=(
        "Query the Northwind Gadgets orders database. Use for questions about "
        "specific orders, revenue, counts, order status, customer order history, "
        "or any numerical/statistical question about orders."
    ),
    func=run_sql_query
)

# Standalone execution block for database initialization
if __name__ == "__main__":
    # Resolve path to backend data directory
    data_dir = Path(__file__).resolve().parent.parent.parent / "data"
    # Execute database initialization populating orders.db from orders.csv
    init_db(str(data_dir / "orders.db"), str(data_dir / "orders.csv"))
