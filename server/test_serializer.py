"""
test_serializer.py — Unit tests for the Serializer module.

Run:
    python test_serializer.py
    python -m unittest test_serializer -v
"""

from __future__ import annotations

import json
import textwrap
import unittest

from engine.runtime import Executor, EventType, TraceEvent, TraceFrame, TraceResult
from engine.serializer import (
    InvalidTraceError,
    SerializerConfig,
    SerializerError,
    TraceSerializer,
)


# =============================================================================
# Helpers
# =============================================================================


def _trace(source: str) -> TraceResult:
    """Execute source and return the trace result."""
    return Executor.execute(textwrap.dedent(source))


def _serialize(source: str, **config_kw) -> dict:
    """Execute, trace, and serialize in one step."""
    result = _trace(source)
    config = SerializerConfig(**config_kw) if config_kw else None
    return TraceSerializer(config).serialize(result)


# =============================================================================
# Test: Empty Trace
# =============================================================================


class TestEmptyTrace(unittest.TestCase):

    def test_empty_result(self) -> None:
        """A TraceResult with no events should serialize cleanly."""
        result = TraceResult()
        data = TraceSerializer().serialize(result)
        self.assertEqual(data["events"], [])
        self.assertEqual(data["frames"], [])
        self.assertEqual(data["total_events"], 0)
        self.assertTrue(data["success"])

    def test_empty_output(self) -> None:
        result = TraceResult(output="")
        data = TraceSerializer().serialize(result)
        self.assertEqual(data["output"], "")

    def test_empty_error(self) -> None:
        result = TraceResult(error=None)
        data = TraceSerializer().serialize(result)
        self.assertIsNone(data["error"])


# =============================================================================
# Test: None / Invalid Input
# =============================================================================


class TestInvalidInput(unittest.TestCase):

    def test_none_trace_result_raises(self) -> None:
        with self.assertRaises(InvalidTraceError):
            TraceSerializer().serialize(None)  # type: ignore[arg-type]

    def test_none_event_raises(self) -> None:
        with self.assertRaises(InvalidTraceError):
            TraceSerializer().serialize_event(None)  # type: ignore[arg-type]

    def test_none_frame_raises(self) -> None:
        with self.assertRaises(InvalidTraceError):
            TraceSerializer().serialize_frame(None)  # type: ignore[arg-type]

    def test_invalid_trace_inherits_serializer_error(self) -> None:
        self.assertTrue(issubclass(InvalidTraceError, SerializerError))


# =============================================================================
# Test: Single Event
# =============================================================================


class TestSingleEvent(unittest.TestCase):

    def test_single_assignment_event(self) -> None:
        data = _serialize("x = 42\n")
        self.assertGreater(len(data["events"]), 0)
        first = data["events"][0]
        self.assertIn("event", first)
        self.assertIn("line", first)
        self.assertIn("function", first)

    def test_event_has_sequence(self) -> None:
        data = _serialize("x = 1\n")
        self.assertEqual(data["events"][0]["sequence"], 0)

    def test_event_has_call_depth(self) -> None:
        data = _serialize("x = 1\n")
        for ev in data["events"]:
            self.assertIn("call_depth", ev)

    def test_event_type_is_string(self) -> None:
        data = _serialize("x = 1\n")
        for ev in data["events"]:
            self.assertIsInstance(ev["event"], str)
            self.assertIn(ev["event"], {"call", "line", "return", "exception"})


# =============================================================================
# Test: Multiple Events
# =============================================================================


class TestMultipleEvents(unittest.TestCase):

    def test_multiple_lines(self) -> None:
        data = _serialize("a = 1\nb = 2\nc = 3\n")
        self.assertGreater(len(data["events"]), 2)

    def test_events_ordered_by_sequence(self) -> None:
        data = _serialize("x = 1\ny = 2\nz = 3\n")
        sequences = [e["sequence"] for e in data["events"]]
        self.assertEqual(sequences, sorted(sequences))

    def test_total_events_matches_list(self) -> None:
        data = _serialize("a = 1\nb = 2\n")
        self.assertEqual(data["total_events"], len(data["events"]))


# =============================================================================
# Test: Nested Calls
# =============================================================================


class TestNestedCalls(unittest.TestCase):

    def test_nested_call_depth(self) -> None:
        source = """\
            def inner():
                return 1
            def outer():
                return inner()
            outer()
        """
        data = _serialize(source)
        depths = {e["call_depth"] for e in data["events"]}
        self.assertGreater(max(depths), 1)

    def test_frames_for_nested_calls(self) -> None:
        source = """\
            def a():
                return b()
            def b():
                return 42
            a()
        """
        data = _serialize(source)
        frame_names = {f["function_name"] for f in data["frames"]}
        self.assertIn("a", frame_names)
        self.assertIn("b", frame_names)


# =============================================================================
# Test: Recursion
# =============================================================================


class TestRecursion(unittest.TestCase):

    def test_recursive_calls_serialized(self) -> None:
        source = """\
            def fib(n):
                if n <= 1:
                    return n
                return fib(n - 1) + fib(n - 2)
            fib(4)
        """
        data = _serialize(source)
        fib_calls = [
            e for e in data["events"]
            if e["event"] == "call" and e["function"] == "fib"
        ]
        # fib(4) should produce multiple recursive calls.
        self.assertGreater(len(fib_calls), 3)

    def test_max_depth_in_result(self) -> None:
        source = """\
            def chain(n):
                if n == 0:
                    return 0
                return chain(n - 1)
            chain(3)
        """
        data = _serialize(source)
        self.assertGreaterEqual(data["max_depth"], 3)


# =============================================================================
# Test: Variable Serialization (primitives via serialize_value)
# =============================================================================


class TestValueSerialization(unittest.TestCase):

    def setUp(self) -> None:
        self.s = TraceSerializer()

    def test_int(self) -> None:
        self.assertEqual(self.s.serialize_value(42), 42)

    def test_float(self) -> None:
        self.assertAlmostEqual(self.s.serialize_value(3.14), 3.14)

    def test_bool_true(self) -> None:
        self.assertIs(self.s.serialize_value(True), True)

    def test_bool_false(self) -> None:
        self.assertIs(self.s.serialize_value(False), False)

    def test_none(self) -> None:
        self.assertIsNone(self.s.serialize_value(None))

    def test_string(self) -> None:
        self.assertEqual(self.s.serialize_value("hello"), "hello")


# =============================================================================
# Test: List Serialization
# =============================================================================


class TestListSerialization(unittest.TestCase):

    def setUp(self) -> None:
        self.s = TraceSerializer()

    def test_flat_list(self) -> None:
        self.assertEqual(self.s.serialize_value([1, 2, 3]), [1, 2, 3])

    def test_nested_list(self) -> None:
        self.assertEqual(self.s.serialize_value([[1], [2]]), [[1], [2]])

    def test_mixed_list(self) -> None:
        result = self.s.serialize_value([1, "a", True, None])
        self.assertEqual(result, [1, "a", True, None])


# =============================================================================
# Test: Tuple Serialization
# =============================================================================


class TestTupleSerialization(unittest.TestCase):

    def setUp(self) -> None:
        self.s = TraceSerializer()

    def test_tuple_becomes_list(self) -> None:
        """JSON has no tuple type; tuples are serialized as lists."""
        result = self.s.serialize_value((1, 2, 3))
        self.assertEqual(result, [1, 2, 3])
        self.assertIsInstance(result, list)

    def test_nested_tuple(self) -> None:
        result = self.s.serialize_value(((1, 2), (3, 4)))
        self.assertEqual(result, [[1, 2], [3, 4]])


# =============================================================================
# Test: Dict Serialization
# =============================================================================


class TestDictSerialization(unittest.TestCase):

    def setUp(self) -> None:
        self.s = TraceSerializer()

    def test_simple_dict(self) -> None:
        self.assertEqual(self.s.serialize_value({"a": 1}), {"a": 1})

    def test_nested_dict(self) -> None:
        result = self.s.serialize_value({"a": {"b": 2}})
        self.assertEqual(result, {"a": {"b": 2}})

    def test_non_string_keys(self) -> None:
        """Non-string dict keys must be converted to string repr."""
        result = self.s.serialize_value({1: "one", 2: "two"})
        self.assertIn("1", result)
        self.assertIn("2", result)


# =============================================================================
# Test: Set Serialization
# =============================================================================


class TestSetSerialization(unittest.TestCase):

    def setUp(self) -> None:
        self.s = TraceSerializer()

    def test_set_becomes_sorted_list(self) -> None:
        """JSON has no set type; sets become sorted lists for determinism."""
        result = self.s.serialize_value({3, 1, 2})
        self.assertEqual(result, [1, 2, 3])
        self.assertIsInstance(result, list)

    def test_frozenset(self) -> None:
        result = self.s.serialize_value(frozenset({2, 1}))
        self.assertEqual(result, [1, 2])


# =============================================================================
# Test: Unsupported Objects
# =============================================================================


class TestUnsupportedObjects(unittest.TestCase):

    def setUp(self) -> None:
        self.s = TraceSerializer()

    def test_custom_object_uses_repr(self) -> None:
        class Foo:
            def __repr__(self) -> str:
                return "Foo()"
        result = self.s.serialize_value(Foo())
        self.assertEqual(result, "Foo()")

    def test_bytes_uses_repr(self) -> None:
        result = self.s.serialize_value(b"hello")
        self.assertIsInstance(result, str)
        self.assertIn("hello", result)

    def test_repr_failure_fallback(self) -> None:
        class BadRepr:
            def __repr__(self) -> str:
                raise RuntimeError("boom")
        result = self.s.serialize_value(BadRepr())
        self.assertEqual(result, "<repr failed>")


# =============================================================================
# Test: Circular References
# =============================================================================


class TestCircularReferences(unittest.TestCase):

    def test_circular_list(self) -> None:
        s = TraceSerializer()
        lst: list = [1, 2]
        lst.append(lst)  # circular
        result = s.serialize_value(lst)
        # Should not raise; the circular part becomes a string marker.
        self.assertIsInstance(result, list)

    def test_circular_dict(self) -> None:
        s = TraceSerializer()
        d: dict = {"a": 1}
        d["self"] = d  # circular
        result = s.serialize_value(d)
        self.assertIsInstance(result, dict)


# =============================================================================
# Test: Depth Limiting
# =============================================================================


class TestDepthLimiting(unittest.TestCase):

    def test_deep_nesting_uses_repr(self) -> None:
        """Beyond max_depth, values fall back to repr."""
        config = SerializerConfig(max_depth=2)
        s = TraceSerializer(config)
        deep = {"a": {"b": {"c": {"d": {"e": 1}}}}}
        result = s.serialize_value(deep)
        # Top levels should be dicts; deeper levels become repr strings.
        self.assertIsInstance(result, dict)
        self.assertIsInstance(result["a"], dict)


# =============================================================================
# Test: Internal Variable Filtering
# =============================================================================


class TestInternalFiltering(unittest.TestCase):

    def test_builtins_excluded(self) -> None:
        data = _serialize("x = 42\n")
        for ev in data["events"]:
            self.assertNotIn("__builtins__", ev.get("locals", {}))
            self.assertNotIn("__builtins__", ev.get("globals", {}))

    def test_spec_excluded(self) -> None:
        data = _serialize("x = 1\n")
        for ev in data["events"]:
            self.assertNotIn("__spec__", ev.get("globals", {}))

    def test_filter_disabled(self) -> None:
        """With filter_internals=False, dunder names pass through."""
        event = TraceEvent(
            sequence=0,
            event_type=EventType.LINE,
            filename="<test>",
            function_name="<module>",
            lineno=1,
            locals_snap={"__test__": "val", "x": "1"},
            globals_snap={},
        )
        config = SerializerConfig(filter_internals=False)
        data = TraceSerializer(config).serialize_event(event)
        self.assertIn("__test__", data["locals"])


# =============================================================================
# Test: Ordering Preservation
# =============================================================================


class TestOrdering(unittest.TestCase):

    def test_events_preserve_sequence_order(self) -> None:
        data = _serialize("a = 1\nb = 2\nc = 3\n")
        sequences = [e["sequence"] for e in data["events"]]
        for i in range(1, len(sequences)):
            self.assertGreater(sequences[i], sequences[i - 1])

    def test_timestamp_ordering(self) -> None:
        data = _serialize("x = 1\ny = 2\n")
        timestamps = [e["timestamp_ns"] for e in data["events"]]
        for i in range(1, len(timestamps)):
            self.assertGreaterEqual(timestamps[i], timestamps[i - 1])


# =============================================================================
# Test: JSON-Safe Output
# =============================================================================


class TestJsonSafe(unittest.TestCase):

    def test_full_output_is_json_serializable(self) -> None:
        data = _serialize("x = [1, 2, 3]\ny = {'a': 1}\nprint(x, y)\n")
        # This must not raise.
        json_str = json.dumps(data)
        self.assertIsInstance(json_str, str)

    def test_error_result_is_json_serializable(self) -> None:
        result = _trace("raise ValueError('boom')\n")
        data = TraceSerializer().serialize(result)
        json_str = json.dumps(data)
        self.assertIsInstance(json_str, str)
        self.assertFalse(data["success"])

    def test_recursive_code_is_json_serializable(self) -> None:
        source = """\
            def fact(n):
                return 1 if n <= 1 else n * fact(n - 1)
            fact(5)
        """
        data = _serialize(source)
        json_str = json.dumps(data)
        self.assertIsInstance(json_str, str)


# =============================================================================
# Test: Config Options
# =============================================================================


class TestConfig(unittest.TestCase):

    def test_exclude_globals(self) -> None:
        config = SerializerConfig(include_globals=False)
        result = _trace("x = 1\n")
        data = TraceSerializer(config).serialize(result)
        for ev in data["events"]:
            self.assertNotIn("globals", ev)

    def test_exclude_timestamps(self) -> None:
        config = SerializerConfig(include_timestamps=False)
        result = _trace("x = 1\n")
        data = TraceSerializer(config).serialize(result)
        for ev in data["events"]:
            self.assertNotIn("timestamp_ns", ev)

    def test_default_config_includes_all(self) -> None:
        data = _serialize("x = 1\n")
        first = data["events"][0]
        self.assertIn("globals", first)
        self.assertIn("timestamp_ns", first)

    def test_config_is_frozen(self) -> None:
        config = SerializerConfig()
        with self.assertRaises(AttributeError):
            config.max_depth = 99  # type: ignore[misc]


# =============================================================================
# Test: Return Values and Exceptions in Events
# =============================================================================


class TestReturnAndException(unittest.TestCase):

    def test_return_value_present(self) -> None:
        source = """\
            def double(n):
                return n * 2
            double(5)
        """
        data = _serialize(source)
        returns = [e for e in data["events"] if e.get("return_value")]
        self.assertGreater(len(returns), 0)

    def test_exception_info_present(self) -> None:
        source = """\
            try:
                1 / 0
            except:
                pass
        """
        data = _serialize(source)
        exceptions = [e for e in data["events"] if e.get("exception_info")]
        self.assertGreater(len(exceptions), 0)


# =============================================================================
# Test: Full Pipeline Integration
# =============================================================================


class TestFullPipeline(unittest.TestCase):

    def test_analyzer_to_serializer(self) -> None:
        """End-to-end: Analyzer → Planner → Wrapper → Executor → Serializer."""
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

        module_info = CodeAnalyzer(source).analyze()
        plan = ExecutionPlanner.create(module_info)
        wrapper = WrapperGenerator.create(plan)
        full_source = source + "\n" + wrapper.source_code

        trace_result = Executor.execute(full_source)
        data = TraceSerializer().serialize(trace_result)

        # Validate JSON-safe.
        json_str = json.dumps(data)
        self.assertIsInstance(json_str, str)
        self.assertTrue(data["success"])
        self.assertGreater(data["total_events"], 0)

        # twoSum must appear in the events.
        called = {e["function"] for e in data["events"] if e["event"] == "call"}
        self.assertIn("twoSum", called)


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
