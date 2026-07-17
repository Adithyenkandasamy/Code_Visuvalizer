"""
engine.serializer — JSON-safe serializer for Code Vision.

Public API::

    from engine.serializer import TraceSerializer, SerializerConfig
"""

from engine.serializer.exceptions import (
    CircularReferenceError,
    InvalidTraceError,
    SerializationDepthError,
    SerializerError,
)
from engine.serializer.models import SerializerConfig
from engine.serializer.serializer import TraceSerializer

__all__ = [
    "CircularReferenceError",
    "InvalidTraceError",
    "SerializationDepthError",
    "SerializerConfig",
    "SerializerError",
    "TraceSerializer",
]
