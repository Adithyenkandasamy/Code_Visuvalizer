"""
test_orchestrator.py — Unit tests for the Engine Orchestrator.

Run:
    python test_orchestrator.py
    python -m unittest test_orchestrator -v
"""

from __future__ import annotations

import logging
import textwrap
import unittest
from unittest.mock import MagicMock

from engine.orchestrator import CodeVisionEngine, EngineError


# =============================================================================
# Mock Classes
# =============================================================================

class MockAnalyzer:
    def __init__(self, source: str) -> None:
        self.source = source

    def analyze(self) -> MagicMock:
        return MagicMock(name="ModuleInfo")


class MockPlanner:
    @classmethod
    def create(cls, module_info: MagicMock) -> MagicMock:
        return MagicMock(name="ExecutionPlan")


class MockWrapper:
    @classmethod
    def create(cls, plan: MagicMock) -> MagicMock:
        mock = MagicMock(name="GeneratedSource")
        mock.source_code = "mock_wrapper_source()"
        return mock


class MockExecutor:
    @classmethod
    def execute(cls, source_code: str) -> MagicMock:
        return MagicMock(name="TraceResult")


class MockSerializer:
    def serialize(self, trace_result: MagicMock) -> dict:
        return {"status": "success", "events": []}


# =============================================================================
# Test: Success & Dependency Injection
# =============================================================================

class TestEngineSuccess(unittest.TestCase):
    def setUp(self) -> None:
        # Disable logging output during tests unless debugging
        logging.getLogger("engine.orchestrator.engine").setLevel(logging.CRITICAL)

    def test_successful_pipeline(self) -> None:
        """Verify the pipeline completes and returns the serialized dict."""
        engine = CodeVisionEngine(
            analyzer_cls=MockAnalyzer,
            planner_cls=MockPlanner,
            wrapper_cls=MockWrapper,
            executor_cls=MockExecutor,
            serializer_cls=MockSerializer,
        )
        result = engine.visualize("def f(): pass")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["status"], "success")

    def test_execution_order(self) -> None:
        """Verify each stage is called with the output of the previous stage."""
        mock_analyzer_instance = MagicMock()
        mock_analyzer_factory = MagicMock(return_value=mock_analyzer_instance)
        
        mock_module_info = MagicMock()
        mock_analyzer_instance.analyze.return_value = mock_module_info
        
        mock_plan = MagicMock()
        mock_planner = MagicMock()
        mock_planner.create.return_value = mock_plan
        
        mock_wrapper_obj = MagicMock()
        mock_wrapper_obj.source_code = "mock_code"
        mock_wrapper = MagicMock()
        mock_wrapper.create.return_value = mock_wrapper_obj
        
        mock_trace = MagicMock()
        mock_executor = MagicMock()
        mock_executor.execute.return_value = mock_trace
        
        mock_serializer_instance = MagicMock()
        mock_serializer_instance.serialize.return_value = {"done": True}
        mock_serializer = MagicMock(return_value=mock_serializer_instance)

        engine = CodeVisionEngine(
            analyzer_cls=mock_analyzer_factory,
            planner_cls=mock_planner,
            wrapper_cls=mock_wrapper,
            executor_cls=mock_executor,
            serializer_cls=mock_serializer,
        )
        
        source = "def a(): pass"
        result = engine.visualize(source)
        
        # 1. Analyzer called with source
        mock_analyzer_factory.assert_called_once_with(source)
        mock_analyzer_instance.analyze.assert_called_once()
        
        # 2. Planner called with module_info
        mock_planner.create.assert_called_once_with(mock_module_info)
        
        # 3. Wrapper called with plan
        mock_wrapper.create.assert_called_once_with(mock_plan)
        
        # 4. Executor called with combined source
        expected_full_source = f"{source}\n\nmock_code"
        mock_executor.execute.assert_called_once_with(expected_full_source)
        
        # 5. Serializer called with trace
        mock_serializer_instance.serialize.assert_called_once_with(mock_trace)
        
        self.assertEqual(result, {"done": True})


# =============================================================================
# Test: Failures & Exception Chaining
# =============================================================================

class TestEngineFailures(unittest.TestCase):
    def setUp(self) -> None:
        logging.getLogger("engine.orchestrator.engine").setLevel(logging.CRITICAL)

    def test_analyzer_failure(self) -> None:
        mock_analyzer = MagicMock()
        mock_analyzer.side_effect = ValueError("Syntax error")
        engine = CodeVisionEngine(analyzer_cls=mock_analyzer)
        
        with self.assertRaises(EngineError) as ctx:
            engine.visualize("bad source")
        
        self.assertEqual(ctx.exception.stage, "analyzer")
        self.assertIsInstance(ctx.exception.__cause__, ValueError)

    def test_planner_failure(self) -> None:
        mock_planner = MagicMock()
        mock_planner.create.side_effect = RuntimeError("No entry point")
        engine = CodeVisionEngine(
            analyzer_cls=MockAnalyzer,
            planner_cls=mock_planner,
        )
        
        with self.assertRaises(EngineError) as ctx:
            engine.visualize("def f(): pass")
            
        self.assertEqual(ctx.exception.stage, "planner")
        self.assertIsInstance(ctx.exception.__cause__, RuntimeError)

    def test_wrapper_failure(self) -> None:
        mock_wrapper = MagicMock()
        mock_wrapper.create.side_effect = TypeError("Invalid plan")
        engine = CodeVisionEngine(
            analyzer_cls=MockAnalyzer,
            planner_cls=MockPlanner,
            wrapper_cls=mock_wrapper,
        )
        
        with self.assertRaises(EngineError) as ctx:
            engine.visualize("def f(): pass")
            
        self.assertEqual(ctx.exception.stage, "wrapper")
        self.assertIsInstance(ctx.exception.__cause__, TypeError)

    def test_runtime_failure(self) -> None:
        mock_executor = MagicMock()
        mock_executor.execute.side_effect = MemoryError("Out of memory")
        engine = CodeVisionEngine(
            analyzer_cls=MockAnalyzer,
            planner_cls=MockPlanner,
            wrapper_cls=MockWrapper,
            executor_cls=mock_executor,
        )
        
        with self.assertRaises(EngineError) as ctx:
            engine.visualize("def f(): pass")
            
        self.assertEqual(ctx.exception.stage, "runtime")
        self.assertIsInstance(ctx.exception.__cause__, MemoryError)

    def test_serializer_failure(self) -> None:
        mock_serializer_instance = MagicMock()
        mock_serializer_instance.serialize.side_effect = KeyError("Missing field")
        mock_serializer = MagicMock(return_value=mock_serializer_instance)
        
        engine = CodeVisionEngine(
            analyzer_cls=MockAnalyzer,
            planner_cls=MockPlanner,
            wrapper_cls=MockWrapper,
            executor_cls=MockExecutor,
            serializer_cls=mock_serializer,
        )
        
        with self.assertRaises(EngineError) as ctx:
            engine.visualize("def f(): pass")
            
        self.assertEqual(ctx.exception.stage, "serializer")
        self.assertIsInstance(ctx.exception.__cause__, KeyError)


# =============================================================================
# Test: Full Integration Pipeline
# =============================================================================

class TestFullIntegration(unittest.TestCase):
    def setUp(self) -> None:
        logging.getLogger("engine.orchestrator.engine").setLevel(logging.CRITICAL)
        self.engine = CodeVisionEngine()  # Uses defaults (real modules)

    def test_full_pipeline_success(self) -> None:
        source = textwrap.dedent("""\
            def compute(x: int) -> int:
                return x * 2
        """)
        # If it runs without raising EngineError, the orchestrator successfully
        # connected all 5 stages.
        result = self.engine.visualize(source)
        
        self.assertIsInstance(result, dict)
        self.assertIn("events", result)
        self.assertIn("frames", result)
        self.assertTrue(result["success"])
        
        # Verify the wrapper called compute
        called_functions = [
            e["function"] for e in result["events"] 
            if e["event"] == "call"
        ]
        self.assertIn("compute", called_functions)

    def test_full_pipeline_syntax_error(self) -> None:
        source = "def compute("  # Invalid syntax
        
        with self.assertRaises(EngineError) as ctx:
            self.engine.visualize(source)
            
        self.assertEqual(ctx.exception.stage, "analyzer")
        
    def test_full_pipeline_runtime_error(self) -> None:
        source = textwrap.dedent("""\
            def compute():
                return 1 / 0
        """)
        # The runtime actually captures the ZeroDivisionError and returns a 
        # TraceResult with success=False, so this doesn't raise a runtime exception
        # in the orchestrator itself! It completes successfully.
        result = self.engine.visualize(source)
        
        self.assertIsInstance(result, dict)
        self.assertFalse(result["success"])
        self.assertIsNotNone(result["error"])
        self.assertIn("ZeroDivisionError", result["error"])

    def test_full_pipeline_no_entry_point(self) -> None:
        source = "import os\nx = 1\n"
        
        # This will fail at the Planner stage because it can't find an entry point
        with self.assertRaises(EngineError) as ctx:
            self.engine.visualize(source)
            
        self.assertEqual(ctx.exception.stage, "planner")

    def test_verify_returned_json(self) -> None:
        """Ensure the output dictionary is strictly JSON serializable."""
        import json
        source = "def foo(): return 42"
        result = self.engine.visualize(source)
        
        try:
            json_str = json.dumps(result)
            self.assertIsInstance(json_str, str)
        except TypeError as e:
            self.fail(f"Pipeline output is not JSON serializable: {e}")


# =============================================================================
# Test: Edge Cases
# =============================================================================

class TestEdgeCases(unittest.TestCase):
    def setUp(self) -> None:
        logging.getLogger("engine.orchestrator.engine").setLevel(logging.CRITICAL)

    def test_empty_source(self) -> None:
        engine = CodeVisionEngine()
        with self.assertRaises(EngineError) as ctx:
            engine.visualize("")
        self.assertEqual(ctx.exception.stage, "analyzer")

    def test_whitespace_only_source(self) -> None:
        engine = CodeVisionEngine()
        with self.assertRaises(EngineError) as ctx:
            engine.visualize("   \n  \t ")
        self.assertEqual(ctx.exception.stage, "analyzer")

    def test_engine_error_message(self) -> None:
        err = EngineError("Something broke", stage="wrapper")
        self.assertEqual(str(err), "Something broke")

    def test_engine_error_stage(self) -> None:
        err = EngineError("Something broke", stage="wrapper")
        self.assertEqual(err.stage, "wrapper")

    def test_engine_error_no_stage(self) -> None:
        err = EngineError("Generic error")
        self.assertIsNone(err.stage)
        self.assertEqual(str(err), "Generic error")

    def test_di_defaults(self) -> None:
        """Verify the engine loads the correct default production classes."""
        from analyzer import CodeAnalyzer
        from engine.planner import ExecutionPlanner
        from engine.wrapper import WrapperGenerator
        from engine.runtime import Executor
        from engine.serializer import TraceSerializer
        
        engine = CodeVisionEngine()
        self.assertIs(engine._analyzer_cls, CodeAnalyzer)
        self.assertIs(engine._planner_cls, ExecutionPlanner)
        self.assertIs(engine._wrapper_cls, WrapperGenerator)
        self.assertIs(engine._executor_cls, Executor)
        self.assertIs(engine._serializer_cls, TraceSerializer)

    def test_partial_di(self) -> None:
        """Verify we can inject just one dependency and the rest default."""
        engine = CodeVisionEngine(analyzer_cls=MockAnalyzer)
        self.assertIs(engine._analyzer_cls, MockAnalyzer)
        
        from engine.planner import ExecutionPlanner
        self.assertIs(engine._planner_cls, ExecutionPlanner)

    def test_full_pipeline_class_method(self) -> None:
        source = textwrap.dedent("""\
            class Calc:
                def add(self, a: int, b: int) -> int:
                    return a + b
        """)
        engine = CodeVisionEngine()
        result = engine.visualize(source)
        self.assertTrue(result["success"])
        
    def test_full_pipeline_async_function(self) -> None:
        source = textwrap.dedent("""\
            import asyncio
            async def run():
                return 42
        """)
        engine = CodeVisionEngine()
        result = engine.visualize(source)
        self.assertTrue(result["success"])

    def test_full_pipeline_static_method(self) -> None:
        source = textwrap.dedent("""\
            class Math:
                @staticmethod
                def get_pi():
                    return 3.14
        """)
        engine = CodeVisionEngine()
        result = engine.visualize(source)
        self.assertTrue(result["success"])

    def test_full_pipeline_logging(self) -> None:
        """Verify the orchestrator logs events properly."""
        with self.assertLogs("engine.orchestrator.engine", level="DEBUG") as cm:
            CodeVisionEngine().visualize("def f(): pass")
            
        logs = "\n".join(cm.output)
        self.assertIn("Starting Code Vision pipeline", logs)
        self.assertIn("Stage 1: Analyzing", logs)
        self.assertIn("Stage 2: Creating execution plan", logs)
        self.assertIn("Stage 3: Generating wrapper", logs)
        self.assertIn("Stage 4: Executing runtime", logs)
        self.assertIn("Stage 5: Serializing", logs)
        self.assertIn("completed successfully", logs)

    def test_failure_logging(self) -> None:
        mock_analyzer = MagicMock(side_effect=ValueError("Boom"))
        engine = CodeVisionEngine(analyzer_cls=mock_analyzer)
        
        with self.assertLogs("engine.orchestrator.engine", level="ERROR") as cm:
            with self.assertRaises(EngineError):
                engine.visualize("code")
                
        self.assertIn("Pipeline failed at Stage 1", cm.output[0])
        self.assertIn("Boom", cm.output[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
