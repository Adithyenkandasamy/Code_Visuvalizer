"""
visualize.py — The primary API endpoint for executing Code Vision.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import get_engine
from api.schemas import VisualizeRequest, VisualizeResponse
from engine.orchestrator import CodeVisionEngine

router = APIRouter(prefix="/api/v1", tags=["Visualize"])


@router.post(
    "/visualize",
    response_model=VisualizeResponse,
    summary="Visualize Python Code Execution",
)
async def visualize_code(
    request: VisualizeRequest,
    engine: CodeVisionEngine = Depends(get_engine),
) -> dict:
    """
    Submit Python source code to the Code Vision engine.

    The API delegates the entire pipeline (analysis, planning, wrapper 
    generation, runtime tracing, and serialization) to the injected 
    CodeVisionEngine orchestrator.
    """
    # The orchestrator returns a raw dict that FastAPI/Pydantic
    # validates and serializes against the VisualizeResponse schema.
    return engine.visualize(request.code)
