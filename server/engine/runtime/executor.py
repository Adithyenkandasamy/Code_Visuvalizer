"""
executor.py — Safe code executor for Code Vision.

Runs generated Python source in an isolated namespace while
recording every execution step via the ``Tracer``.

The executor ONLY runs source produced by the Wrapper Generator.
It never touches arbitrary external files.

Pipeline::

    GeneratedSource → Executor → Tracer → TraceResult
"""

from __future__ import annotations

import io
import sys
import contextlib

from engine.runtime.exceptions import ExecutionError, TracerError
from engine.runtime.models import EventType, TraceEvent, TraceFrame, TraceResult
from engine.runtime.tracer import TRACE_FILENAME, Tracer


# =============================================================================
# Frame Builder
# =============================================================================


def _build_frames(events: tuple[TraceEvent, ...]) -> tuple[TraceFrame, ...]:
    """
    Group a flat sequence of trace events into per-call ``TraceFrame``
    objects using a stack-based approach.

    Each ``CALL`` event opens a new frame; the matching ``RETURN``
    event closes it.
    """
    frames: list[TraceFrame] = []
    stack: list[list[TraceEvent]] = []  # stack of event-lists

    for ev in events:
        if ev.event_type == EventType.CALL:
            stack.append([ev])
        elif stack:
            stack[-1].append(ev)
            if ev.event_type == EventType.RETURN:
                frame_events = stack.pop()
                frames.append(
                    TraceFrame(
                        function_name=frame_events[0].function_name,
                        call_depth=frame_events[0].call_depth,
                        events=tuple(frame_events),
                    )
                )
        else:
            # Line / exception at module level (no enclosing call).
            # Collect into a synthetic "<module>" frame later.
            pass

    # Flush any unclosed frames (shouldn't happen in normal execution).
    while stack:
        frame_events = stack.pop()
        frames.append(
            TraceFrame(
                function_name=frame_events[0].function_name,
                call_depth=frame_events[0].call_depth,
                events=tuple(frame_events),
            )
        )

    return tuple(frames)


# =============================================================================
# Executor
# =============================================================================


class Executor:
    """
    Safely execute generated Python source and collect a ``TraceResult``.

    Usage::

        executor = Executor(source_code)
        result = executor.run()

    Or via the class-method shortcut::

        result = Executor.execute(source_code)

    The executor:
        1. Compiles the source (catches ``SyntaxError``).
        2. Installs a ``sys.settrace`` tracer.
        3. Runs the compiled code in a clean namespace.
        4. Captures ``stdout`` output.
        5. Returns an immutable ``TraceResult``.
    """

    def __init__(self, source_code: str) -> None:
        if not source_code or not source_code.strip():
            raise ExecutionError("Source code must not be empty.")
        self._source = source_code

    # ── Public API ─────────────────────────────────────────────────────

    def run(self) -> TraceResult:
        """
        Execute the source and return a ``TraceResult``.

        Returns:
            Immutable ``TraceResult`` with all recorded events.

        Raises:
            ExecutionError: If the code cannot be compiled or raises.
        """
        # 1. Compile.
        try:
            code = compile(self._source, TRACE_FILENAME, "exec")
        except SyntaxError as exc:
            raise ExecutionError(
                f"Syntax error in generated source: {exc}",
                original=exc,
            ) from exc

        # 2. Prepare isolated namespace.
        namespace: dict = {"__name__": "__main__"}

        # 3. Set up tracer and stdout capture.
        tracer = Tracer()
        stdout_buf = io.StringIO()
        error_msg: str | None = None
        success = True

        try:
            tracer.install()
            with contextlib.redirect_stdout(stdout_buf):
                exec(code, namespace)  # noqa: S102 — intentional exec of generated code
        except Exception as exc:
            success = False
            error_msg = f"{type(exc).__name__}: {exc}"
        finally:
            tracer.uninstall()

        # 4. Collect events and build frames.
        events = tuple(tracer.events)
        frames = _build_frames(events)

        return TraceResult(
            events=events,
            frames=frames,
            output=stdout_buf.getvalue(),
            error=error_msg,
            total_events=len(events),
            max_depth=tracer.max_depth,
            success=success,
        )

    @classmethod
    def execute(cls, source_code: str) -> TraceResult:
        """Convenience class method: execute in one call."""
        return cls(source_code).run()
