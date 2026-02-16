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