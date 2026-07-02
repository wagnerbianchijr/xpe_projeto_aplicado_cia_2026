"""Funções de consulta somente leitura. Cada uma recebe um SupportsFetch e retorna models."""
from psycopg import sql

from aggregates import pick_aggregate, value_expr
from db import SupportsFetch
from models import (
    FailingSensor,
    KpiSummary,
    LineRecordCount,
    LivenessRow,
    SensorMeta,
    SensorStatusRow,
    TimeseriesPoint,
    ViolationRow,
)

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


_RECORD_COUNTS_SQL = """
SELECT
    pl.line_id
  , pl.name              AS line_name
  , count(r.*)           AS records
FROM production_line pl
LEFT JOIN sensor s        ON s.line_id = pl.line_id
LEFT JOIN sensor_reading r ON r.sensor_id = s.sensor_id
GROUP BY pl.line_id, pl.name
ORDER BY pl.line_id
"""


def kpis(db: SupportsFetch) -> KpiSummary:
    counts = db.fetch(_STATUS_COUNTS_SQL)[0]
    failed = db.fetch(_FAILED_COUNT_SQL)[0]
    totals = db.fetch(_LINES_AND_PRODUCTION_SQL)[0]
    record_rows = db.fetch(_RECORD_COUNTS_SQL)
    records_by_line = [
        LineRecordCount(
            line_id=r["line_id"], line_name=r["line_name"], count=r["records"]
        )
        for r in record_rows
    ]
    total_records = sum(rec.count for rec in records_by_line)
    return KpiSummary(
        ok=counts["ok"],
        alerta=counts["alerta"],
        sem_dados=counts["sem_dados"],
        failed=failed["failed"],
        lines=totals["lines"],
        production_today=float(totals["production_today"] or 0.0),
        total_records=total_records,
        records_by_line=records_by_line,
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
WHERE (%(line_id)s::int IS NULL OR ss.line_id = %(line_id)s::int)
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
  AND (%(line_id)s::int IS NULL OR sl.line_id = %(line_id)s::int)
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


_VIOLATIONS_SQL = """
SELECT
    bucket
  , sensor_id
  , line_id
  , metric
FROM sensor_out_of_range_1h
WHERE violated
  AND (%(line_id)s::int IS NULL OR line_id = %(line_id)s::int)
  AND bucket >= now() - %(window)s::interval
ORDER BY bucket DESC
"""


def timeseries(
    db: SupportsFetch, sensor_id: int, metric: str, window_seconds: int
) -> list[TimeseriesPoint]:
    view = pick_aggregate(window_seconds)
    query = sql.SQL(
        """
        SELECT
            bucket AS time
          , {value} AS value
        FROM {view}
        WHERE sensor_id = %(sensor_id)s
          AND bucket >= now() - %(window)s::interval
        ORDER BY bucket
        """
    ).format(value=value_expr(metric), view=sql.Identifier(view))
    rows = db.fetch(
        query, {"sensor_id": sensor_id, "window": f"{window_seconds} seconds"}
    )
    return [TimeseriesPoint(time=r["time"], value=r["value"]) for r in rows]


def violations(
    db: SupportsFetch, line_id: int | None, window_seconds: int
) -> list[ViolationRow]:
    rows = db.fetch(
        _VIOLATIONS_SQL,
        {"line_id": line_id, "window": f"{window_seconds} seconds"},
    )
    return [
        ViolationRow(
            bucket=r["bucket"],
            sensor_id=r["sensor_id"],
            line_id=r["line_id"],
            metric=r["metric"],
        )
        for r in rows
    ]


_SENSOR_META_SQL = """
SELECT
    sensor_id
  , line_id
  , metric
  , unit
  , min_limit
  , max_limit
  , description
FROM sensor
WHERE sensor_id = %(sensor_id)s
"""


def sensor_meta(db: SupportsFetch, sensor_id: int) -> SensorMeta | None:
    rows = db.fetch(_SENSOR_META_SQL, {"sensor_id": sensor_id})
    if not rows:
        return None
    r = rows[0]
    return SensorMeta(
        sensor_id=r["sensor_id"],
        line_id=r["line_id"],
        metric=r["metric"],
        unit=r["unit"],
        min_limit=r["min_limit"],
        max_limit=r["max_limit"],
        description=r["description"],
    )


_FAILING_SENSORS_SQL = """
SELECT
    sl.sensor_id
  , sl.line_id
  , pl.name AS line_name
  , sl.metric
FROM sensor_liveness sl
JOIN production_line pl ON pl.line_id = sl.line_id
WHERE sl.is_failed
ORDER BY sl.line_id, sl.sensor_id
"""


def failing_sensors(db: SupportsFetch) -> list[FailingSensor]:
    rows = db.fetch(_FAILING_SENSORS_SQL)
    return [
        FailingSensor(
            sensor_id=r["sensor_id"],
            line_id=r["line_id"],
            line_name=r["line_name"],
            metric=r["metric"],
        )
        for r in rows
    ]
