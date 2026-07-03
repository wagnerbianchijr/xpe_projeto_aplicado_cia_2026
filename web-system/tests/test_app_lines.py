from fastapi.testclient import TestClient

from app import create_app
from db import FakeDatabase
from models import LineOverview
from queries import line_overview


def _rows():
    return [
        {"line_id": 1, "line_name": "Linha Sucos 01", "ok": 10, "alerta": 0, "sem_dados": 0, "failed": 0},
        {"line_id": 2, "line_name": "Linha Águas Saborizadas 01", "ok": 8, "alerta": 0, "sem_dados": 2, "failed": 1},
        {"line_id": 3, "line_name": "Linha Chás Gelados 01", "ok": 9, "alerta": 1, "sem_dados": 0, "failed": 0},
    ]


def test_line_overview_maps_and_derives_status():
    rows = line_overview(FakeDatabase([_rows()]))
    assert rows == [
        LineOverview(1, "Linha Sucos 01", 10, 0, 0, 0),
        LineOverview(2, "Linha Águas Saborizadas 01", 8, 0, 2, 1),
        LineOverview(3, "Linha Chás Gelados 01", 9, 1, 0, 0),
    ]
    assert rows[0].status == "verde"     # tudo normal
    assert rows[1].status == "amarelo"   # sem_dados/falho, sem alerta
    assert rows[2].status == "vermelho"  # há alerta


def test_lines_partial_renders_three_conveyors_with_status():
    client = TestClient(create_app(FakeDatabase([_rows()])))
    resp = client.get("/api/lines")
    assert resp.status_code == 200
    body = resp.text
    assert body.count('class="conveyor status-') == 3
    assert "status-verde" in body
    assert "status-amarelo" in body
    assert "status-vermelho" in body
    assert "Linha Sucos 01" in body
    assert "<svg" in body  # esteira desenhada


def test_lines_partial_banner_when_db_down():
    class Broken:
        def fetch(self, *a, **k):
            raise RuntimeError("no db")

    client = TestClient(create_app(Broken()))
    resp = client.get("/api/lines")
    assert resp.status_code == 200
    assert "Sem conexão com o banco" in resp.text
