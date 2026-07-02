from fastapi.testclient import TestClient

from app import create_app
from db import FakeDatabase
from models import FailingSensor
from queries import failing_sensors


def test_failing_sensors_maps_rows():
    fake = FakeDatabase([[
        {"sensor_id": 205, "line_id": 2, "line_name": "Linha Águas Saborizadas 01",
         "metric": "line_speed"},
    ]])
    rows = failing_sensors(fake)
    assert rows == [FailingSensor(205, 2, "Linha Águas Saborizadas 01", "line_speed")]


def test_alerts_partial_lists_failures_with_line_and_badge():
    db = FakeDatabase([[
        {"sensor_id": 205, "line_id": 2, "line_name": "Linha Águas Saborizadas 01",
         "metric": "line_speed"},
    ]])
    client = TestClient(create_app(db))
    resp = client.get("/api/alerts")
    assert resp.status_code == 200
    body = resp.text
    assert 'class="badge"' in body                       # alert badge shown
    assert "has-alerts" in body                          # bell flagged
    assert "Sensor 205 (line_speed) da Linha Águas Saborizadas 01 está com falha." in body


def test_alerts_partial_empty_when_no_failures():
    db = FakeDatabase([[]])
    client = TestClient(create_app(db))
    resp = client.get("/api/alerts")
    assert resp.status_code == 200
    assert "Nenhum sensor com falha." in resp.text
    assert 'class="badge"' not in resp.text


def test_alerts_partial_banner_when_db_down():
    class Broken:
        def fetch(self, *a, **k):
            raise RuntimeError("no db")

    client = TestClient(create_app(Broken()))
    resp = client.get("/api/alerts")
    assert resp.status_code == 200
    assert "Sem conexão com o banco." in resp.text
