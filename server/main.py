"""
main.py — FastAPI server entry point for Code Vision.

Run:
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI

from api.exceptions import register_exception_handlers
from api.middleware import configure_middleware
from api.routers import health, visualize


# =============================================================================
# App Setup
# =============================================================================

app = FastAPI(
    title="Code Vision API",
    description="Python source-code analysis and execution tracing API.",
    version="1.0.0",
)

# Apply Middleware (CORS)
configure_middleware(app)

# Apply Exception Handlers
register_exception_handlers(app)

# Include Routers
app.include_router(health.router)
app.include_router(visualize.router)
