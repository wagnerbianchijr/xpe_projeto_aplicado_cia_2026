from db import FakeDatabase
from models import KpiSummary
from queries import kpis


def test_kpis_assembles_three_fetches():
    fake = FakeDatabase([
        [{"ok": 25, "alerta": 3, "sem_dados": 2}],
        [{"failed": 1}],
        [{"lines": 3, "production_today": 1234.5}],
    ])
    result = kpis(fake)
    assert result == KpiSummary(
        ok=25, alerta=3, sem_dados=2, failed=1, lines=3, production_today=1234.5
    )
    assert len(fake.calls) == 3


def test_kpis_coerces_nulls_to_zero():
    fake = FakeDatabase([
        [{"ok": 0, "alerta": 0, "sem_dados": 0}],
        [{"failed": 0}],
        [{"lines": 0, "production_today": None}],
    ])
    result = kpis(fake)
    assert result.production_today == 0.0
