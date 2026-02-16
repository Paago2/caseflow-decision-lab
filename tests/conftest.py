import pytest

from caseflow.core.settings import clear_settings_cache


@pytest.fixture(autouse=True)
def default_safe_test_env(monkeypatch):
    clear_settings_cache()
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("API_KEY", "test-key")

    yield

    clear_settings_cache()
