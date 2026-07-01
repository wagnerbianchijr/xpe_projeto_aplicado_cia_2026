from datetime import datetime, timezone

from generator import Reading
from writer import insert_readings

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


class _FakeCursor:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def executemany(self, sql, rows):
        self.calls.append((sql, rows))


class _FakeConn:
    def __init__(self):
        self.cur = _FakeCursor()
        self.committed = False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True


def test_insert_readings_batches_rows_and_commits():
    conn = _FakeConn()
    readings = [Reading(T0, 101, 85.0, 0), Reading(T0, 102, 5.0, 0)]

    n = insert_readings(conn, readings)

    assert n == 2
    assert conn.committed is True
    sql, rows = conn.cur.calls[0]
    assert "INSERT INTO sensor_reading" in sql
    assert rows == [(T0, 101, 85.0, 0), (T0, 102, 5.0, 0)]


def test_insert_readings_empty_is_noop():
    conn = _FakeConn()
    n = insert_readings(conn, [])
    assert n == 0
    assert conn.committed is False
    assert conn.cur.calls == []
