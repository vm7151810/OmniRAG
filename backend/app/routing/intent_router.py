r"""
===============================================================================
MODULE: intent_router.py
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
LAYER: Backend Routing Layer (Microsecond Semantic Pre-Router)
===============================================================================

DESCRIPTION:
    This module provides the in-memory, zero-LLM intent classification engine 
    (`analyse_intent`) and system prompt injector (`build_system_prompt`). It pre-analyzes 
    user queries in <0.5ms using static keyword set matching, regular expression order 
    ID pattern extraction, and dynamic customer name set lookup.

KEY RESPONSIBILITIES:
    1. Defining keyword sets for STRUCTURED_DATA, POLICY_DOCUMENT, and OUT_OF_SCOPE.
    2. Dynamically loading customer full names from SQLite `orders.db` / `orders.csv`.
    3. Detecting Order ID regex patterns (`ord-\d+`).
    4. Categorizing queries into `MIXED_QUERY_DETECTED`, `STRUCTURED_DATA`, `POLICY_DOCUMENT`, 
       or `OUT_OF_SCOPE` with confidence scores.
    5. Injecting non-binding soft hint blocks into the agent system prompt.
===============================================================================
"""

import csv
import os
import re
import sqlite3
from dataclasses import dataclass


@dataclass
class IntentAnalysis:
    """
    Data class representing the result of intent analysis.

    ATTRIBUTES:
        labels (list[str]): List of detected intent label strings (e.g. ['MIXED_QUERY_DETECTED']).
        hint_text (str): Explanatory guidance string injected into the agent prompt.
        confidence (float): Calculated classification confidence score between 0.0 and 1.0.
    """
    labels: list[str]
    hint_text: str
    confidence: float


# Base filesystem directory resolution for backend root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Data directory path containing orders.db and orders.csv
DATA_DIR = os.path.join(BASE_DIR, "data")

# Static keyword set matching structured database queries (SQL domain)
STRUCTURED_DATA_KEYWORDS: set[str] = {
    "order", "revenue", "count", "pending", "status", "how many",
    "total", "customer", "amount", "product", "date",
    "delivered", "shipped", "processing", "cancelled", "returned",
    "bought", "purchased", "spent",
    "keyboard", "headphones", "webcam", "speaker", "ssd", "monitor",
    "cushion", "mouse", "hub",
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    "last month", "this week"
}

# Static keyword set matching policy document queries (RAG domain)
POLICY_DOCUMENT_KEYWORDS: set[str] = {
    "return", "warranty", "leave", "discount", "refund", "policy",
    "faq", "eligible", "claim", "cover",
    "pto", "sick", "vacation", "annual", "hr", "manager",
    "repair", "broken", "defective", "damage", "replacement",
    "promo", "code", "bulk", "sale",
    "shipping", "delivery time", "manual", "setup", "compatibility"
}

# Static keyword set matching completely out-of-scope queries
OUT_OF_SCOPE_KEYWORDS: set[str] = {
    "weather", "cricket", "football", "news", "politics", "recipe",
    "movie", "song", "capital of", "who is", "stock price"
}

# Compiled regular expression pattern matching Order ID strings like 'ORD-1001' or 'ord-1207'
ORD_REGEX = re.compile(r"\bord-\d+\b", re.IGNORECASE)

# Module-level set caching dynamic customer full names loaded from DB/CSV
_dynamic_customers: set[str] = set()


def _initialize_customers() -> None:
    """
    Dynamically extracts unique customer full names from orders.db or orders.csv at startup.

    RETURNS:
        None: Populates module-level _dynamic_customers set.
    """
    global _dynamic_customers
    # Clear existing dynamic customer set
    _dynamic_customers.clear()
    
    # Resolve file paths for SQLite database and CSV dataset
    db_path = os.path.join(DATA_DIR, "orders.db")
    csv_path = os.path.join(DATA_DIR, "orders.csv")
    
    # Step 1: Try reading customer names from SQLite database if file exists
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            # Verify table 'orders' exists in SQLite master schema
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='orders';"
            )
            if cursor.fetchone():
                try:
                    # Select customer column values from orders table
                    cursor.execute("SELECT customer FROM orders")
                    rows = cursor.fetchall()
                    for row in rows:
                        if row[0]:
                            # Store lowercased customer name in set
                            _dynamic_customers.add(str(row[0]).lower())
                except sqlite3.OperationalError:
                    # Fallback check for alternative column name Customer_Name
                    try:
                        cursor.execute("SELECT Customer_Name FROM orders")
                        rows = cursor.fetchall()
                        for row in rows:
                            if row[0]:
                                _dynamic_customers.add(str(row[0]).lower())
                    except sqlite3.OperationalError:
                        pass
            conn.close()
        except Exception:  # noqa: S110
            # Fall back to CSV if database connection fails
            pass
            
    # Step 2: Fall back to reading orders.csv if database failed or yielded no customers
    if not _dynamic_customers and os.path.exists(csv_path):
        try:
            with open(csv_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames:
                    # Locate column header containing 'customer' or 'name'
                    customer_col = next((
                        col for col in reader.fieldnames 
                        if "customer" in col.lower() or "name" in col.lower()
                    ), None)
                    
                    if customer_col:
                        for row in reader:
                            val = row.get(customer_col)
                            if val:
                                _dynamic_customers.add(str(val).lower())
        except Exception:  # noqa: S110
            pass

# Execute dynamic customer initialization at module load time
_initialize_customers()


def analyse_intent(query: str) -> IntentAnalysis:
    """
    Analyzes an input query string and returns intent labels, soft hints, and confidence.

    ARGUMENTS:
        query (str): Input natural language search query string.

    RETURNS:
        IntentAnalysis: Data object containing labels, hint_text, and confidence float.
    """
    # Normalize query string to lowercase for case-insensitive matching
    query_lower = query.lower()
    
    # Step 1: Compute matching keyword tokens across static keyword sets
    data_matches = [kw for kw in STRUCTURED_DATA_KEYWORDS if kw in query_lower]
    policy_matches = [kw for kw in POLICY_DOCUMENT_KEYWORDS if kw in query_lower]
    out_of_scope_matches = [kw for kw in OUT_OF_SCOPE_KEYWORDS if kw in query_lower]
    
    # Step 2: Check if query mentions any dynamically loaded customer name
    customer_match = any(cust in query_lower for cust in _dynamic_customers)
    if customer_match:
        # Append 'customer_name' signal to structured data matches list
        data_matches.append("customer_name")
        
    # Step 3: Check if query contains an Order ID pattern matching 'ORD-\d+'
    has_ord_id = bool(ORD_REGEX.search(query_lower))
    
    labels: list[str] = []
    
    # Step 4: Evaluate Mixed Query condition (query contains both policy and data signals, or contains order ID)
    is_mixed = (len(data_matches) > 0 and len(policy_matches) > 0) or has_ord_id
    
    # Handle inherently ambiguous terms ('returned' and 'shipping') by routing to MIXED
    ambiguous = ["returned", "shipping"]
    if any(kw in query_lower for kw in ambiguous):
        is_mixed = True
        
    # Step 5: Assign Intent Category, Hint Text, and Confidence Score
    if is_mixed:
        labels.append("MIXED_QUERY_DETECTED")
        hint_text = (
            "This query contains elements of both policy and structured data "
            "(or mentions a specific order ID/ambiguous terms). Please synthesize "
            "information from both the RAG tool and the SQL tool if necessary."
        )
        confidence = 0.95
    elif len(data_matches) > 0:
        labels.append("STRUCTURED_DATA")
        hint_text = (
            "This query likely requires looking up structured data such as order "
            "statuses, revenue, or customer info. Consider using the SQL tool."
        )
        confidence = 0.9
    elif len(policy_matches) > 0:
        labels.append("POLICY_DOCUMENT")
        hint_text = (
            "This query appears to ask about company policies, FAQs, or "
            "guidelines. Consider using the RAG tool."
        )
        confidence = 0.9
    elif len(out_of_scope_matches) > 0:
        labels.append("OUT_OF_SCOPE")
        hint_text = (
            "This query is completely out of scope of our business context. "
            "Please decline answering gracefully."
        )
        confidence = 0.99
    else:
        labels.append("OUT_OF_SCOPE")
        hint_text = (
            "This query does not match any known domains. Treat as out of "
            "scope unless context implies otherwise."
        )
        confidence = 0.5

    return IntentAnalysis(labels=labels, hint_text=hint_text, confidence=confidence)


def build_system_prompt(base_prompt: str, intent: IntentAnalysis) -> str:
    """
    Injects pre-analyzed intent signals and soft hints into the base agent system prompt.

    ARGUMENTS:
        base_prompt (str): The raw base system prompt string.
        intent (IntentAnalysis): The intent analysis object containing labels and hint text.

    RETURNS:
        str: Enhanced system prompt string with injected intent analysis block.
    """
    # Join detected intent label strings into comma-separated list
    labels_str = ", ".join(intent.labels)
    # Construct intent analysis injection block
    injection = f"""
--- INTENT ANALYSIS ---
Detected signals: {labels_str}
{intent.hint_text}
--- END INTENT ANALYSIS ---
"""
    # Append injection block to base system prompt string
    return f"{base_prompt}\n{injection.strip()}"
