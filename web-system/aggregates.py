"""Pure selectors: window -> aggregate view, and metric -> value expression."""
from psycopg import sql


def pick_aggregate(window_seconds: int) -> str:
    """Choose the coarsest aggregate that still covers the window well."""
    if window_seconds <= 3600:
        return "sensor_reading_1m"
    if window_seconds <= 6 * 3600:
        return "sensor_reading_15m"
    if window_seconds <= 24 * 3600:
        return "sensor_reading_30m"
    return "sensor_reading_1h"


def value_expr(metric: str) -> sql.Composable:
    """Value column for a metric: throughput for counters, average otherwise."""
    if metric == "production_count":
        return sql.SQL("max_value - min_value")
    return sql.SQL("sum_value / nullif(count_value, 0)")
