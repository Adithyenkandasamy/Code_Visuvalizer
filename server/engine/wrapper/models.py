"""
models.py — Frozen dataclasses for the Wrapper Generator.

These models carry structured data between the generator,
input generator, and template renderer without any coupling
to the planner or analyzer.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class GeneratedVariable:
    """
    A single input variable to be declared in the generated source.

    Attributes:
        name:  Variable name  (e.g. ``nums``).
        value: Python literal  (e.g. ``[2, 7, 11, 15]``).
    """

    name: str
    value: str


@dataclass(frozen=True, slots=True)
class GeneratedSource:
    """
    The final output of the wrapper generator.

    Attributes:
        source_code: Complete, runnable Python source string.
        variables:   The input variables that were generated.
        call_expr:   The function/method call expression.
    """

    source_code: str
    variables: list[GeneratedVariable] = field(default_factory=list)
    call_expr: str = ""
