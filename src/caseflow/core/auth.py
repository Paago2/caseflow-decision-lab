from fastapi import HTTPException, Request, status

from caseflow.core.settings import get_settings


def require_api_key(request: Request) -> None:
    settings = get_settings()
    provided_api_key = request.headers.get("X-API-Key")

    if not provided_api_key or provided_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )
