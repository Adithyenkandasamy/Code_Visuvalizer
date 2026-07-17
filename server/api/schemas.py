"""
schemas.py — Pydantic models for the API layer.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VisualizeRequest(BaseModel):
    """Payload sent by the client to be visualized."""
    
    code: str = Field(
        ...,
        min_length=1,
        description="Raw Python source code to trace.",
        examples=["def add(a: int, b: int) -> int:\n    return a + b\nadd(2, 3)"],
    )


class TraceEventSchema(BaseModel):
    sequence: int
    event: str
    line: int
    function: str
    filename: str
    call_depth: int
    locals: dict[str, str]
    globals: dict[str, str] | None = None
    timestamp_ns: int | None = None
    return_value: str | None = None
    exception_info: str | None = None


class TraceFrameSchema(BaseModel):
    function_name: str
    call_depth: int
    events: list[TraceEventSchema]


class VisualizeResponse(BaseModel):
    """The JSON-safe response returned by the Engine Orchestrator."""
    
    events: list[TraceEventSchema]
    frames: list[TraceFrameSchema]
    output: str
    error: str | None
    total_events: int
    max_depth: int
    success: bool
