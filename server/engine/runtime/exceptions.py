"""
exceptions.py — Custom exceptions for the Runtime Trace Engine.
"""

from __future__ import annotations


class RuntimeError_(Exception):
    """Base exception for all runtime-engine errors (name avoids shadowing builtins)."""


class ExecutionError(RuntimeError_):
    """Raised when the executed code produces an unhandled exception."""

    def __init__(
        self,
        message: str,
        *,
        original: BaseException | None = None,
    ) -> None:
        self.original = original
        super().__init__(message)


class ExecutionTimeoutError(RuntimeError_):
    """Raised when execution exceeds the allowed time limit."""

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        super().__init__(f"Execution timed out after {seconds:.1f}s.")


class TracerError(RuntimeError_):
    """Raised when the tracer itself encounters an internal error."""
