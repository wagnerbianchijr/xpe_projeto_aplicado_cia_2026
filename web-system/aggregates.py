"""Seletores puros: janela -> view agregada, e métrica -> expressão de valor."""
from psycopg import sql


def pick_aggregate(window_seconds: int) -> str:
    """Escolhe a agregação mais grossa que ainda cobre bem a janela."""
    if window_seconds <= 3600:
        return "sensor_reading_1m"
    if window_seconds <= 6 * 3600:
        return "sensor_reading_15m"
    if window_seconds <= 24 * 3600:
        return "sensor_reading_30m"
    return "sensor_reading_1h"


def value_expr(metric: str) -> sql.Composable:
    """Coluna de valor para uma métrica: vazão para contadores, média nos demais casos."""
    if metric == "production_count":
        return sql.SQL("max_value - min_value")
    return sql.SQL("sum_value / nullif(count_value, 0)")
