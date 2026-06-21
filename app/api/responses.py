"""Standardized response helpers.

Every endpoint should return one of these two shapes:

Success::

    {"code": 0, "message": "success", "data": {...}}

Error (via JSONResponse)::

    {"code": 404, "message": "指标 'x' 不存在", "detail": null}
"""
from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


def success_response(data: Any, message: str = "success") -> dict[str, Any]:
    """Build a standardized success response body.

    Args:
        data: The payload to include.
        message: Human-readable success message.

    Returns:
        Dict ready to be returned from a FastAPI endpoint.
    """
    return {"code": 0, "message": message, "data": data}


def error_response(code: int, message: str, detail: Any = None) -> JSONResponse:
    """Build a standardized error JSONResponse.

    Args:
        code: HTTP status code.
        message: Human-readable error description.
        detail: Optional extra context (e.g. validation errors).

    Returns:
        JSONResponse with the standardized error body.
    """
    return JSONResponse(
        status_code=code,
        content={"code": code, "message": message, "detail": detail},
    )
