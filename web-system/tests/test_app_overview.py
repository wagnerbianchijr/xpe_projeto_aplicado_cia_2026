from fastapi.testclient import TestClient

from app import create_app
from db import FakeDatabase


def _kpi_responses():
    return [
        [{"ok": 25, "alerta": 3, "sem_dados": 2}],
        [{"failed": 1}],
        [{"lines": 3, "production_today": 1234.5}],
    ]


def test_overview_page_renders_nav_and_kpi_container():
    app = create_app(FakeDatabase(_kpi_responses()), refresh_seconds=7)
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    assert "Serra Clara" in body
    assert "/api/kpis" in body
    assert "every 7s" in body


def test_kpis_partial_renders_counts():
    app = create_app(FakeDatabase(_kpi_responses()), refresh_seconds=5)
    client = TestClient(app)
    resp = client.get("/api/kpis")
    assert resp.status_code == 200
    assert "25" in resp.text
    assert "1234" in resp.text


def test_kpis_partial_shows_banner_when_db_down():
    class Broken:
        def fetch(self, *a, **k):
            raise RuntimeError("no db")

    app = create_app(Broken(), refresh_seconds=5)
    client = TestClient(app)
    resp = client.get("/api/kpis")
    assert resp.status_code == 200
    assert "sem conexão com o banco" in resp.text.lower()
