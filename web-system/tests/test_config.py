import pytest

from config import Settings, load_settings


def test_load_settings_reads_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    monkeypatch.setenv("REFRESH_SECONDS", "10")
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "9000")
    s = load_settings(load_env=False)
    assert s == Settings(
        database_url="postgresql://u:p@h:5432/db",
        refresh_seconds=10,
        host="0.0.0.0",
        port=9000,
    )


def test_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    monkeypatch.delenv("REFRESH_SECONDS", raising=False)
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    s = load_settings(load_env=False)
    assert s.refresh_seconds == 5
    assert s.host == "127.0.0.1"
    assert s.port == 8000


def test_missing_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        load_settings(load_env=False)


def test_refresh_must_be_positive(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    monkeypatch.setenv("REFRESH_SECONDS", "0")
    with pytest.raises(ValueError):
        load_settings(load_env=False)
