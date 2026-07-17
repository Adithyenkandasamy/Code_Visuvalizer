"""
models.py — Frozen dataclasses for the Execution Planner.

These models are intentionally decoupled from the Analyzer's own
dataclasses so the planner can evolve independently.  A mapping
layer in planner.py bridges the two.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


# =============================================================================
# Enumerations
# =============================================================================


class CallType(Enum):
    """
    Describes HOW the entry point should be invoked.

    FUNCTION             — plain top-level function call
    CLASS_METHOD         — instance method  (needs object instantiation)
    STATIC_METHOD        — @staticmethod    (call on class directly)
    CLASS_METHOD_DECORATOR — @classmethod   (receives cls as first arg)
    ASYNC_FUNCTION       — async callable   (requires await)
    """

    FUNCTION = "FUNCTION"
    CLASS_METHOD = "CLASS_METHOD"
    STATIC_METHOD = "STATIC_METHOD"
    CLASS_METHOD_DECORATOR = "CLASS_METHOD_DECORATOR"
    ASYNC_FUNCTION = "ASYNC_FUNCTION"


class ParameterKind(Enum):
    """
    Mirrors Python's five parameter categories.

    The planner defines its own enum (rather than re-using the
    analyzer's) to maintain a clean architectural boundary.
    """

    POSITIONAL_ONLY = auto()
    POSITIONAL_OR_KEYWORD = auto()
    VAR_POSITIONAL = auto()
    KEYWORD_ONLY = auto()
    VAR_KEYWORD = auto()


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True, slots=True)
class PlannedParameter:
    """
    A single parameter in the execution plan.

    Attributes:
        name:       Parameter name (``self`` / ``cls`` are already filtered out).
        annotation: String form of the type annotation, or ``None``.
        kind:       The parameter category.
    """

    name: str
    annotation: str | None = None
    kind: ParameterKind = ParameterKind.POSITIONAL_OR_KEYWORD


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """
    A structured, immutable description of HOW a piece of Python code
    should be executed — without actually executing it.

    Attributes:
        module_name:    Logical module name (defaults to ``__main__``).
        entry_function: Name of the function / method to invoke.
        call_type:      Invocation strategy (see ``CallType``).
        parameters:     Ordered list of parameters the caller must supply.
        entry_class:    Owning class name, or ``None`` for top-level functions.
    """

    module_name: str
    entry_function: str
    call_type: CallType
    parameters: list[PlannedParameter] = field(default_factory=list)
    entry_class: str | None = None
