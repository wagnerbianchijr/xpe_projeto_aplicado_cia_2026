"""Persist generated readings to the sensor_reading hypertable."""

_INSERT_SQL = (
    "INSERT INTO sensor_reading (time, sensor_id, value, quality) "
    "VALUES (%s, %s, %s, %s)"
)


def insert_readings(conn, readings) -> int:
    """Insert a tick's readings in one transaction. Returns rows written."""
    if not readings:
        return 0
    rows = [(r.time, r.sensor_id, r.value, r.quality) for r in readings]
    with conn.cursor() as cur:
        cur.executemany(_INSERT_SQL, rows)
    conn.commit()
    return len(rows)
