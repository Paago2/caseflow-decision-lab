from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "caseflow-decision-lab"
    app_env: str = "local"
    app_version: str = "0.1.0"
    git_sha: str = "unknown"
    build_time: str = "unknown"
    api_key: str = ""


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings

    if _settings is None:
        _settings = Settings(
            app_name=os.getenv("APP_NAME", "caseflow-decision-lab"),
            app_env=os.getenv("APP_ENV", "local"),
            app_version=os.getenv("APP_VERSION", "0.1.0"),
            git_sha=os.getenv("GIT_SHA", "unknown"),
            build_time=os.getenv("BUILD_TIME", "unknown"),
            api_key=os.getenv("API_KEY", ""),
        )

    return _settings


def clear_settings_cache() -> None:
    global _settings
    _settings = None
