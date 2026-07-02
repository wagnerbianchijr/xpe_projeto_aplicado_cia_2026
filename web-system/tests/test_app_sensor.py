from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app import create_app

T = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)


class FakeByCall:
    def __init__(self, mapping):
        self.mapping = mapping

    def fetch(self, query, params=None):
        text = query if isinstance(query, str) else query.as_string(None)
        for needle, rows in self.mapping.items():
            if needle in text:
                return rows
        raise AssertionError(f"unexpected query: {text}")


META = [{
    "sensor_id": 101, "line_id": 1, "metric": "temperature", "unit": "°C",
    "min_limit": 70.0, "max_limit": 95.0, "description": "Temperatura",
}]


def _db(meta_rows):
    return FakeByCall({
        "FROM sensor\nWHERE sensor_id": meta_rows,
        "FROM sensor_out_of_range_1h": [{"bucket": T, "sensor_id": 101, "line_id": 1, "metric": "temperature"}],
        "FROM sensor_status\n": [{"ok": 1, "alerta": 0, "sem_dados": 0}],
        "FROM sensor_liveness\n": [{"failed": 0}],
        "production_today": [{"lines": 3, "production_today": 0}],
    })


def test_sensor_detail_renders_meta_and_chart():
    client = TestClient(create_app(_db(META)))
    resp = client.get("/sensor/101")
    assert resp.status_code == 200
    body = resp.text
    assert "temperature" in body
    assert "70" in body and "95" in body      # limits shown
    assert "/api/timeseries?sensor_id=101" in body


def test_sensor_detail_unknown_404():
    client = TestClient(create_app(_db([])))
    resp = client.get("/sensor/999")
    assert resp.status_code == 404


def test_sensor_detail_shows_banner_when_db_down():
    class Broken:
        def fetch(self, *a, **k):
            raise RuntimeError("no db")

    client = TestClient(create_app(Broken()))
    resp = client.get("/sensor/101")
    assert resp.status_code == 200
    assert "sem conexão com o banco" in resp.text.lower()
