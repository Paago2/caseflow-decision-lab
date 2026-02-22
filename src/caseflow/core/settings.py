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
    rate_limit_enabled: bool = False
    rate_limit_rps: float = 5.0
    rate_limit_burst: int = 10
    rate_limit_scope: str = "ip"
    audit_sink: str = "log"
    audit_jsonl_path: str = "artifacts/events/decision_events.jsonl"
    provenance_dir: str = "artifacts/provenance"
    evidence_index_dir: str = "artifacts/evidence_index"
    evidence_min_score: float = 0.15
    evidence_max_citations: int = 3
    underwrite_engine: str = "graph"
    justifier_provider: str = "deterministic"
    trace_dir: str = "artifacts/traces"
    trace_enabled: bool = False
    underwrite_results_dir: str = "artifacts/underwrite_results"
    underwrite_persist_results: bool = False
    ocr_engine: str = "noop"
    postgres_dsn: str = "postgresql://caseflow:caseflow@postgres:5432/caseflow"
    redis_url: str = "redis://redis:6379/0"
    s3_endpoint_url: str = "http://minio:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_raw: str = "caseflow-raw"
    s3_bucket_artifacts: str = "caseflow-artifacts"


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

    if settings.app_env != "local":
        if not settings.s3_access_key.strip():
            raise ValueError(
                "S3_ACCESS_KEY must be set and non-empty when APP_ENV is not 'local'."
            )
        if not settings.s3_secret_key.strip():
            raise ValueError(
                "S3_SECRET_KEY must be set and non-empty when APP_ENV is not 'local'."
            )

    if not settings.model_registry_dir.strip():
        raise ValueError("MODEL_REGISTRY_DIR must be set and non-empty.")

    if not settings.active_model_id.strip():
        raise ValueError("ACTIVE_MODEL_ID must be set and non-empty.")

    if settings.rate_limit_rps < 0:
        raise ValueError("RATE_LIMIT_RPS must be >= 0.")

    if settings.rate_limit_burst < 0:
        raise ValueError("RATE_LIMIT_BURST must be >= 0.")

    if settings.rate_limit_scope != "ip":
        raise ValueError("RATE_LIMIT_SCOPE must be 'ip'.")

    if settings.audit_sink not in {"log", "jsonl"}:
        raise ValueError("AUDIT_SINK must be 'log' or 'jsonl'.")

    if settings.audit_sink == "jsonl" and not settings.audit_jsonl_path.strip():
        raise ValueError("AUDIT_JSONL_PATH must be set when AUDIT_SINK=jsonl.")

    if not settings.provenance_dir.strip():
        raise ValueError("PROVENANCE_DIR must be set and non-empty.")

    if not settings.evidence_index_dir.strip():
        raise ValueError("EVIDENCE_INDEX_DIR must be set and non-empty.")

    if settings.evidence_max_citations < 0:
        raise ValueError("EVIDENCE_MAX_CITATIONS must be >= 0.")

    if settings.underwrite_engine not in {"graph", "legacy"}:
        raise ValueError("UNDERWRITE_ENGINE must be one of: graph, legacy.")

    if settings.justifier_provider not in {"deterministic", "stub_llm"}:
        raise ValueError("JUSTIFIER_PROVIDER must be one of: deterministic, stub_llm.")

    if not settings.trace_dir.strip():
        raise ValueError("TRACE_DIR must be set and non-empty.")

    if not settings.underwrite_results_dir.strip():
        raise ValueError("UNDERWRITE_RESULTS_DIR must be set and non-empty.")

    if settings.ocr_engine not in {"noop", "tesseract"}:
        raise ValueError("OCR_ENGINE must be one of: noop, tesseract.")

    if not settings.postgres_dsn.strip():
        raise ValueError("POSTGRES_DSN must be set and non-empty.")

    if not settings.redis_url.strip():
        raise ValueError("REDIS_URL must be set and non-empty.")

    endpoint = settings.s3_endpoint_url.strip()
    if not endpoint:
        raise ValueError("S3_ENDPOINT_URL must be set and non-empty.")
    if not (endpoint.startswith("http://") or endpoint.startswith("https://")):
        raise ValueError("S3_ENDPOINT_URL must start with http:// or https://.")

    if not settings.s3_bucket_raw.strip():
        raise ValueError("S3_BUCKET_RAW must be set and non-empty.")

    if not settings.s3_bucket_artifacts.strip():
        raise ValueError("S3_BUCKET_ARTIFACTS must be set and non-empty.")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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
            rate_limit_enabled=_env_bool("RATE_LIMIT_ENABLED", False),
            rate_limit_rps=float(os.getenv("RATE_LIMIT_RPS", "5")),
            rate_limit_burst=int(os.getenv("RATE_LIMIT_BURST", "10")),
            rate_limit_scope=os.getenv("RATE_LIMIT_SCOPE", "ip"),
            audit_sink=os.getenv("AUDIT_SINK", "log"),
            audit_jsonl_path=os.getenv(
                "AUDIT_JSONL_PATH",
                "artifacts/events/decision_events.jsonl",
            ),
            provenance_dir=os.getenv("PROVENANCE_DIR", "artifacts/provenance"),
            evidence_index_dir=os.getenv(
                "EVIDENCE_INDEX_DIR", "artifacts/evidence_index"
            ),
            evidence_min_score=float(os.getenv("EVIDENCE_MIN_SCORE", "0.15")),
            evidence_max_citations=int(os.getenv("EVIDENCE_MAX_CITATIONS", "3")),
            underwrite_engine=os.getenv("UNDERWRITE_ENGINE", "graph"),
            justifier_provider=os.getenv("JUSTIFIER_PROVIDER", "deterministic"),
            trace_dir=os.getenv("TRACE_DIR", "artifacts/traces"),
            trace_enabled=_env_bool("TRACE_ENABLED", False),
            underwrite_results_dir=os.getenv(
                "UNDERWRITE_RESULTS_DIR", "artifacts/underwrite_results"
            ),
            underwrite_persist_results=_env_bool("UNDERWRITE_PERSIST_RESULTS", False),
            ocr_engine=os.getenv("OCR_ENGINE", "noop"),
            postgres_dsn=os.getenv(
                "POSTGRES_DSN",
                "postgresql://caseflow:caseflow@postgres:5432/caseflow",
            ),
            redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
            s3_endpoint_url=os.getenv("S3_ENDPOINT_URL", "http://minio:9000"),
            s3_access_key=os.getenv("S3_ACCESS_KEY", "minioadmin"),
            s3_secret_key=os.getenv("S3_SECRET_KEY", "minioadmin"),
            s3_bucket_raw=os.getenv("S3_BUCKET_RAW", "caseflow-raw"),
            s3_bucket_artifacts=os.getenv("S3_BUCKET_ARTIFACTS", "caseflow-artifacts"),
        )
        _validate_settings(candidate)
        _settings = candidate

    return _settings


def clear_settings_cache() -> None:
    global _settings
    _settings = None
