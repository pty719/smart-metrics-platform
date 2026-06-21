"""API Key authentication dependency.

All protected endpoints should declare ``api_key: str = Depends(verify_api_key)``.
"""
from __future__ import annotations

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

security = HTTPBearer()


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    """Verify the Bearer token from the Authorization header.

    Args:
        credentials: HTTP Bearer credentials extracted from the request.

    Returns:
        The validated API key string.

    Raises:
        HTTPException: 401 if the API key is invalid or missing.
    """
    api_key = credentials.credentials
    if api_key != settings.API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return api_key
