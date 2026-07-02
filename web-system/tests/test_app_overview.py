from fastapi.testclient import TestClient

from app import create_app
from db import FakeDatabase


def _kpi_responses():
    return [
        [{"ok": 25, "alerta": 3, "sem_dados": 2}],
        [{"failed": 1}],
        [{"lines": 3, "production_today": 1234.5}],
        [
            {"line_id": 1, "line_name": "Linha Sucos 01", "records": 500},
            {"line_id": 2, "line_name": "Linha Águas Saborizadas 01", "records": 300},
            {"line_id": 3, "line_name": "Linha Chás Gelados 01", "records": 200},
        ],
    ]


def test_overview_page_renders_nav_and_kpi_container():
    app = create_app(FakeDatabase(_kpi_responses()), refresh_seconds=7)
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    assert "Serra Clara" in body
    assert "/api/kpis" in body
    # KPIs refresh via the global refresh-tick event, not a hardcoded interval
    assert "refresh-tick from:body" in body
    # the refresh selector carries the configured default
    assert 'id="refresh-rate"' in body
    assert 'data-default="7"' in body


def test_kpis_partial_renders_counts():
    app = create_app(FakeDatabase(_kpi_responses()), refresh_seconds=5)
    client = TestClient(app)
    resp = client.get("/api/kpis")
    assert resp.status_code == 200
    assert "25" in resp.text
    assert "1234" in resp.text
    # total records (500+300+200 = 1000 -> "1.000") and per-line tiles
    assert "1.000" in resp.text
    assert "Registros no banco" in resp.text
    assert "Registros · Linha Sucos 01" in resp.text


def test_kpis_partial_shows_banner_when_db_down():
    class Broken:
        def fetch(self, *a, **k):
            raise RuntimeError("no db")

    app = create_app(Broken(), refresh_seconds=5)
    client = TestClient(app)
    resp = client.get("/api/kpis")
    assert resp.status_code == 200
    assert "sem conexão com o banco" in resp.text.lower()
