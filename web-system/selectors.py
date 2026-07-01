"""Pure selectors: window -> aggregate view, and metric -> value expression."""
from __future__ import annotations

import sys
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psycopg import sql

# Pre-import stdlib selectors to avoid shadowing it.
# Remove our module from sys.modules and sys.path to force importing the stdlib version.
_this_module = sys.modules.pop('selectors', None)
_cwd = os.path.dirname(os.path.abspath(__file__))
_orig_path = sys.path[:]
sys.path = [p for p in sys.path if os.path.abspath(p) != _cwd and p not in ('', '.')]

try:
    import selectors as _stdlib_selectors_cache
finally:
    sys.path = _orig_path
    if _this_module is not None:
        sys.modules['selectors'] = _this_module


def __getattr__(name: str):
    """Provide access to stdlib selectors attributes for subprocess and other modules."""
    try:
        return getattr(_stdlib_selectors_cache, name)
    except AttributeError:
        raise AttributeError(f"module 'selectors' has no attribute '{name}'")


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
    from psycopg import sql
    if metric == "production_count":
        return sql.SQL("max_value - min_value")
    return sql.SQL("sum_value / nullif(count_value, 0)")
