from __future__ import annotations

import os
from dataclasses import dataclass

VALID_APP_ENVS = {"local", "dev", "stg", "prod"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "caseflow-decision-lab"
    app_env: str = "local"
    app_version: str = "0.1.0"
    git_sha: str = "unknown"
    build_time: str = "unknown"
    api_key: str = ""
    model_registry_dir: str = "models/registry"
    active_model_id: str = "baseline_v1"


_settings: Settings | None = None


def _validate_settings(settings: Settings) -> None:
    if settings.app_env not in VALID_APP_ENVS:
        allowed = ", ".join(sorted(VALID_APP_ENVS))
        raise ValueError(
            f"Invalid APP_ENV '{settings.app_env}'. Expected one of: {allowed}."
        )

    if settings.app_env != "local" and not settings.api_key.strip():
        raise ValueError(
            "API_KEY must be set and non-empty when APP_ENV is not 'local'."
        )

    if not settings.model_registry_dir.strip():
        raise ValueError("MODEL_REGISTRY_DIR must be set and non-empty.")

    if not settings.active_model_id.strip():
        raise ValueError("ACTIVE_MODEL_ID must be set and non-empty.")


def get_settings() -> Settings:
    global _settings

    if _settings is None:
        candidate = Settings(
            app_name=os.getenv("APP_NAME", "caseflow-decision-lab"),
            app_env=os.getenv("APP_ENV", "local"),
            app_version=os.getenv("APP_VERSION", "0.1.0"),
            git_sha=os.getenv("GIT_SHA", "unknown"),
            build_time=os.getenv("BUILD_TIME", "unknown"),
            api_key=os.getenv("API_KEY", ""),
            model_registry_dir=os.getenv("MODEL_REGISTRY_DIR", "models/registry"),
            active_model_id=os.getenv("ACTIVE_MODEL_ID", "baseline_v1"),
        )
        _validate_settings(candidate)
        _settings = candidate

    return _settings


def clear_settings_cache() -> None:
    global _settings
    _settings = None
