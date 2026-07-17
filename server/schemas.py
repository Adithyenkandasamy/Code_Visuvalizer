"""
schemas.py — Pydantic models for the Code Vision REST API.

These models handle serialisation between the internal frozen
dataclasses (analyzer / planner) and the JSON wire format.
The API layer owns these schemas; the compiler stages remain
completely unaware of FastAPI or Pydantic.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# =============================================================================
# Request
# =============================================================================


class AnalyzeRequest(BaseModel):
    """Payload sent by the client."""

    source_code: str = Field(
        ...,
        min_length=1,
        description="Python source code to analyse.",
        examples=["def add(a: int, b: int) -> int:\n    return a + b\n"],
    )
    module_name: str = Field(
        default="__main__",
        description="Logical module name for the execution plan.",
    )


# =============================================================================
# Response — Analyzer
# =============================================================================


class ImportInfoResponse(BaseModel):
    module: str
    name: str | None = None
    alias: str | None = None
    kind: str
    lineno: int


class ParameterInfoResponse(BaseModel):
    name: str
    annotation: str | None = None
    default_value: str | None = None
    kind: str


class FunctionInfoResponse(BaseModel):
    name: str
    parameters: list[ParameterInfoResponse] = []
    return_annotation: str | None = None
    decorators: list[str] = []
    docstring: str | None = None
    is_async: bool = False
    is_method: bool = False
    lineno: int = 0
    end_lineno: int | None = None


class ClassInfoResponse(BaseModel):
    name: str
    bases: list[str] = []
    methods: list[FunctionInfoResponse] = []
    decorators: list[str] = []
    docstring: str | None = None
    lineno: int = 0
    end_lineno: int | None = None


class ModuleInfoResponse(BaseModel):
    imports: list[ImportInfoResponse] = []
    classes: list[ClassInfoResponse] = []
    functions: list[FunctionInfoResponse] = []
    docstring: str | None = None
    source_lines: int = 0


# =============================================================================
# Response — Planner
# =============================================================================


class PlannedParameterResponse(BaseModel):
    name: str
    annotation: str | None = None
    kind: str


class ExecutionPlanResponse(BaseModel):
    module_name: str
    entry_function: str
    call_type: str
    parameters: list[PlannedParameterResponse] = []
    entry_class: str | None = None


# =============================================================================
# Response — Combined
# =============================================================================


class AnalyzeResponse(BaseModel):
    """Full pipeline response: analysis + execution plan."""

    success: bool = True
    module_info: ModuleInfoResponse
    execution_plan: ExecutionPlanResponse | None = None
    plan_error: str | None = None


class ErrorResponse(BaseModel):
    """Returned on failure."""

    success: bool = False
    error: str
    error_type: str
    detail: str | None = None
