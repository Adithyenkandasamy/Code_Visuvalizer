"""
planner.py — Execution Planner for Code Vision.

Converts Analyzer output (``ModuleInfo``) into a structured
``ExecutionPlan`` that describes HOW the code should be executed
— without ever executing it.

Architecture:
    Analyzer (ModuleInfo)  →  ExecutionPlanner  →  ExecutionPlan

The planner is framework-agnostic: it knows nothing about FastAPI,
React, or any runtime.  It is a pure compiler stage.
"""

from __future__ import annotations

from analyzer import (
    ClassInfo,
    FunctionInfo,
    ModuleInfo,
    ParameterInfo,
    ParameterKind as AnalyzerParameterKind,
)

from engine.planner.exceptions import (
    InvalidModuleError,
    NoExecutableFoundError,
    PlannerError,
)
from engine.planner.models import (
    CallType,
    ExecutionPlan,
    ParameterKind,
    PlannedParameter,
)


# =============================================================================
# Parameter-Kind Mapping  (Analyzer → Planner)
# =============================================================================

_PARAM_KIND_MAP: dict[AnalyzerParameterKind, ParameterKind] = {
    AnalyzerParameterKind.POSITIONAL_ONLY: ParameterKind.POSITIONAL_ONLY,
    AnalyzerParameterKind.POSITIONAL_OR_KEYWORD: ParameterKind.POSITIONAL_OR_KEYWORD,
    AnalyzerParameterKind.VAR_POSITIONAL: ParameterKind.VAR_POSITIONAL,
    AnalyzerParameterKind.KEYWORD_ONLY: ParameterKind.KEYWORD_ONLY,
    AnalyzerParameterKind.VAR_KEYWORD: ParameterKind.VAR_KEYWORD,
}


def _map_kind(analyzer_kind: AnalyzerParameterKind) -> ParameterKind:
    """Map an analyzer ``ParameterKind`` to the planner's own enum."""
    return _PARAM_KIND_MAP[analyzer_kind]


# =============================================================================
# Call-Type Detection
# =============================================================================

# Implicit receiver parameter names that should be stripped from the
# invocation parameter list.
_SELF_NAMES: frozenset[str] = frozenset({"self"})
_CLS_NAMES: frozenset[str] = frozenset({"cls", "klass"})


def _determine_call_type(func: FunctionInfo, *, is_method: bool) -> CallType:
    """
    Determine the ``CallType`` for a function or method.

    Priority (highest → lowest):
        1. @staticmethod decorator  → STATIC_METHOD
        2. @classmethod decorator   → CLASS_METHOD_DECORATOR
        3. Instance method (self)   → CLASS_METHOD
        4. Async (top-level)        → ASYNC_FUNCTION
        5. Regular function         → FUNCTION
    """
    decorator_names = {d.split("(")[0] for d in func.decorators}

    if is_method:
        if "staticmethod" in decorator_names:
            return CallType.STATIC_METHOD
        if "classmethod" in decorator_names:
            return CallType.CLASS_METHOD_DECORATOR
        return CallType.CLASS_METHOD

    # Top-level function.
    if func.is_async:
        return CallType.ASYNC_FUNCTION
    return CallType.FUNCTION


# =============================================================================
# Parameter Extraction
# =============================================================================


def _build_parameters(
    func: FunctionInfo,
    call_type: CallType,
) -> list[PlannedParameter]:
    """
    Convert analyzer ``ParameterInfo`` objects into ``PlannedParameter``
    objects, filtering out implicit receiver params (``self`` / ``cls``).
    """
    params = list(func.parameters)

    # Strip the implicit first parameter for instance / class methods.
    if params:
        first = params[0].name
        if call_type == CallType.CLASS_METHOD and first in _SELF_NAMES:
            params = params[1:]
        elif call_type == CallType.CLASS_METHOD_DECORATOR and first in _CLS_NAMES:
            params = params[1:]

    return [
        PlannedParameter(
            name=p.name,
            annotation=p.annotation,
            kind=_map_kind(p.kind),
        )
        for p in params
    ]


# =============================================================================
# Entry-Point Selection Heuristics
# =============================================================================


def _find_entry_in_classes(
    classes: list[ClassInfo],
) -> tuple[ClassInfo, FunctionInfo] | None:
    """
    Search classes for the best entry-point method.

    Heuristic (in order):
        1. First class with a public (non-dunder) method.
        2. First class with any non-``__init__`` method.
        3. First class with ``__init__`` (last resort).
    """
    # Pass 1: public non-dunder methods.
    for cls in classes:
        public = [m for m in cls.methods if not m.name.startswith("_")]
        if public:
            return cls, public[0]

    # Pass 2: any non-__init__ method (includes dunder like __call__).
    for cls in classes:
        non_init = [m for m in cls.methods if m.name != "__init__"]
        if non_init:
            return cls, non_init[0]

    # Pass 3: __init__ itself.
    for cls in classes:
        if cls.methods:
            return cls, cls.methods[0]

    return None


def _find_entry_in_functions(
    functions: list[FunctionInfo],
) -> FunctionInfo | None:
    """
    Search top-level functions for the best entry point.

    Prefers ``main``, then public functions, then any function.
    """
    # Prefer a function named "main".
    for fn in functions:
        if fn.name == "main":
            return fn

    # Public (non-private) functions.
    for fn in functions:
        if not fn.name.startswith("_"):
            return fn

    # Fallback: any function.
    return functions[0] if functions else None


# =============================================================================
# ExecutionPlanner — Public API
# =============================================================================


class ExecutionPlanner:
    """
    Converts ``ModuleInfo`` (from the Analyzer) into an ``ExecutionPlan``.

    Usage (instance style)::

        planner = ExecutionPlanner(module_info)
        plan = planner.plan()

    Usage (class-method shortcut)::

        plan = ExecutionPlanner.create(module_info)

    The planner never executes code.  It only reasons about structure.
    """

    def __init__(
        self,
        module_info: ModuleInfo,
        *,
        module_name: str = "__main__",
    ) -> None:
        if module_info is None:
            raise InvalidModuleError("ModuleInfo must not be None.")
        self._module_info = module_info
        self._module_name = module_name

    # ── Public API ─────────────────────────────────────────────────────

    def plan(self) -> ExecutionPlan:
        """
        Analyze the module and produce an ``ExecutionPlan``.

        Returns:
            A frozen ``ExecutionPlan`` describing the invocation strategy.

        Raises:
            NoExecutableFoundError: If no callable entry point exists.
        """
        entry_class, entry_func = self._resolve_entry_point()
        is_method = entry_class is not None
        call_type = _determine_call_type(entry_func, is_method=is_method)
        parameters = _build_parameters(entry_func, call_type)

        return ExecutionPlan(
            module_name=self._module_name,
            entry_function=entry_func.name,
            call_type=call_type,
            parameters=parameters,
            entry_class=entry_class.name if entry_class else None,
        )

    @classmethod
    def create(
        cls,
        module_info: ModuleInfo,
        *,
        module_name: str = "__main__",
    ) -> ExecutionPlan:
        """Convenience class method: build a plan in one call."""
        return cls(module_info, module_name=module_name).plan()

    # ── Internals ──────────────────────────────────────────────────────

    def _resolve_entry_point(self) -> tuple[ClassInfo | None, FunctionInfo]:
        """
        Select the most appropriate entry point from the module.

        Strategy:
            1. Look inside classes for a suitable method.
            2. Fall back to top-level functions.
            3. Raise if nothing found.
        """
        mi = self._module_info

        # Try classes first (common pattern: Solution.twoSum).
        class_result = _find_entry_in_classes(mi.classes)
        if class_result is not None:
            return class_result

        # Try top-level functions.
        func_result = _find_entry_in_functions(mi.functions)
        if func_result is not None:
            return None, func_result

        raise NoExecutableFoundError(
            "Module contains no functions or methods that can serve as an entry point."
        )
