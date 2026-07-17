"""
models.py — Immutable dataclasses for the Runtime Trace Engine.

Every snapshot is a frozen dataclass that stores *copies* of
runtime state — never live references.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


# =============================================================================
# Enumerations
# =============================================================================


class EventType(Enum):
    """Python trace-event types captured by ``sys.settrace``."""

    CALL = "call"
    LINE = "line"
    RETURN = "return"
    EXCEPTION = "exception"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """
    A single execution event recorded by the tracer.

    Attributes:
        sequence:       Global ordering index (0-based, monotonic).
        event_type:     The kind of trace event.
        filename:       Source file (``"<trace>"`` for generated code).
        function_name:  Name of the active function, or ``"<module>"``.
        lineno:         Source line number (1-indexed).
        locals_snap:    Deep-copied snapshot of local variables.
        globals_snap:   Filtered snapshot of global variables.
        call_depth:     Current call-stack depth (0 = top level).
        timestamp_ns:   Monotonic timestamp in nanoseconds.
        return_value:   String repr of the return value (``return`` events only).
        exception_info: String repr of the exception (``exception`` events only).
    """

    sequence: int
    event_type: EventType
    filename: str
    function_name: str
    lineno: int
    locals_snap: dict[str, str] = field(default_factory=dict)
    globals_snap: dict[str, str] = field(default_factory=dict)
    call_depth: int = 0
    timestamp_ns: int = 0
    return_value: str | None = None
    exception_info: str | None = None


@dataclass(frozen=True, slots=True)
class TraceFrame:
    """
    A higher-level grouping: one complete function invocation.

    Attributes:
        function_name: The function that was called.
        call_depth:    Nesting depth when the call was made.
        events:        All ``TraceEvent`` objects within this call.
    """

    function_name: str
    call_depth: int = 0
    events: tuple[TraceEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class TraceResult:
    """
    Top-level container returned by the executor.

    Attributes:
        events:        All trace events in deterministic order.
        frames:        Events grouped into per-call ``TraceFrame`` objects.
        output:        Captured ``stdout`` output from the execution.
        error:         Error message if execution failed, else ``None``.
        total_events:  Convenience count of events.
        max_depth:     Maximum call depth observed.
        success:       ``True`` if execution completed without error.
    """

    events: tuple[TraceEvent, ...] = ()
    frames: tuple[TraceFrame, ...] = ()
    output: str = ""
    error: str | None = None
    total_events: int = 0
    max_depth: int = 0
    success: bool = True
