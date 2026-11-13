"""
===============================================================================
MODULE: conftest.py
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
LAYER: Backend Test Suite Layer (Pytest Configuration & Session Fixtures)
===============================================================================

DESCRIPTION:
    Pytest configuration and global session fixture module. Loads environment variables 
    from `.env` files and suppresses non-critical third-party deprecation warnings 
    during automated test execution.

KEY RESPONSIBILITIES:
    1. Executing `dotenv.load_dotenv(override=True)` for test environment loading.
    2. Suppressing `google.genai.types` internal deprecation warnings.
===============================================================================
"""

import warnings
from collections.abc import Generator

import pytest
from dotenv import load_dotenv

# Override environment variables from root .env file for testing
load_dotenv(override=True)


@pytest.fixture(autouse=True, scope="session")
def suppress_google_genai_deprecation() -> Generator[None, None, None]:
    """
    Session-scoped autouse fixture that suppresses internal Google GenAI deprecation warnings.

    YIELDS:
        None: Wraps test session in warnings filter context.
    """
    # Enter warnings filter context manager
    with warnings.catch_warnings():
        # Ignore UnionGenericAlias deprecation warnings emitted by google.genai.types
        warnings.filterwarnings(
            "ignore",
            category=DeprecationWarning,
            message=".*_UnionGenericAlias.*",
            module="google\\.genai\\.types"
        )
        yield
