"""
exceptions.py — Custom exceptions for the Wrapper Generator.
"""

from __future__ import annotations


class WrapperError(Exception):
    """Base exception for all wrapper-generator errors."""


class InvalidPlanError(WrapperError):
    """Raised when the ExecutionPlan is invalid or incomplete."""

    def __init__(self, message: str = "Invalid execution plan.") -> None:
        super().__init__(message)


class UnsupportedCallTypeError(WrapperError):
    """Raised when the call type is not supported by the generator."""

    def __init__(self, call_type: str) -> None:
        super().__init__(f"Unsupported call type: {call_type}")


class TemplateRenderError(WrapperError):
    """Raised when the template renderer fails to produce valid output."""

    def __init__(self, message: str = "Template rendering failed.") -> None:
        super().__init__(message)
