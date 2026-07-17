"""
exceptions.py — Custom exceptions for the Serializer module.
"""

from __future__ import annotations


class SerializerError(Exception):
    """Base exception for all serializer-related errors."""


class InvalidTraceError(SerializerError):
    """Raised when the provided TraceResult is None or structurally invalid."""

    def __init__(self, message: str = "Invalid or None TraceResult provided.") -> None:
        super().__init__(message)


class SerializationDepthError(SerializerError):
    """Raised when recursive serialization exceeds the maximum depth."""

    def __init__(self, max_depth: int) -> None:
        self.max_depth = max_depth
        super().__init__(f"Serialization exceeded maximum depth of {max_depth}.")


class CircularReferenceError(SerializerError):
    """Raised when a circular reference is detected during serialization."""

    def __init__(self) -> None:
        super().__init__("Circular reference detected during serialization.")
