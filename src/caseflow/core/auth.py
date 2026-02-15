from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from caseflow.core.settings import get_settings

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    scheme_name="ApiKeyAuth",
)


def require_api_key(provided_api_key: str | None = Security(api_key_header)) -> None:
    settings = get_settings()

    if not provided_api_key or provided_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )
