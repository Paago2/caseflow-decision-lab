from caseflow.core.settings import clear_settings_cache, get_settings


def test_get_settings_dev_with_api_key_is_valid(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("API_KEY", "dev-secret")
    clear_settings_cache()

    settings = get_settings()

    assert settings.app_env == "dev"
    assert settings.api_key == "dev-secret"


def test_get_settings_rejects_invalid_app_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "banana")
    monkeypatch.setenv("API_KEY", "some-key")
    clear_settings_cache()

    try:
        get_settings()
        assert False, "Expected ValueError for invalid APP_ENV"
    except ValueError as exc:
        assert "Invalid APP_ENV" in str(exc)


def test_get_settings_rejects_missing_api_key_in_prod(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("API_KEY", raising=False)
    clear_settings_cache()

    try:
        get_settings()
        assert False, "Expected ValueError when API_KEY is missing in prod"
    except ValueError as exc:
        assert "API_KEY must be set and non-empty" in str(exc)


def test_get_settings_allows_missing_api_key_in_local(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.delenv("API_KEY", raising=False)
    clear_settings_cache()

    settings = get_settings()

    assert settings.app_env == "local"
    assert settings.api_key == ""


def test_get_settings_uses_default_model_registry_values(monkeypatch) -> None:
    monkeypatch.delenv("MODEL_REGISTRY_DIR", raising=False)
    monkeypatch.delenv("ACTIVE_MODEL_ID", raising=False)
    clear_settings_cache()

    settings = get_settings()

    assert settings.model_registry_dir == "models/registry"
    assert settings.active_model_id == "baseline_v1"


def test_get_settings_allows_overridden_model_registry_values(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_REGISTRY_DIR", "/tmp/custom-models")
    monkeypatch.setenv("ACTIVE_MODEL_ID", "baseline_v2")
    clear_settings_cache()

    settings = get_settings()

    assert settings.model_registry_dir == "/tmp/custom-models"
    assert settings.active_model_id == "baseline_v2"


def test_get_settings_rejects_empty_model_registry_dir(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_REGISTRY_DIR", "")
    clear_settings_cache()

    try:
        get_settings()
        assert False, "Expected ValueError when MODEL_REGISTRY_DIR is empty"
    except ValueError as exc:
        assert "MODEL_REGISTRY_DIR must be set and non-empty" in str(exc)


def test_get_settings_rejects_empty_active_model_id(monkeypatch) -> None:
    monkeypatch.setenv("ACTIVE_MODEL_ID", "")
    clear_settings_cache()

    try:
        get_settings()
        assert False, "Expected ValueError when ACTIVE_MODEL_ID is empty"
    except ValueError as exc:
        assert "ACTIVE_MODEL_ID must be set and non-empty" in str(exc)


def test_get_settings_reads_infra_env_vars(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://user:pass@postgres:5432/customdb")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/9")
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://minio:9000")
    monkeypatch.setenv("S3_ACCESS_KEY", "custom-key")
    monkeypatch.setenv("S3_SECRET_KEY", "custom-secret")
    monkeypatch.setenv("S3_BUCKET_RAW", "my-raw")
    monkeypatch.setenv("S3_BUCKET_ARTIFACTS", "my-artifacts")
    clear_settings_cache()

    settings = get_settings()

    assert settings.postgres_dsn == "postgresql://user:pass@postgres:5432/customdb"
    assert settings.redis_url == "redis://redis:6379/9"
    assert settings.s3_endpoint_url == "http://minio:9000"
    assert settings.s3_access_key == "custom-key"
    assert settings.s3_secret_key == "custom-secret"
    assert settings.s3_bucket_raw == "my-raw"
    assert settings.s3_bucket_artifacts == "my-artifacts"


def test_get_settings_rejects_empty_s3_bucket_names(monkeypatch) -> None:
    monkeypatch.setenv("S3_BUCKET_RAW", "")
    clear_settings_cache()

    try:
        get_settings()
        assert False, "Expected ValueError when S3_BUCKET_RAW is empty"
    except ValueError as exc:
        assert "S3_BUCKET_RAW must be set and non-empty" in str(exc)

    monkeypatch.setenv("S3_BUCKET_RAW", "caseflow-raw")
    monkeypatch.setenv("S3_BUCKET_ARTIFACTS", "")
    clear_settings_cache()

    try:
        get_settings()
        assert False, "Expected ValueError when S3_BUCKET_ARTIFACTS is empty"
    except ValueError as exc:
        assert "S3_BUCKET_ARTIFACTS must be set and non-empty" in str(exc)


def test_get_settings_rejects_invalid_s3_endpoint_url(monkeypatch) -> None:
    monkeypatch.setenv("S3_ENDPOINT_URL", "minio:9000")
    clear_settings_cache()

    try:
        get_settings()
        assert False, "Expected ValueError for invalid S3_ENDPOINT_URL"
    except ValueError as exc:
        assert "S3_ENDPOINT_URL must start with http:// or https://" in str(exc)


def test_get_settings_rejects_missing_s3_creds_outside_local(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("API_KEY", "prod-secret")
    monkeypatch.setenv("S3_ACCESS_KEY", "")
    monkeypatch.setenv("S3_SECRET_KEY", "")
    clear_settings_cache()

    try:
        get_settings()
        assert False, "Expected ValueError when S3 creds are missing in prod"
    except ValueError as exc:
        assert "S3_ACCESS_KEY must be set and non-empty" in str(exc)
