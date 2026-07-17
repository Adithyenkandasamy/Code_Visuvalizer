"""
health.py — Liveness and version probes.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Basic liveness probe."""
    return {"status": "ok", "service": "code-vision"}


@router.get("/version")
async def version_check() -> dict[str, str]:
    """Returns the current API version."""
    return {"version": "1.0.0"}
