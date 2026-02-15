from fastapi import APIRouter

from caseflow.core.settings import get_settings

router = APIRouter()


@router.get("/version")
def version() -> dict[str, str]:
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "version": settings.app_version,
        "git_sha": settings.git_sha,
        "build_time": settings.build_time,
    }