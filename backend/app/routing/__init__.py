"""
===============================================================================
PACKAGE: app.routing
PROJECT: OmniRAG Enterprise Agentic Support Chatbot
===============================================================================

DESCRIPTION:
    Package initializer for backend intent routing and prompt injection components.

EXPORTS:
    - analyse_intent: Intent classification function.
    - build_system_prompt: System prompt injection generator.
    - IntentAnalysis: Dataclass for intent classification outputs.
===============================================================================
"""

from app.routing.intent_router import (
    IntentAnalysis,
    analyse_intent,
    build_system_prompt,
)

__all__ = ["analyse_intent", "build_system_prompt", "IntentAnalysis"]
