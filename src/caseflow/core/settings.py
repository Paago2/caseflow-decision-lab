from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str = "local"
    api_key: str = ""


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings

    if _settings is None:
        _settings = Settings(
            app_env=os.getenv("APP_ENV", "local"),
            api_key=os.getenv("API_KEY", ""),
        )

    return _settings


def clear_settings_cache() -> None:
    global _settings
    _settings = None
