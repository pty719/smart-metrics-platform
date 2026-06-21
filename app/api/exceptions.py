"""Global FastAPI exception handlers.

Register these handlers on the ``app`` instance so that all ``AppException``
subclasses are automatically converted to the project's standard error JSON.
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppException


async def app_exception_handler(
    request: Request,
    exc: AppException,
) -> JSONResponse:
    """Convert an ``AppException`` to a standardized JSON error response.

    Args:
        request: The incoming HTTP request (required by FastAPI handler signature).
        exc: The caught ``AppException`` instance.

    Returns:
        JSONResponse with ``{"code": ..., "message": ..., "detail": null}``.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.message,
            "detail": None,
        },
    )
