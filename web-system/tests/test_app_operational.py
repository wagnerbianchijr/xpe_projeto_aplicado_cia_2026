from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app import create_app

T = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)


class FakeByCall:
    """Retorna respostas indexadas por substring do SQL, então a ordem das rotas é irrelevante."""

    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def fetch(self, query, params=None):
        text = query if isinstance(query, str) else query.as_string(None)
        self.calls.append((text, params))
        for needle, rows in self.mapping.items():
            if needle in text:
                return rows
        raise AssertionError(f"unexpected query: {text}")


def _db():
    return FakeByCall({
        "FROM sensor_status ss": [{
            "sensor_id": 101, "line_id": 1, "line_name": "Linha Sucos 01",
            "metric": "temperature", "unit": "°C", "value": 80.0,
            "last_time": T, "status": "normal",
        }],
        "FROM sensor_liveness sl": [{
            "sensor_id": 205, "line_id": 2, "metric": "line_speed",
            "last_time": None, "seconds_since_last": None, "is_failed": True,
        }],
        # Consultas do cabeçalho de KPI (o layout base as dispara ao carregar):
        "FROM sensor_status\n": [{"ok": 1, "alerta": 0, "sem_dados": 0}],
        "FROM sensor_liveness\n": [{"failed": 1}],
        "production_today": [{"lines": 3, "production_today": 0}],
    })


def test_operational_page_has_line_filter_and_table_container():
    client = TestClient(create_app(_db()))
    resp = client.get("/operational")
    assert resp.status_code == 200
    assert "/api/operational" in resp.text
    assert "line_id" in resp.text


def test_operational_table_partial_lists_status_and_failed():
    client = TestClient(create_app(_db()))
    resp = client.get("/api/operational")
    assert resp.status_code == 200
    body = resp.text
    assert "temperature" in body
    assert "normal" in body
    assert "line_speed" in body  # sensor com falha listado


def test_operational_table_shows_banner_when_db_down():
    class Broken:
        def fetch(self, *a, **k):
            raise RuntimeError("no db")

    client = TestClient(create_app(Broken()))
    resp = client.get("/api/operational")
    assert resp.status_code == 200
    assert "sem conexão com o banco" in resp.text.lower()


def test_operational_malformed_line_id_does_not_500():
    client = TestClient(create_app(_db()))
    resp = client.get("/api/operational?line_id=abc")
    assert resp.status_code == 200
