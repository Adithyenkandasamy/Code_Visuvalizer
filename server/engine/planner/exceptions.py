"""
exceptions.py — Custom exceptions for the Execution Planner.

All planner exceptions inherit from PlannerError so callers
can catch the entire family with a single except clause.
"""

from __future__ import annotations


class PlannerError(Exception):
    """Base exception for all planner-related errors."""


class NoExecutableFoundError(PlannerError):
    """
    Raised when the module contains no function or method
    that qualifies as an entry point for execution.
    """

    def __init__(self, message: str = "No executable function or method found.") -> None:
        super().__init__(message)


class InvalidModuleError(PlannerError):
    """
    Raised when the provided ModuleInfo is structurally invalid
    or cannot be processed by the planner.
    """

    def __init__(self, message: str = "Invalid module information provided.") -> None:
        super().__init__(message)
