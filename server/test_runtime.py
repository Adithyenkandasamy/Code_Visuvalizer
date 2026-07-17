"""
test_runtime.py — Unit tests for the Runtime Trace Engine.

Run:
    python test_runtime.py
    python -m unittest test_runtime -v
"""

from __future__ import annotations

import textwrap
import unittest

from engine.runtime import (
    EventType,
    ExecutionError,
    Executor,
    RuntimeError_,
    TraceEvent,
    TraceFrame,
    TraceResult,
    TraceSerializer,
)


# =============================================================================
# Helpers
# =============================================================================


def _run(source: str) -> TraceResult:
    """Shortcut: dedent + execute."""
    return Executor.execute(textwrap.dedent(source))


# =============================================================================
# Test: Simple Assignment
# =============================================================================


class TestSimpleAssignment(unittest.TestCase):

    def test_variable_captured(self) -> None:
        result = _run("x = 10\nprint(x)\n")
        self.assertTrue(result.success)
        self.assertIn("10", result.output)
        # At least one event must capture x in locals or globals.
        all_vars = {}
        for ev in result.events:
            all_vars.update(ev.locals_snap)
            all_vars.update(ev.globals_snap)
        self.assertIn("x", all_vars)

    def test_multiple_assignments(self) -> None:
        result = _run("a = 1\nb = 2\nc = a + b\nprint(c)\n")
        self.assertTrue(result.success)
        self.assertIn("3", result.output)

    def test_output_captured(self) -> None:
        result = _run('print("hello world")\n')
        self.assertTrue(result.success)
        self.assertIn("hello world", result.output)


# =============================================================================
# Test: Loops
# =============================================================================


class TestLoops(unittest.TestCase):

    def test_for_loop(self) -> None:
        source = """\
            total = 0
            for i in range(5):
                total += i
            print(total)
        """
        result = _run(source)
        self.assertTrue(result.success)
        self.assertIn("10", result.output)
        # Must have multiple line events (loop iterations).
        line_events = [e for e in result.events if e.event_type == EventType.LINE]
        self.assertGreater(len(line_events), 3)

    def test_while_loop(self) -> None:
        source = """\
            n = 3
            while n > 0:
                n -= 1
            print(n)
        """
        result = _run(source)
        self.assertTrue(result.success)
        self.assertIn("0", result.output)


# =============================================================================
# Test: If Statements
# =============================================================================


class TestIfStatements(unittest.TestCase):

    def test_true_branch(self) -> None:
        source = """\
            x = 10
            if x > 5:
                result = "big"
            else:
                result = "small"
            print(result)
        """
        result = _run(source)
        self.assertTrue(result.success)
        self.assertIn("big", result.output)

    def test_false_branch(self) -> None:
        source = """\
            x = 2
            if x > 5:
                result = "big"
            else:
                result = "small"
            print(result)
        """
        result = _run(source)
        self.assertIn("small", result.output)


# =============================================================================
# Test: Function Calls
# =============================================================================


class TestFunctionCalls(unittest.TestCase):

    def test_function_call_events(self) -> None:
        source = """\
            def add(a, b):
                return a + b
            result = add(3, 4)
            print(result)
        """
        result = _run(source)
        self.assertTrue(result.success)
        self.assertIn("7", result.output)
        # Must have call and return events for 'add'.
        call_events = [
            e for e in result.events
            if e.event_type == EventType.CALL and e.function_name == "add"
        ]
        return_events = [
            e for e in result.events
            if e.event_type == EventType.RETURN and e.function_name == "add"
        ]
        self.assertGreaterEqual(len(call_events), 1)
        self.assertGreaterEqual(len(return_events), 1)

    def test_return_value_captured(self) -> None:
        source = """\
            def double(n):
                return n * 2
            result = double(5)
            print(result)
        """
        result = _run(source)
        return_events = [
            e for e in result.events
            if e.event_type == EventType.RETURN and e.function_name == "double"
        ]
        self.assertTrue(any(e.return_value == "10" for e in return_events))

    def test_nested_function_calls(self) -> None:
        source = """\
            def inner(x):
                return x + 1
            def outer(x):
                return inner(x) + 1
            result = outer(1)
            print(result)
        """
        result = _run(source)
        self.assertTrue(result.success)
        self.assertIn("3", result.output)
        # Call depth should reach at least 2.
        self.assertGreaterEqual(result.max_depth, 2)

    def test_call_depth_tracking(self) -> None:
        source = """\
            def a():
                return b()
            def b():
                return c()
            def c():
                return 42
            print(a())
        """
        result = _run(source)
        self.assertIn("42", result.output)
        self.assertGreaterEqual(result.max_depth, 3)


# =============================================================================
# Test: Recursion
# =============================================================================


class TestRecursion(unittest.TestCase):

    def test_factorial(self) -> None:
        source = """\
            def factorial(n):
                if n <= 1:
                    return 1
                return n * factorial(n - 1)
            print(factorial(5))
        """
        result = _run(source)
        self.assertTrue(result.success)
        self.assertIn("120", result.output)
        # Recursion should produce multiple call events for 'factorial'.
        calls = [
            e for e in result.events
            if e.event_type == EventType.CALL and e.function_name == "factorial"
        ]
        self.assertEqual(len(calls), 5)

    def test_recursion_depth(self) -> None:
        source = """\
            def countdown(n):
                if n == 0:
                    return 0
                return countdown(n - 1)
            countdown(4)
        """
        result = _run(source)
        self.assertTrue(result.success)
        self.assertGreaterEqual(result.max_depth, 4)


# =============================================================================
# Test: Class Methods
# =============================================================================


class TestClassMethods(unittest.TestCase):

    def test_instance_method(self) -> None:
        source = """\
            class Calculator:
                def add(self, a, b):
                    return a + b
            calc = Calculator()
            print(calc.add(2, 3))
        """
        result = _run(source)
        self.assertTrue(result.success)
        self.assertIn("5", result.output)

    def test_class_with_init(self) -> None:
        source = """\
            class Point:
                def __init__(self, x, y):
                    self.x = x
                    self.y = y
                def magnitude(self):
                    return (self.x ** 2 + self.y ** 2) ** 0.5
            p = Point(3, 4)
            print(p.magnitude())
        """
        result = _run(source)
        self.assertTrue(result.success)
        self.assertIn("5.0", result.output)


# =============================================================================
# Test: Static Methods
# =============================================================================


class TestStaticMethods(unittest.TestCase):

    def test_static_method_call(self) -> None:
        source = """\
            class MathUtils:
                @staticmethod
                def multiply(a, b):
                    return a * b
            print(MathUtils.multiply(6, 7))
        """
        result = _run(source)
        self.assertTrue(result.success)
        self.assertIn("42", result.output)


# =============================================================================
# Test: Exception Handling
# =============================================================================


class TestExceptions(unittest.TestCase):

    def test_handled_exception(self) -> None:
        source = """\
            try:
                x = 1 / 0
            except ZeroDivisionError:
                x = -1
            print(x)
        """
        result = _run(source)
        self.assertTrue(result.success)
        self.assertIn("-1", result.output)
        # Must have at least one exception event.
        exc_events = [e for e in result.events if e.event_type == EventType.EXCEPTION]
        self.assertGreater(len(exc_events), 0)

    def test_unhandled_exception_captured(self) -> None:
        source = "x = 1 / 0\n"
        result = _run(source)
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertIn("ZeroDivisionError", result.error)

    def test_empty_source_raises(self) -> None:
        with self.assertRaises(ExecutionError):
            Executor.execute("")


# =============================================================================
# Test: Async Functions
# =============================================================================


class TestAsyncFunctions(unittest.TestCase):

    def test_async_function_via_asyncio_run(self) -> None:
        source = """\
            import asyncio
            async def greet(name):
                return f"Hello, {name}"
            result = asyncio.run(greet("World"))
            print(result)
        """
        result = _run(source)
        self.assertTrue(result.success)
        self.assertIn("Hello, World", result.output)


# =============================================================================
# Test: Deterministic Ordering
# =============================================================================


class TestOrdering(unittest.TestCase):

    def test_sequence_is_monotonic(self) -> None:
        source = """\
            a = 1
            b = 2
            c = a + b
            print(c)
        """
        result = _run(source)
        sequences = [e.sequence for e in result.events]
        self.assertEqual(sequences, sorted(sequences))

    def test_timestamps_are_monotonic(self) -> None:
        source = "x = 1\ny = 2\n"
        result = _run(source)
        timestamps = [e.timestamp_ns for e in result.events]
        for i in range(1, len(timestamps)):
            self.assertGreaterEqual(timestamps[i], timestamps[i - 1])


# =============================================================================
# Test: Variable Snapshots
# =============================================================================


class TestVariableSnapshots(unittest.TestCase):

    def test_locals_captured_in_function(self) -> None:
        source = """\
            def compute(x):
                y = x * 2
                return y
            compute(5)
        """
        result = _run(source)
        # Find a line event inside 'compute' that has 'y' in locals.
        found = False
        for ev in result.events:
            if ev.function_name == "compute" and "y" in ev.locals_snap:
                self.assertEqual(ev.locals_snap["y"], "10")
                found = True
                break
        self.assertTrue(found, "Expected 'y' in locals of 'compute'")

    def test_globals_filtered(self) -> None:
        """Internal variables like __builtins__ must be excluded."""
        source = "x = 42\n"
        result = _run(source)
        for ev in result.events:
            self.assertNotIn("__builtins__", ev.globals_snap)
            self.assertNotIn("__spec__", ev.globals_snap)
            self.assertNotIn("__loader__", ev.globals_snap)

    def test_snapshots_are_strings(self) -> None:
        """All variable values must be repr strings, not live objects."""
        source = "data = [1, 2, 3]\n"
        result = _run(source)
        for ev in result.events:
            for val in ev.locals_snap.values():
                self.assertIsInstance(val, str)
            for val in ev.globals_snap.values():
                self.assertIsInstance(val, str)


# =============================================================================
# Test: TraceResult Properties
# =============================================================================


class TestTraceResult(unittest.TestCase):

    def test_total_events_matches(self) -> None:
        result = _run("x = 1\ny = 2\n")
        self.assertEqual(result.total_events, len(result.events))

    def test_success_flag(self) -> None:
        result = _run("x = 1\n")
        self.assertTrue(result.success)

    def test_error_on_failure(self) -> None:
        result = _run("raise ValueError('boom')\n")
        self.assertFalse(result.success)
        self.assertIn("ValueError", result.error)


# =============================================================================
# Test: Frames
# =============================================================================


class TestFrames(unittest.TestCase):

    def test_frames_created_for_function(self) -> None:
        source = """\
            def greet():
                return "hi"
            greet()
        """
        result = _run(source)
        greet_frames = [f for f in result.frames if f.function_name == "greet"]
        self.assertGreaterEqual(len(greet_frames), 1)
        # Each frame must contain a CALL and RETURN.
        frame = greet_frames[0]
        event_types = {e.event_type for e in frame.events}
        self.assertIn(EventType.CALL, event_types)
        self.assertIn(EventType.RETURN, event_types)


# =============================================================================
# Test: Frozen Dataclasses
# =============================================================================


class TestFrozenDataclasses(unittest.TestCase):

    def test_trace_result_is_frozen(self) -> None:
        result = _run("x = 1\n")
        with self.assertRaises(AttributeError):
            result.success = False  # type: ignore[misc]

    def test_trace_event_is_frozen(self) -> None:
        result = _run("x = 1\n")
        with self.assertRaises(AttributeError):
            result.events[0].lineno = 999  # type: ignore[misc]

    def test_trace_frame_is_frozen(self) -> None:
        source = "def f(): return 1\nf()\n"
        result = _run(source)
        if result.frames:
            with self.assertRaises(AttributeError):
                result.frames[0].function_name = "hacked"  # type: ignore[misc]


# =============================================================================
# Test: Serializer
# =============================================================================


class TestSerializer(unittest.TestCase):

    def test_serialize_returns_dict(self) -> None:
        result = _run("x = 1\nprint(x)\n")
        data = TraceSerializer.serialize(result)
        self.assertIsInstance(data, dict)
        self.assertIn("events", data)
        self.assertIn("frames", data)
        self.assertIn("output", data)
        self.assertIn("success", data)

    def test_serialize_event_keys(self) -> None:
        result = _run("x = 1\n")
        data = TraceSerializer.serialize(result)
        if data["events"]:
            event = data["events"][0]
            self.assertIn("sequence", event)
            self.assertIn("event_type", event)
            self.assertIn("lineno", event)
            self.assertIn("locals", event)
            self.assertIn("call_depth", event)

    def test_serialize_preserves_output(self) -> None:
        result = _run('print("hello")\n')
        data = TraceSerializer.serialize(result)
        self.assertIn("hello", data["output"])


# =============================================================================
# Test: Exceptions Hierarchy
# =============================================================================


class TestExceptionHierarchy(unittest.TestCase):

    def test_execution_error_inherits(self) -> None:
        self.assertTrue(issubclass(ExecutionError, RuntimeError_))

    def test_execution_error_preserves_original(self) -> None:
        try:
            Executor.execute("def")  # invalid syntax
        except ExecutionError as exc:
            self.assertIsNotNone(exc.original)


# =============================================================================
# Test: Full Pipeline Integration
# =============================================================================


class TestFullPipeline(unittest.TestCase):
    """End-to-end: Analyzer → Planner → Wrapper → Executor."""

    def test_solution_twosum_pipeline(self) -> None:
        from analyzer import CodeAnalyzer
        from engine.planner import ExecutionPlanner
        from engine.wrapper import WrapperGenerator

        source = textwrap.dedent("""\
            class Solution:
                def twoSum(self, nums: list[int], target: int) -> list[int]:
                    for i in range(len(nums)):
                        for j in range(i + 1, len(nums)):
                            if nums[i] + nums[j] == target:
                                return [i, j]
                    return []
        """)
        # Analyze → Plan → Generate wrapper.
        module_info = CodeAnalyzer(source).analyze()
        plan = ExecutionPlanner.create(module_info)
        wrapper = WrapperGenerator.create(plan)

        # Prepend the original class definition to the wrapper.
        full_source = source + "\n" + wrapper.source_code

        # Execute with tracing.
        result = Executor.execute(full_source)
        self.assertTrue(result.success)
        self.assertGreater(result.total_events, 0)
        # The twoSum method should have been called.
        called = {e.function_name for e in result.events if e.event_type == EventType.CALL}
        self.assertIn("twoSum", called)


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
