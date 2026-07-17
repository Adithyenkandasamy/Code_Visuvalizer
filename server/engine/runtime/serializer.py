"""
serializer.py — TraceResult serializer for Code Vision.

Converts immutable ``TraceResult`` objects into plain Python
dictionaries suitable for JSON serialisation.

This module is intentionally kept separate from the executor
and tracer so that serialisation concerns never leak into the
runtime pipeline.
"""

from __future__ import annotations

from engine.runtime.models import TraceEvent, TraceFrame, TraceResult


class TraceSerializer:
    """
    Converts ``TraceResult`` → ``dict`` for JSON transport.

    Usage::

        data = TraceSerializer.serialize(result)
    """

    @staticmethod
    def serialize_event(event: TraceEvent) -> dict:
        """Serialize a single ``TraceEvent`` to a plain dict."""
        return {
            "sequence": event.sequence,
            "event_type": event.event_type.value,
            "filename": event.filename,
            "function_name": event.function_name,
            "lineno": event.lineno,
            "locals": dict(event.locals_snap),
            "globals": dict(event.globals_snap),
            "call_depth": event.call_depth,
            "timestamp_ns": event.timestamp_ns,
            "return_value": event.return_value,
            "exception_info": event.exception_info,
        }

    @staticmethod
    def serialize_frame(frame: TraceFrame) -> dict:
        """Serialize a ``TraceFrame`` to a plain dict."""
        return {
            "function_name": frame.function_name,
            "call_depth": frame.call_depth,
            "events": [TraceSerializer.serialize_event(e) for e in frame.events],
        }

    @staticmethod
    def serialize(result: TraceResult) -> dict:
        """
        Serialize a complete ``TraceResult`` to a JSON-ready dict.

        Returns:
            A dict with keys: ``events``, ``frames``, ``output``,
            ``error``, ``total_events``, ``max_depth``, ``success``.
        """
        return {
            "events": [TraceSerializer.serialize_event(e) for e in result.events],
            "frames": [TraceSerializer.serialize_frame(f) for f in result.frames],
            "output": result.output,
            "error": result.error,
            "total_events": result.total_events,
            "max_depth": result.max_depth,
            "success": result.success,
        }
