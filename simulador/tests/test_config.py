import pytest

from config import load_settings


def test_load_settings_reads_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("TICK_SECONDS", "5")
    monkeypatch.setenv("P_ANOMALY", "0.01")
    monkeypatch.setenv("P_DROPOUT", "0.02")
    monkeypatch.setenv("SEED", "42")

    settings = load_settings(load_env=False)

    assert settings.database_url == "postgresql://x"
    assert settings.tick_seconds == 5.0
    assert settings.p_anomaly == 0.01
    assert settings.p_dropout == 0.02
    assert settings.seed == 42


def test_defaults_applied(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.delenv("TICK_SECONDS", raising=False)
    monkeypatch.delenv("P_ANOMALY", raising=False)
    monkeypatch.delenv("P_DROPOUT", raising=False)
    monkeypatch.delenv("SEED", raising=False)

    settings = load_settings(load_env=False)

    assert settings.tick_seconds == 5.0
    assert settings.p_anomaly == 0.005
    assert settings.p_dropout == 0.002
    assert settings.seed is None


def test_missing_database_url_raises(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        load_settings(load_env=False)
