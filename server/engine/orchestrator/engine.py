"""
engine.py — The core orchestrator for Code Vision.

Coordinates the five pipeline stages:
    1. Analyzer
    2. Planner
    3. Wrapper Generator
    4. Runtime / Tracer
    5. Serializer

This module contains no business logic itself. It delegates all
heavy lifting to the injected dependencies.
"""

from __future__ import annotations

import logging
from typing import Any

from analyzer import CodeAnalyzer
from engine.planner import ExecutionPlanner
from engine.runtime import Executor
from engine.serializer import TraceSerializer
from engine.wrapper import WrapperGenerator

from engine.orchestrator.exceptions import EngineError
from engine.orchestrator.models import (
    AnalyzerFactory,
    ExecutorFactory,
    PlannerFactory,
    SerializerFactory,
    WrapperFactory,
)


logger = logging.getLogger(__name__)


class CodeVisionEngine:
    """
    Orchestrates the Code Vision pipeline.

    Defaults to the production implementations of each stage, but
    allows full dependency injection for testing or customisation.
    """

    def __init__(
        self,
        *,
        analyzer_cls: AnalyzerFactory = CodeAnalyzer,
        planner_cls: PlannerFactory = ExecutionPlanner,
        wrapper_cls: WrapperFactory = WrapperGenerator,
        executor_cls: ExecutorFactory = Executor,
        serializer_cls: SerializerFactory = TraceSerializer,
    ) -> None:
        self._analyzer_cls = analyzer_cls
        self._planner_cls = planner_cls
        self._wrapper_cls = wrapper_cls
        self._executor_cls = executor_cls
        self._serializer_cls = serializer_cls

    def visualize(self, source: str) -> dict[str, Any]:
        """
        Run the complete execution and tracing pipeline.

        Args:
            source: Raw Python source code to analyze and trace.

        Returns:
            A JSON-safe dictionary containing the execution trace.

        Raises:
            EngineError: If any pipeline stage fails. The original
                         exception is preserved in ``__cause__``.
        """
        logger.info("Starting Code Vision pipeline.")
        
        # Stage 1: Analyze
        try:
            logger.debug("Stage 1: Analyzing source code.")
            analyzer = self._analyzer_cls(source)
            module_info = analyzer.analyze()
        except Exception as e:
            logger.error("Pipeline failed at Stage 1 (Analyzer): %s", e)
            raise EngineError(f"Analyzer failed: {e}", stage="analyzer") from e

        # Stage 2: Plan
        try:
            logger.debug("Stage 2: Creating execution plan.")
            plan = self._planner_cls.create(module_info)
        except Exception as e:
            logger.error("Pipeline failed at Stage 2 (Planner): %s", e)
            raise EngineError(f"Planner failed: {e}", stage="planner") from e

        # Stage 3: Wrapper
        try:
            logger.debug("Stage 3: Generating wrapper.")
            wrapper = self._wrapper_cls.create(plan)
            # Combine the original source with the generated instantiation/call logic.
            full_source = f"{source}\n\n{wrapper.source_code}"
        except Exception as e:
            logger.error("Pipeline failed at Stage 3 (Wrapper): %s", e)
            raise EngineError(f"Wrapper Generator failed: {e}", stage="wrapper") from e

        # Stage 4: Runtime
        try:
            logger.debug("Stage 4: Executing runtime.")
            trace_result = self._executor_cls.execute(full_source)
        except Exception as e:
            logger.error("Pipeline failed at Stage 4 (Runtime): %s", e)
            raise EngineError(f"Runtime execution failed: {e}", stage="runtime") from e

        # Stage 5: Serialize
        try:
            logger.debug("Stage 5: Serializing trace.")
            serializer = self._serializer_cls()
            result = serializer.serialize(trace_result)
        except Exception as e:
            logger.error("Pipeline failed at Stage 5 (Serializer): %s", e)
            raise EngineError(f"Serialization failed: {e}", stage="serializer") from e

        logger.info("Code Vision pipeline completed successfully.")
        return result
