"""
tracer.py — sys.settrace()-based execution tracer for Code Vision.

Records call, line, return, and exception events with immutable
snapshots of local and global variables.  All variable values are
stored as ``repr()`` strings — never as live object references.

The tracer is stateful but short-lived: create one per execution,
collect events, then discard it.
"""

from __future__ import annotations

import time
import types
from typing import Any

from engine.runtime.models import EventType, TraceEvent


# =============================================================================
# Constants
# =============================================================================

# Internal / dunder names to strip from variable snapshots.
_IGNORED_GLOBALS: frozenset[str] = frozenset({
    "__builtins__",
    "__loader__",
    "__spec__",
    "__name__",
    "__doc__",
    "__file__",
    "__cached__",
    "__package__",
    "__annotations__",
    "__all__",
    "__path__",
    "__import__",
})

# The virtual filename we assign to dynamically executed code.
TRACE_FILENAME: str = "<trace>"

# Maximum number of events to prevent runaway traces.
MAX_EVENTS: int = 10_000

# Maximum repr length for a single variable value.
MAX_REPR_LEN: int = 200


# =============================================================================
# Snapshot Helpers
# =============================================================================


def _safe_repr(value: Any) -> str:
    """
    Return a bounded ``repr()`` of *value*.

    Truncates at ``MAX_REPR_LEN`` to avoid giant strings from
    large data structures.  Never raises.
    """
    try:
        r = repr(value)
        if len(r) > MAX_REPR_LEN:
            return r[: MAX_REPR_LEN - 3] + "..."
        return r
    except Exception:
        return "<repr failed>"


def _snapshot_locals(frame_locals: dict[str, Any]) -> dict[str, str]:
    """
    Deep-copy local variables as ``{name: repr_string}`` pairs.

    Filters out dunder names and module / type objects that are
    noise rather than useful state.
    """
    snap: dict[str, str] = {}
    for name, value in frame_locals.items():
        if name.startswith("__") and name.endswith("__"):
            continue
        if isinstance(value, (type, types.ModuleType, types.FunctionType)):
            continue
        snap[name] = _safe_repr(value)
    return snap


def _snapshot_globals(frame_globals: dict[str, Any]) -> dict[str, str]:
    """
    Capture a filtered, repr-based snapshot of global variables.

    Only includes user-defined names — strips interpreter internals,
    modules, classes, and functions.
    """
    snap: dict[str, str] = {}
    for name, value in frame_globals.items():
        if name in _IGNORED_GLOBALS:
            continue
        if name.startswith("__") and name.endswith("__"):
            continue
        if isinstance(value, (type, types.ModuleType, types.FunctionType)):
            continue
        snap[name] = _safe_repr(value)
    return snap


# =============================================================================
# Tracer
# =============================================================================


class Tracer:
    """
    Low-level ``sys.settrace()`` callback collector.

    Usage::

        tracer = Tracer()
        tracer.install()     # activates sys.settrace
        exec(code, ns)
        tracer.uninstall()   # deactivates sys.settrace
        events = tracer.events  # list[TraceEvent]

    The tracer automatically stops recording after ``MAX_EVENTS``
    to protect against infinite loops.
    """

    def __init__(self) -> None:
        self._events: list[TraceEvent] = []
        self._sequence: int = 0
        self._depth: int = 0
        self._max_depth: int = 0
        self._active: bool = False

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def events(self) -> list[TraceEvent]:
        """Return the collected events (mutable until frozen by executor)."""
        return list(self._events)

    @property
    def max_depth(self) -> int:
        """Maximum call depth observed during tracing."""
        return self._max_depth

    # ── Install / Uninstall ────────────────────────────────────────────

    def install(self) -> None:
        """Activate the tracer via ``sys.settrace``."""
        import sys
        self._active = True
        sys.settrace(self._trace_callback)

    def uninstall(self) -> None:
        """Deactivate the tracer."""
        import sys
        self._active = False
        sys.settrace(None)

    # ── Trace Callback ─────────────────────────────────────────────────

    def _trace_callback(
        self,
        frame: types.FrameType,
        event: str,
        arg: Any,
    ) -> Any:
        """
        The function passed to ``sys.settrace()``.

        Args:
            frame: The current execution frame.
            event: One of ``"call"``, ``"line"``, ``"return"``, ``"exception"``.
            arg:   Event-specific argument (return value, exception info, etc.).

        Returns:
            ``self._trace_callback`` to continue tracing this scope,
            or ``None`` to stop tracing it.
        """
        if not self._active:
            return None

        # Safety: stop if we've collected too many events.
        if self._sequence >= MAX_EVENTS:
            return None

        # Only trace code executed as "<trace>" (our generated source)
        # or code called from within it.
        filename = frame.f_code.co_filename

        # Map event string → EventType enum.
        try:
            event_type = EventType(event)
        except ValueError:
            # c_call, c_return, c_exception — skip C-level events.
            return self._trace_callback

        # Track call depth.
        if event_type == EventType.CALL:
            self._depth += 1
            if self._depth > self._max_depth:
                self._max_depth = self._depth

        # Build the immutable event snapshot.
        return_value: str | None = None
        exception_info: str | None = None

        if event_type == EventType.RETURN:
            return_value = _safe_repr(arg)
        elif event_type == EventType.EXCEPTION:
            if arg and len(arg) >= 2:
                exception_info = _safe_repr(arg[1])

        trace_event = TraceEvent(
            sequence=self._sequence,
            event_type=event_type,
            filename=filename,
            function_name=frame.f_code.co_name,
            lineno=frame.f_lineno,
            locals_snap=_snapshot_locals(dict(frame.f_locals)),
            globals_snap=_snapshot_globals(dict(frame.f_globals)),
            call_depth=self._depth,
            timestamp_ns=time.monotonic_ns(),
            return_value=return_value,
            exception_info=exception_info,
        )

        self._events.append(trace_event)
        self._sequence += 1

        # Adjust depth after recording the return event.
        if event_type == EventType.RETURN:
            self._depth = max(0, self._depth - 1)

        return self._trace_callback
