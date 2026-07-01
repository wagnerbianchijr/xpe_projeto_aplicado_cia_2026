"""Read-only query functions. Each takes a SupportsFetch and returns models."""
from db import SupportsFetch
from models import KpiSummary, LivenessRow, SensorStatusRow

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


_SENSOR_STATUS_SQL = """
SELECT
    ss.sensor_id
  , ss.line_id
  , pl.name AS line_name
  , ss.metric
  , ss.unit
  , ss.value
  , ss.last_time
  , ss.status
FROM sensor_status ss
JOIN production_line pl ON pl.line_id = ss.line_id
WHERE (%(line_id)s IS NULL OR ss.line_id = %(line_id)s)
ORDER BY ss.line_id, ss.sensor_id
"""

_FAILED_SENSORS_SQL = """
SELECT
    sl.sensor_id
  , sl.line_id
  , sl.metric
  , sl.last_time
  , sl.seconds_since_last
  , sl.is_failed
FROM sensor_liveness sl
WHERE sl.is_failed
  AND (%(line_id)s IS NULL OR sl.line_id = %(line_id)s)
ORDER BY sl.line_id, sl.sensor_id
"""


def sensor_status(db: SupportsFetch, line_id: int | None = None) -> list[SensorStatusRow]:
    rows = db.fetch(_SENSOR_STATUS_SQL, {"line_id": line_id})
    return [
        SensorStatusRow(
            sensor_id=r["sensor_id"],
            line_id=r["line_id"],
            line_name=r["line_name"],
            metric=r["metric"],
            unit=r["unit"],
            value=r["value"],
            last_time=r["last_time"],
            status=r["status"],
        )
        for r in rows
    ]


def failed_sensors(db: SupportsFetch, line_id: int | None = None) -> list[LivenessRow]:
    rows = db.fetch(_FAILED_SENSORS_SQL, {"line_id": line_id})
    return [
        LivenessRow(
            sensor_id=r["sensor_id"],
            line_id=r["line_id"],
            metric=r["metric"],
            last_time=r["last_time"],
            seconds_since_last=r["seconds_since_last"],
            is_failed=r["is_failed"],
        )
        for r in rows
    ]
