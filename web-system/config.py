"""Configuração carregada do ambiente (.env é ignorado pelo git)."""
from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_url: str
    refresh_seconds: int
    host: str
    port: int


def load_settings(load_env: bool = True) -> Settings:
    """Constrói Settings a partir de variáveis de ambiente.

    Quando load_env é True, os valores são primeiro carregados de um arquivo .env local.
    Os testes passam load_env=False para que o .env de um desenvolvedor não vaze para os resultados.
    """
    if load_env:
        load_dotenv()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required. Copy web-system/.env.example to "
            "web-system/.env and set it."
        )

    refresh_seconds = int(os.environ.get("REFRESH_SECONDS", "5"))
    if refresh_seconds <= 0:
        raise ValueError(f"REFRESH_SECONDS must be > 0, got {refresh_seconds}")

    return Settings(
        database_url=database_url,
        refresh_seconds=refresh_seconds,
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
    )
