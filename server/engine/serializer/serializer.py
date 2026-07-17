"""
serializer.py — Deterministic JSON-safe serializer for Code Vision.

Converts ``TraceResult`` objects from the Runtime Trace Engine into
plain Python dictionaries that are directly JSON-serializable.

The serializer:
    • Never executes code.
    • Knows nothing about FastAPI or the frontend.
    • Handles circular references gracefully.
    • Limits recursion depth to prevent stack overflows.
    • Falls back to ``repr()`` for unsupported types.

Pipeline::

    TraceResult → TraceSerializer → dict[str, Any]
"""

from __future__ import annotations

from typing import Any

from engine.runtime.models import EventType, TraceEvent, TraceFrame, TraceResult

from engine.serializer.exceptions import (
    CircularReferenceError,
    InvalidTraceError,
    SerializerError,
)
from engine.serializer.models import INTERNAL_NAMES, SerializerConfig


# =============================================================================
# Value Converter  (handles recursion + circular refs)
# =============================================================================


class _ValueConverter:
    """
    Recursively converts arbitrary Python values into JSON-safe
    equivalents with depth limiting and circular-reference detection.

    This is an internal helper — callers should use ``TraceSerializer``.
    """

    def __init__(self, config: SerializerConfig) -> None:
        self._max_depth = config.max_depth
        self._max_repr = config.max_repr_len

    def convert(self, value: Any, *, _depth: int = 0, _seen: set[int] | None = None) -> Any:
        """
        Convert *value* to a JSON-safe Python object.

        Args:
            value:   The value to convert.
            _depth:  Current recursion depth (internal).
            _seen:   Set of ``id()`` values already visited (internal).

        Returns:
            A JSON-safe value (str, int, float, bool, None, list, or dict).
        """
        if _seen is None:
            _seen = set()

        # Depth guard.
        if _depth > self._max_depth:
            return self._safe_repr(value)

        # Primitives — already JSON-safe.
        if value is None or isinstance(value, (bool, int, float)):
            return value

        if isinstance(value, str):
            return value

        # Circular-reference guard for containers.
        obj_id = id(value)
        if obj_id in _seen:
            return "<circular reference>"
        _seen.add(obj_id)

        try:
            if isinstance(value, dict):
                return {
                    self._key_to_str(k): self.convert(v, _depth=_depth + 1, _seen=_seen)
                    for k, v in value.items()
                }

            if isinstance(value, (list, tuple)):
                converted = [self.convert(item, _depth=_depth + 1, _seen=_seen) for item in value]
                return converted

            if isinstance(value, set):
                return sorted(
                    (self.convert(item, _depth=_depth + 1, _seen=_seen) for item in value),
                    key=lambda x: str(x),
                )

            if isinstance(value, frozenset):
                return sorted(
                    (self.convert(item, _depth=_depth + 1, _seen=_seen) for item in value),
                    key=lambda x: str(x),
                )

            # Fallback: repr.
            return self._safe_repr(value)
        finally:
            _seen.discard(obj_id)

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _key_to_str(key: Any) -> str:
        """JSON keys must be strings."""
        if isinstance(key, str):
            return key
        return repr(key)

    def _safe_repr(self, value: Any) -> str:
        """Bounded repr that never raises."""
        try:
            r = repr(value)
            if len(r) > self._max_repr:
                return r[: self._max_repr - 3] + "..."
            return r
        except Exception:
            return "<repr failed>"


# =============================================================================
# Variable Filter
# =============================================================================


def _filter_variables(
    variables: dict[str, str],
    *,
    filter_internals: bool = True,
) -> dict[str, str]:
    """
    Remove internal / dunder variable names from a snapshot dict.

    The runtime tracer already does some filtering, but the serializer
    applies its own pass to guarantee a clean output regardless of
    tracer changes.
    """
    if not filter_internals:
        return dict(variables)

    return {
        name: value
        for name, value in variables.items()
        if name not in INTERNAL_NAMES
        and not (name.startswith("__") and name.endswith("__"))
    }


# =============================================================================
# TraceSerializer
# =============================================================================


class TraceSerializer:
    """
    Converts ``TraceResult`` → JSON-safe ``dict``.

    Usage::

        serializer = TraceSerializer()
        data = serializer.serialize(trace_result)

    Or with custom config::

        config = SerializerConfig(max_depth=3, include_globals=False)
        data = TraceSerializer(config).serialize(trace_result)
    """

    def __init__(self, config: SerializerConfig | None = None) -> None:
        self._config = config or SerializerConfig()
        self._converter = _ValueConverter(self._config)

    # ── Public API ─────────────────────────────────────────────────────

    def serialize(self, trace_result: TraceResult) -> dict[str, Any]:
        """
        Serialize a complete ``TraceResult`` into a JSON-safe dict.

        Args:
            trace_result: The immutable result from the executor.

        Returns:
            A dict with keys: ``events``, ``frames``, ``output``,
            ``error``, ``total_events``, ``max_depth``, ``success``.

        Raises:
            InvalidTraceError: If *trace_result* is ``None``.
        """
        if trace_result is None:
            raise InvalidTraceError()

        return {
            "events": [self.serialize_event(e) for e in trace_result.events],
            "frames": [self.serialize_frame(f) for f in trace_result.frames],
            "output": trace_result.output,
            "error": trace_result.error,
            "total_events": trace_result.total_events,
            "max_depth": trace_result.max_depth,
            "success": trace_result.success,
        }

    def serialize_event(self, event: TraceEvent) -> dict[str, Any]:
        """
        Serialize a single ``TraceEvent`` into a JSON-safe dict.

        Args:
            event: A frozen ``TraceEvent`` instance.

        Returns:
            Dict with keys: ``sequence``, ``event``, ``line``,
            ``function``, ``call_depth``, ``locals``, etc.

        Raises:
            InvalidTraceError: If *event* is ``None``.
        """
        if event is None:
            raise InvalidTraceError("TraceEvent must not be None.")

        result: dict[str, Any] = {
            "sequence": event.sequence,
            "event": event.event_type.value,
            "line": event.lineno,
            "function": event.function_name,
            "filename": event.filename,
            "call_depth": event.call_depth,
            "locals": _filter_variables(
                event.locals_snap,
                filter_internals=self._config.filter_internals,
            ),
        }

        # Optional fields.
        if self._config.include_globals:
            result["globals"] = _filter_variables(
                event.globals_snap,
                filter_internals=self._config.filter_internals,
            )

        if self._config.include_timestamps:
            result["timestamp_ns"] = event.timestamp_ns

        if event.return_value is not None:
            result["return_value"] = event.return_value

        if event.exception_info is not None:
            result["exception_info"] = event.exception_info

        return result

    def serialize_frame(self, frame: TraceFrame) -> dict[str, Any]:
        """
        Serialize a ``TraceFrame`` into a JSON-safe dict.

        Args:
            frame: A frozen ``TraceFrame`` instance.

        Returns:
            Dict with keys: ``function_name``, ``call_depth``, ``events``.

        Raises:
            InvalidTraceError: If *frame* is ``None``.
        """
        if frame is None:
            raise InvalidTraceError("TraceFrame must not be None.")

        return {
            "function_name": frame.function_name,
            "call_depth": frame.call_depth,
            "events": [self.serialize_event(e) for e in frame.events],
        }

    def serialize_value(self, value: Any) -> Any:
        """
        Convert an arbitrary Python value to a JSON-safe equivalent.

        This is the public gateway to the value converter and is
        useful for serializing individual variables.

        Args:
            value: Any Python object.

        Returns:
            A JSON-safe value.
        """
        return self._converter.convert(value)
