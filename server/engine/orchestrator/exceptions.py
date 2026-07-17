"""
exceptions.py — Exceptions for the Engine Orchestrator.
"""

from __future__ import annotations


class EngineError(Exception):
    """
    Raised when any stage of the Code Vision pipeline fails.
    
    The original exception from the failing stage is preserved
    as the ``__cause__`` of this exception (via ``raise ... from e``).
    """

    def __init__(self, message: str, stage: str | None = None) -> None:
        self.stage = stage
        super().__init__(message)
