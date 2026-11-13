"""
===============================================================================
MODULE: logger.py
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
LAYER: Backend Infrastructure Layer (Structured JSON Logger)
===============================================================================

DESCRIPTION:
    This module configures the global `structlog` logging framework for the backend. 
    It formats all log entries into standardized structured JSON payloads with ISO-8601 
    timestamps, module names, trace IDs, and action titles.

KEY RESPONSIBILITIES:
    1. Custom structlog processor `rename_event_to_action` for standard key mapping.
    2. Custom structlog processor `drop_level` for clean JSON log schema.
    3. Stream handler setup outputting to `sys.stdout` when DEBUG mode is active.
    4. Suppressing log output via `logging.NullHandler()` when DEBUG is inactive.
===============================================================================
"""

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog


def rename_event_to_action(
    logger: Any,
    log_method: str,
    event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """
    Structlog processor that maps default 'event' key to 'action' and 'logger' key to 'module'.

    ARGUMENTS:
        logger (Any): Bound structlog logger instance.
        log_method (str): Name of the calling log method (e.g. 'info').
        event_dict (MutableMapping[str, Any]): Mutable dictionary containing log attributes.

    RETURNS:
        MutableMapping[str, Any]: Processed event dictionary with renamed keys.
    """
    # Rename 'event' key to 'action' for standardized telemetry schema
    if "event" in event_dict:
        event_dict["action"] = event_dict.pop("event")
    # Rename 'logger' key to 'module' for standardized telemetry schema
    if "logger" in event_dict:
        event_dict["module"] = event_dict.pop("logger")
    return event_dict


def drop_level(
    logger: Any,
    log_method: str,
    event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """
    Structlog processor that removes the 'level' key to maintain a minimal JSON schema.

    ARGUMENTS:
        logger (Any): Bound structlog logger instance.
        log_method (str): Name of the calling log method.
        event_dict (MutableMapping[str, Any]): Mutable dictionary containing log attributes.

    RETURNS:
        MutableMapping[str, Any]: Processed event dictionary without the 'level' key.
    """
    # Delete 'level' key if present in event dictionary
    if "level" in event_dict:
        del event_dict["level"]
    return event_dict


def get_logger(name: str) -> Any:
    """
    Configures structlog processors and returns a named bound logger instance.

    ARGUMENTS:
        name (str): The module name string (e.g. __name__).

    RETURNS:
        Any: Configured structlog bound logger instance.
    """
    # Import settings lazily to avoid circular import loops
    from app.config import settings
    debug_mode = settings.DEBUG
    
    # Fetch root Python logger instance
    root_logger = logging.getLogger()
    # Clear existing log handlers to prevent duplicate output in test runners
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    # If DEBUG mode is disabled, attach NullHandler to suppress logging overhead
    if not debug_mode:
        root_logger.addHandler(logging.NullHandler())
        root_logger.setLevel(logging.CRITICAL)
    # If DEBUG mode is enabled, attach StreamHandler outputting to stdout
    else:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger.addHandler(stream_handler)
        root_logger.setLevel(logging.INFO)

    # Configure global structlog processor pipeline
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,            # Filter logs based on severity level
            structlog.stdlib.add_logger_name,            # Attach logger name
            structlog.stdlib.add_log_level,              # Attach log level
            structlog.processors.TimeStamper(fmt="iso"), # Attach ISO-8601 UTC timestamp
            rename_event_to_action,                      # Rename event -> action, logger -> module
            drop_level,                                  # Remove level key
            structlog.processors.JSONRenderer()          # Render final log dictionary as JSON string
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Return bound logger instance for the given module name
    return structlog.get_logger(name)
