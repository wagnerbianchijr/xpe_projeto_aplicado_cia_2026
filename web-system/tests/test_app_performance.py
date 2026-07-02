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


def _db(meta_rows):
    return FakeByCall({
        "FROM sensor\nWHERE sensor_id": meta_rows,
        "sensor_reading_": [{"time": T, "value": 80.0}],
        "FROM sensor_status\n": [{"ok": 1, "alerta": 0, "sem_dados": 0}],
        "FROM sensor_liveness\n": [{"failed": 0}],
        "production_today": [{"lines": 3, "production_today": 0}],
    })


META = [{
    "sensor_id": 101, "line_id": 1, "metric": "temperature", "unit": "°C",
    "min_limit": 70.0, "max_limit": 95.0, "description": "Temp",
}]


def test_performance_page_renders():
    client = TestClient(create_app(_db(META)))
    resp = client.get("/performance")
    assert resp.status_code == 200
    assert "/static/charts.js" in resp.text


def test_timeseries_json_shape():
    client = TestClient(create_app(_db(META)))
    resp = client.get("/api/timeseries?sensor_id=101&window=3600")
    assert resp.status_code == 200
    data = resp.json()
    assert data["metric"] == "temperature"
    assert data["unit"] == "°C"
    assert data["limits"] == {"min": 70.0, "max": 95.0}
    assert data["points"][0]["value"] == 80.0
    assert data["points"][0]["time"].startswith("2026-07-01T12:00")


def test_timeseries_unknown_sensor_404():
    client = TestClient(create_app(_db([])))
    resp = client.get("/api/timeseries?sensor_id=999&window=3600")
    assert resp.status_code == 404
