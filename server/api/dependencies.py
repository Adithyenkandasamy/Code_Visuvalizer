"""
dependencies.py — FastAPI dependency injection.
"""

from __future__ import annotations

from engine.orchestrator import CodeVisionEngine


def get_engine() -> CodeVisionEngine:
    """
    Dependency provider for the Code Vision Engine.
    
    This instantiates the orchestrator, ensuring it is cleanly injected
    into the route handlers. This isolates the API from direct instantiation.
    """
    return CodeVisionEngine()
