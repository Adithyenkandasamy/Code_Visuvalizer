"""
models.py — Type protocols for Engine Orchestrator dependency injection.

Defines structural typing (Protocols) so the orchestrator can accept
any implementation of the underlying modules, as long as they provide
the required methods.
"""

from __future__ import annotations

from typing import Any, Protocol

# These imports are only for type hinting the Protocols.
# The orchestrator itself doesn't depend on their internal business logic.
from analyzer import ModuleInfo
from engine.planner.models import ExecutionPlan
from engine.runtime.models import TraceResult
from engine.wrapper.models import GeneratedSource


# =============================================================================
# Stage 1: Analyzer
# =============================================================================

class AnalyzerInstance(Protocol):
    def analyze(self) -> ModuleInfo:
        ...


class AnalyzerFactory(Protocol):
    def __call__(self, source: str) -> AnalyzerInstance:
        ...


# =============================================================================
# Stage 2: Planner
# =============================================================================

class PlannerFactory(Protocol):
    def create(self, module_info: ModuleInfo, module_name: str = ...) -> ExecutionPlan:
        ...


# =============================================================================
# Stage 3: Wrapper Generator
# =============================================================================

class WrapperFactory(Protocol):
    def create(self, plan: ExecutionPlan) -> GeneratedSource:
        ...


# =============================================================================
# Stage 4: Runtime / Tracer
# =============================================================================

class ExecutorFactory(Protocol):
    def execute(self, source_code: str) -> TraceResult:
        ...


# =============================================================================
# Stage 5: Serializer
# =============================================================================

class SerializerInstance(Protocol):
    def serialize(self, trace_result: TraceResult) -> dict[str, Any]:
        ...


class SerializerFactory(Protocol):
    def __call__(self) -> SerializerInstance:
        ...
