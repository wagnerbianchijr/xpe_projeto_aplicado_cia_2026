"""Read-only query functions. Each takes a SupportsFetch and returns models."""
from db import SupportsFetch
from models import KpiSummary

_STATUS_COUNTS_SQL = """
SELECT
    count(*) FILTER (WHERE status = 'normal')    AS ok
  , count(*) FILTER (WHERE status = 'alerta')    AS alerta
  , count(*) FILTER (WHERE status = 'sem_dados') AS sem_dados
FROM sensor_status
"""

_FAILED_COUNT_SQL = """
SELECT
    count(*) FILTER (WHERE is_failed) AS failed
FROM sensor_liveness
"""

_LINES_AND_PRODUCTION_SQL = """
SELECT
    (SELECT count(*) FROM production_line) AS lines
  , coalesce((
        SELECT sum(daily.throughput)
        FROM (
            SELECT
                max(r.value) - min(r.value) AS throughput
            FROM sensor_reading r
            JOIN sensor s ON s.sensor_id = r.sensor_id
            WHERE s.metric = 'production_count'
              AND r.time >= date_trunc('day', now())
            GROUP BY r.sensor_id
        ) daily
    ), 0) AS production_today
"""


def kpis(db: SupportsFetch) -> KpiSummary:
    counts = db.fetch(_STATUS_COUNTS_SQL)[0]
    failed = db.fetch(_FAILED_COUNT_SQL)[0]
    totals = db.fetch(_LINES_AND_PRODUCTION_SQL)[0]
    return KpiSummary(
        ok=counts["ok"],
        alerta=counts["alerta"],
        sem_dados=counts["sem_dados"],
        failed=failed["failed"],
        lines=totals["lines"],
        production_today=float(totals["production_today"] or 0.0),
    )
