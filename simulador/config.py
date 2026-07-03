"""Configuração carregada do ambiente (.env é git-ignored)."""
from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_url: str
    tick_seconds: float
    seed: int | None
    p_anomaly: float
    p_dropout: float


def load_settings(load_env: bool = True) -> Settings:
    """Monta Settings a partir das variáveis de ambiente.

    Quando load_env é True, os valores são primeiro carregados de um .env local.
    Os testes passam load_env=False para que o .env do dev não vaze nos resultados.
    """
    if load_env:
        load_dotenv()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required. Copy simulador/.env.example to "
            "simulador/.env and set it."
        )

    seed_raw = os.environ.get("SEED")
    tick_seconds = float(os.environ.get("TICK_SECONDS", "5"))
    if tick_seconds <= 0:
        raise ValueError(f"TICK_SECONDS must be > 0, got {tick_seconds}")

    return Settings(
        database_url=database_url,
        tick_seconds=tick_seconds,
        seed=int(seed_raw) if seed_raw else None,
        p_anomaly=_probability("P_ANOMALY", "0.005"),
        p_dropout=_probability("P_DROPOUT", "0.002"),
    )


def _probability(name: str, default: str) -> float:
    """Lê uma variável de ambiente como probabilidade em [0, 1]; rejeita o resto."""
    value = float(os.environ.get(name, default))
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be a probability in [0, 1], got {value}")
    return value
