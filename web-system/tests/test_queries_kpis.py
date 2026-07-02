from db import FakeDatabase
from models import KpiSummary, LineRecordCount
from queries import kpis

_RECORDS = [
    {"line_id": 1, "line_name": "Linha Sucos 01", "records": 100},
    {"line_id": 2, "line_name": "Linha Águas Saborizadas 01", "records": 50},
    {"line_id": 3, "line_name": "Linha Chás Gelados 01", "records": 30},
]


def test_kpis_assembles_all_fetches():
    fake = FakeDatabase([
        [{"ok": 25, "alerta": 3, "sem_dados": 2}],
        [{"failed": 1}],
        [{"lines": 3, "production_today": 1234.5}],
        _RECORDS,
    ])
    result = kpis(fake)
    assert result == KpiSummary(
        ok=25, alerta=3, sem_dados=2, failed=1, lines=3, production_today=1234.5,
        total_records=180,
        records_by_line=[
            LineRecordCount(1, "Linha Sucos 01", 100),
            LineRecordCount(2, "Linha Águas Saborizadas 01", 50),
            LineRecordCount(3, "Linha Chás Gelados 01", 30),
        ],
    )
    assert len(fake.calls) == 4


def test_kpis_coerces_nulls_to_zero():
    fake = FakeDatabase([
        [{"ok": 0, "alerta": 0, "sem_dados": 0}],
        [{"failed": 0}],
        [{"lines": 0, "production_today": None}],
        [],
    ])
    result = kpis(fake)
    assert result.production_today == 0.0
    assert result.total_records == 0
    assert result.records_by_line == []
