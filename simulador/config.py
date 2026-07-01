"""Configuration loaded from environment (.env is git-ignored)."""
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
    """Build Settings from environment variables.

    When load_env is True, values are first loaded from a local .env file.
    Tests pass load_env=False so a developer's .env cannot leak into results.
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
    return Settings(
        database_url=database_url,
        tick_seconds=float(os.environ.get("TICK_SECONDS", "5")),
        seed=int(seed_raw) if seed_raw else None,
        p_anomaly=float(os.environ.get("P_ANOMALY", "0.005")),
        p_dropout=float(os.environ.get("P_DROPOUT", "0.002")),
    )
