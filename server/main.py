"""
main.py — FastAPI server for Code Vision.

Exposes the Analyzer → Planner pipeline as a REST API.
The server never executes user code; it only analyses structure
and builds execution plans.

Run:
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from analyzer import CodeAnalyzer
from analyzer import AnalyzerError

from engine.planner import ExecutionPlanner, PlannerError

from converters import convert_execution_plan, convert_module
from schemas import AnalyzeRequest, AnalyzeResponse, ErrorResponse


# =============================================================================
# App Setup
# =============================================================================

app = FastAPI(
    title="Code Vision API",
    description=(
        "Static Python source-code analysis and execution planning. "
        "No user code is ever executed."
    ),
    version="0.1.0",
)

# Allow the React / Vite frontend (dev) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Exception Handlers
# =============================================================================


@app.exception_handler(AnalyzerError)
async def analyzer_error_handler(_request, exc: AnalyzerError) -> JSONResponse:
    """Map analyzer errors to 422 responses."""
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error=str(exc),
            error_type=type(exc).__name__,
        ).model_dump(),
    )


@app.exception_handler(PlannerError)
async def planner_error_handler(_request, exc: PlannerError) -> JSONResponse:
    """Map planner errors to 422 responses."""
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error=str(exc),
            error_type=type(exc).__name__,
        ).model_dump(),
    )


# =============================================================================
# Endpoints
# =============================================================================


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok", "service": "code-vision"}


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Full pipeline: Analyze source code → build execution plan.

    Returns both the structural analysis (ModuleInfo) and the
    execution plan.  If planning fails (e.g. no entry point),
    the plan field is null and plan_error explains why.
    """
    # Stage 1 — Analyze (raises on syntax / empty errors).
    module_info = CodeAnalyzer(request.source_code).analyze()
    module_response = convert_module(module_info)

    # Stage 2 — Plan (best-effort; failure is non-fatal).
    plan_response = None
    plan_error = None
    try:
        plan = ExecutionPlanner.create(
            module_info,
            module_name=request.module_name,
        )
        plan_response = convert_execution_plan(plan)
    except PlannerError as exc:
        plan_error = str(exc)

    return AnalyzeResponse(
        success=True,
        module_info=module_response,
        execution_plan=plan_response,
        plan_error=plan_error,
    )


@app.post("/api/analyze/module", response_model=dict)
async def analyze_module_only(request: AnalyzeRequest) -> dict:
    """Return only the structural analysis (no execution plan)."""
    module_info = CodeAnalyzer(request.source_code).analyze()
    return convert_module(module_info).model_dump()


@app.post("/api/analyze/plan", response_model=dict)
async def analyze_plan_only(request: AnalyzeRequest) -> dict:
    """Return only the execution plan."""
    module_info = CodeAnalyzer(request.source_code).analyze()
    plan = ExecutionPlanner.create(
        module_info,
        module_name=request.module_name,
    )
    return convert_execution_plan(plan).model_dump()
