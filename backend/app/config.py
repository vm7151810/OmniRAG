"""
===============================================================================
MODULE: config.py
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
LAYER: Backend Infrastructure Layer (Pydantic Settings & Environment Injector)
===============================================================================

DESCRIPTION:
    This module defines the central application settings schema (`Settings`) 
    using Pydantic BaseSettings. It loads environment variables from `.env` files 
    and injects them natively into `os.environ` for third-party SDK compatibility 
    (LangChain, Pinecone, Google Generative AI).

KEY RESPONSIBILITIES:
    1. Parsing `.env` files with UTF-8 encoding.
    2. Validating API keys for Google Gemini, Pinecone, and LangChain.
    3. Exporting `settings` instance for type-safe application access.
    4. Injecting variables into `os.environ` for SDK auto-discovery.
===============================================================================
"""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Pydantic settings model for application configuration.

    ATTRIBUTES:
        GOOGLE_API_KEY (str): API key for Google Gemini model inference and embeddings.
        PINECONE_API_KEY (str): API key for Pinecone vector database.
        PINECONE_INDEX_NAME (str): Name of the Pinecone serverless index.
        LANGCHAIN_API_KEY (str): API key for optional LangSmith observability tracing.
        LANGCHAIN_TRACING_V2 (bool): Boolean flag enabling LangChain V2 tracing.
        DEBUG (bool): Boolean flag enabling verbose debug telemetry logging.
    """
    GOOGLE_API_KEY: str = ""
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX_NAME: str = ""
    LANGCHAIN_API_KEY: str = ""
    LANGSMITH_API_KEY: str = ""
    LANGCHAIN_TRACING_V2: bool = True
    LANGSMITH_TRACING: bool = True
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGSMITH_PROJECT: str = "omnirag"
    LANGCHAIN_PROJECT: str = "omnirag"
    LANGSMITH_AGENT_ID: str = "omnirag"
    LANGSMITH_AGENT_ENVIRONMENT: str = "local"
    DEBUG: bool = True

    # Pydantic configuration dictionary specifying .env file path and extra field handling
    model_config = SettingsConfigDict(
        env_file="../.env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

# Instantiate global settings object
settings = Settings()

# Step 1: Inject credentials into os.environ for native SDK auto-discovery
os.environ["GOOGLE_API_KEY"] = settings.GOOGLE_API_KEY
os.environ["PINECONE_API_KEY"] = settings.PINECONE_API_KEY
os.environ["PINECONE_INDEX_NAME"] = settings.PINECONE_INDEX_NAME
os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY or settings.LANGSMITH_API_KEY
os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY or settings.LANGCHAIN_API_KEY

# Step 2: Inject LangChain/LangSmith tracing environment variables
effective_key = settings.LANGCHAIN_API_KEY or settings.LANGSMITH_API_KEY
if (settings.LANGCHAIN_TRACING_V2 or settings.LANGSMITH_TRACING) and effective_key:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT
    os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
    os.environ["LANGSMITH_AGENT_ID"] = settings.LANGSMITH_AGENT_ID
    os.environ["LANGSMITH_AGENT_ENVIRONMENT"] = settings.LANGSMITH_AGENT_ENVIRONMENT
else:
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGSMITH_TRACING"] = "false"

# Step 3: Inject DEBUG environment variable if enabled
if settings.DEBUG:
    os.environ["DEBUG"] = "true"
