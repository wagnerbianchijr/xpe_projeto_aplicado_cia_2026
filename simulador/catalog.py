"""Carrega o catálogo de sensores (tabela dimensão) do banco."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SensorSpec:
    sensor_id: int
    line_id: int
    metric: str
    min_limit: float | None
    max_limit: float | None


def load_catalog(conn) -> list[SensorSpec]:
    """Lê identidade e limites operacionais de cada sensor, ordenados por id."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT sensor_id, line_id, metric, min_limit, max_limit "
            "FROM sensor ORDER BY sensor_id"
        )
        return [SensorSpec(*row) for row in cur.fetchall()]
