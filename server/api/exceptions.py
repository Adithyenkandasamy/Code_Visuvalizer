"""
exceptions.py — API exception handlers.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from engine.orchestrator import EngineError


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register global exception handlers for the FastAPI application.
    """

    @app.exception_handler(EngineError)
    async def engine_error_handler(_request: Request, exc: EngineError) -> JSONResponse:
        """Map internal EngineError failures to HTTP 422 Unprocessable Entity."""
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": str(exc),
                "error_type": "EngineError",
                "stage": exc.stage,
            },
        )
