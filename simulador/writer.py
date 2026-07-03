"""Persiste as leituras geradas na hypertable sensor_reading."""

_INSERT_SQL = (
    "INSERT INTO sensor_reading (time, sensor_id, value, quality) "
    "VALUES (%s, %s, %s, %s)"
)


def insert_readings(conn, readings) -> int:
    """Insere as leituras de um tick numa transação. Retorna as linhas gravadas."""
    if not readings:
        return 0
    rows = [(r.time, r.sensor_id, r.value, r.quality) for r in readings]
    with conn.cursor() as cur:
        cur.executemany(_INSERT_SQL, rows)
    conn.commit()
    return len(rows)
