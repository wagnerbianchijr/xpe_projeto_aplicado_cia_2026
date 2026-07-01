# web-system Implementation Plan


**Goal:** Build the Serra Clara Bebidas IIoT dashboard: a FastAPI web app that reads Tiger Cloud (TimescaleDB) and renders operational + historical indicators.

**Architecture:** FastAPI serves Jinja2 pages; HTMX polls `/api/*` fragment/JSON routes on an interval; Chart.js renders time series. A `psycopg_pool.ConnectionPool` configured **read-only** feeds a thin `Database.fetch()` used by pure query functions. Query functions take a `SupportsFetch` so tests inject a fake — no live DB in CI.

**Tech Stack:** Python 3, FastAPI, Uvicorn, Jinja2, HTMX, Chart.js, psycopg 3 + psycopg_pool, python-dotenv, pytest, httpx (TestClient).

## Global Constraints

- Component lives under `web-system/`. Run commands from that directory.
- DB access is **read-only**. No writes, no DDL. Enforced at connection level (`conn.read_only = True`).
- Connection string comes from `DATABASE_URL` in `web-system/.env` (git-ignored, same pattern as `simulador`). Never commit `.env`.
- UI language: pt-BR.
- Data sources already exist in the schema (`modelo-de-dados`, complete on service `h3bmabyk97`): tables `production_line`, `sensor`, hypertable `sensor_reading`; continuous aggregates `sensor_reading_1m|15m|30m|1h` (columns `bucket, sensor_id, sum_value, count_value, min_value, max_value, last_value`); views `sensor_status` (`sensor_id, line_id, metric, unit, value, last_time, status`), `sensor_liveness` (`sensor_id, line_id, metric, last_time, seconds_since_last, is_failed`), `sensor_out_of_range_1h` (`bucket, sensor_id, line_id, metric, violated`).
- Metric math: `production_count` → throughput `max_value - min_value`; every other metric → average `sum_value / nullif(count_value, 0)`.
- Aggregate by window: ≤1h→`sensor_reading_1m`, ≤6h→`sensor_reading_15m`, ≤24h→`sensor_reading_30m`, >24h→`sensor_reading_1h`.
- Format SQL with leading commas.
- Tests never require a live database. The app must render (with an error banner) when the DB is unreachable.
- Default HTMX refresh: 5s (matches the simulador tick).

---

### Task 1: Scaffold, dependencies, config

**Files:**
- Create: `web-system/requirements.txt`
- Create: `web-system/pytest.ini`
- Create: `web-system/.env.example`
- Create: `web-system/config.py`
- Test: `web-system/tests/test_config.py`
- Create: `web-system/tests/__init__.py` (empty)

**Interfaces:**
- Produces: `config.Settings(database_url: str, refresh_seconds: int, host: str, port: int)`; `config.load_settings(load_env: bool = True) -> Settings`.

- [ ] **Step 1: Create dependency and test config files**

`web-system/requirements.txt`:
```
fastapi>=0.110
uvicorn[standard]>=0.29
jinja2>=3.1
psycopg[binary]>=3.1
psycopg_pool>=3.2
python-dotenv>=1.0
pytest>=8.0
httpx>=0.27
```

`web-system/pytest.ini`:
```
[pytest]
pythonpath = .
testpaths = tests
```

`web-system/.env.example`:
```
# Copy this file to .env and fill in real values. .env is git-ignored.
# psycopg DSN for the Tiger Cloud service (password stays here only).
DATABASE_URL=postgresql://tsdbadmin:PASSWORD@HOST:PORT/tsdb?sslmode=require

# Optional overrides (defaults shown):
REFRESH_SECONDS=5
HOST=127.0.0.1
PORT=8000
```

`web-system/tests/__init__.py`: empty file.

- [ ] **Step 2: Write the failing test**

`web-system/tests/test_config.py`:
```python
import pytest

from config import Settings, load_settings


def test_load_settings_reads_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    monkeypatch.setenv("REFRESH_SECONDS", "10")
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "9000")
    s = load_settings(load_env=False)
    assert s == Settings(
        database_url="postgresql://u:p@h:5432/db",
        refresh_seconds=10,
        host="0.0.0.0",
        port=9000,
    )


def test_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    monkeypatch.delenv("REFRESH_SECONDS", raising=False)
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    s = load_settings(load_env=False)
    assert s.refresh_seconds == 5
    assert s.host == "127.0.0.1"
    assert s.port == 8000


def test_missing_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        load_settings(load_env=False)


def test_refresh_must_be_positive(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    monkeypatch.setenv("REFRESH_SECONDS", "0")
    with pytest.raises(ValueError):
        load_settings(load_env=False)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd web-system && python -m venv .venv && ./.venv/bin/pip install -r requirements.txt && ./.venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'config'`.

- [ ] **Step 4: Write minimal implementation**

`web-system/config.py`:
```python
"""Configuration loaded from environment (.env is git-ignored)."""
from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_url: str
    refresh_seconds: int
    host: str
    port: int


def load_settings(load_env: bool = True) -> Settings:
    """Build Settings from environment variables.

    When load_env is True, values are first loaded from a local .env file.
    Tests pass load_env=False so a developer's .env cannot leak into results.
    """
    if load_env:
        load_dotenv()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required. Copy web-system/.env.example to "
            "web-system/.env and set it."
        )

    refresh_seconds = int(os.environ.get("REFRESH_SECONDS", "5"))
    if refresh_seconds <= 0:
        raise ValueError(f"REFRESH_SECONDS must be > 0, got {refresh_seconds}")

    return Settings(
        database_url=database_url,
        refresh_seconds=refresh_seconds,
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add web-system/requirements.txt web-system/pytest.ini web-system/.env.example web-system/config.py web-system/tests/__init__.py web-system/tests/test_config.py
git commit -m "web-system: scaffold, dependencies, config"
```

---

### Task 2: Read-only database access layer

**Files:**
- Create: `web-system/db.py`
- Test: `web-system/tests/test_db.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `db.configure(conn) -> None` — pool `configure` callback; sets `conn.read_only = True` and `conn.row_factory = dict_row`.
  - `db.create_pool(database_url: str) -> ConnectionPool` — opens a read-only pool (min 1, max 5, `connect_timeout=5`).
  - `db.Database` — wraps a pool; `fetch(query, params=None) -> list[dict]`.
  - `db.SupportsFetch` — `Protocol` with `fetch(self, query, params=None) -> list[dict]`. Query functions in later tasks accept this type.
  - `db.FakeDatabase(responses: list[list[dict]])` — test double; `fetch` pops the next canned response, records `(query, params)` in `self.calls`; raises `IndexError` if drained.

- [ ] **Step 1: Write the failing test**

`web-system/tests/test_db.py`:
```python
import pytest

from db import FakeDatabase, configure


def test_configure_sets_read_only_and_row_factory():
    from psycopg.rows import dict_row

    class Conn:
        pass

    c = Conn()
    configure(c)
    assert c.read_only is True
    assert c.row_factory is dict_row


def test_fake_database_returns_canned_rows_in_order():
    fake = FakeDatabase([[{"a": 1}], [{"b": 2}]])
    assert fake.fetch("SELECT 1") == [{"a": 1}]
    assert fake.fetch("SELECT 2", {"x": 9}) == [{"b": 2}]
    assert fake.calls == [("SELECT 1", None), ("SELECT 2", {"x": 9})]


def test_fake_database_raises_when_drained():
    fake = FakeDatabase([])
    with pytest.raises(IndexError):
        fake.fetch("SELECT 1")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'db'`.

- [ ] **Step 3: Write minimal implementation**

`web-system/db.py`:
```python
"""Read-only Tiger Cloud access: connection pool + a thin fetch helper."""
from typing import Any, Protocol

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def configure(conn) -> None:
    """Pool configure callback: force read-only + dict rows on every connection."""
    conn.read_only = True
    conn.row_factory = dict_row


def create_pool(database_url: str) -> ConnectionPool:
    """Open a small read-only pool. connect_timeout keeps startup from hanging."""
    return ConnectionPool(
        database_url,
        min_size=1,
        max_size=5,
        kwargs={"connect_timeout": 5},
        configure=configure,
        open=True,
    )


class SupportsFetch(Protocol):
    def fetch(self, query: Any, params: Any = None) -> list[dict]: ...


class Database:
    """Executes read-only queries against a pooled connection."""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def fetch(self, query: Any, params: Any = None) -> list[dict]:
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


class FakeDatabase:
    """Test double: returns canned responses in call order."""

    def __init__(self, responses: list[list[dict]]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple] = []

    def fetch(self, query: Any, params: Any = None) -> list[dict]:
        self.calls.append((query, params))
        return self._responses.pop(0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_db.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add web-system/db.py web-system/tests/test_db.py
git commit -m "web-system: read-only db pool, fetch helper, fake"
```

---

### Task 3: Aggregate/metric selectors + models

**Files:**
- Create: `web-system/selectors.py`
- Create: `web-system/models.py`
- Test: `web-system/tests/test_selectors.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `selectors.pick_aggregate(window_seconds: int) -> str` — returns a view name.
  - `selectors.value_expr(metric: str) -> psycopg.sql.Composable` — SQL expression for the metric's value column.
  - `models.KpiSummary(ok, alerta, sem_dados, failed, lines, production_today)`.
  - `models.SensorStatusRow(sensor_id, line_id, line_name, metric, unit, value, last_time, status)`.
  - `models.LivenessRow(sensor_id, line_id, metric, last_time, seconds_since_last, is_failed)`.
  - `models.TimeseriesPoint(time, value)`.
  - `models.ViolationRow(bucket, sensor_id, line_id, metric)`.
  - `models.SensorMeta(sensor_id, line_id, metric, unit, min_limit, max_limit, description)`.

- [ ] **Step 1: Write the failing test**

`web-system/tests/test_selectors.py`:
```python
from selectors import pick_aggregate, value_expr


def test_pick_aggregate_boundaries():
    assert pick_aggregate(60) == "sensor_reading_1m"
    assert pick_aggregate(3600) == "sensor_reading_1m"
    assert pick_aggregate(3601) == "sensor_reading_15m"
    assert pick_aggregate(6 * 3600) == "sensor_reading_15m"
    assert pick_aggregate(6 * 3600 + 1) == "sensor_reading_30m"
    assert pick_aggregate(24 * 3600) == "sensor_reading_30m"
    assert pick_aggregate(24 * 3600 + 1) == "sensor_reading_1h"
    assert pick_aggregate(90 * 24 * 3600) == "sensor_reading_1h"


def test_value_expr_average_for_normal_metric():
    assert value_expr("temperature").as_string(None) == "sum_value / nullif(count_value, 0)"


def test_value_expr_throughput_for_production_count():
    assert value_expr("production_count").as_string(None) == "max_value - min_value"
```

Note: `selectors` is a stdlib module name; `pythonpath = .` in `pytest.ini` puts the local file first, so the local module wins. Keep the local filename `selectors.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_selectors.py -v`
Expected: FAIL — `ImportError: cannot import name 'pick_aggregate'`.

- [ ] **Step 3: Write minimal implementation**

`web-system/selectors.py`:
```python
"""Pure selectors: window -> aggregate view, and metric -> value expression."""
from psycopg import sql


def pick_aggregate(window_seconds: int) -> str:
    """Choose the coarsest aggregate that still covers the window well."""
    if window_seconds <= 3600:
        return "sensor_reading_1m"
    if window_seconds <= 6 * 3600:
        return "sensor_reading_15m"
    if window_seconds <= 24 * 3600:
        return "sensor_reading_30m"
    return "sensor_reading_1h"


def value_expr(metric: str) -> sql.Composable:
    """Value column for a metric: throughput for counters, average otherwise."""
    if metric == "production_count":
        return sql.SQL("max_value - min_value")
    return sql.SQL("sum_value / nullif(count_value, 0)")
```

`web-system/models.py`:
```python
"""Typed rows returned by the query layer."""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class KpiSummary:
    ok: int
    alerta: int
    sem_dados: int
    failed: int
    lines: int
    production_today: float


@dataclass
class SensorStatusRow:
    sensor_id: int
    line_id: int
    line_name: str
    metric: str
    unit: str
    value: float | None
    last_time: datetime | None
    status: str


@dataclass
class LivenessRow:
    sensor_id: int
    line_id: int
    metric: str
    last_time: datetime | None
    seconds_since_last: float | None
    is_failed: bool


@dataclass
class TimeseriesPoint:
    time: datetime
    value: float | None


@dataclass
class ViolationRow:
    bucket: datetime
    sensor_id: int
    line_id: int
    metric: str


@dataclass
class SensorMeta:
    sensor_id: int
    line_id: int
    metric: str
    unit: str
    min_limit: float | None
    max_limit: float | None
    description: str | None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_selectors.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add web-system/selectors.py web-system/models.py web-system/tests/test_selectors.py
git commit -m "web-system: aggregate/metric selectors and row models"
```

---

### Task 4: KPI query

**Files:**
- Create: `web-system/queries.py`
- Test: `web-system/tests/test_queries_kpis.py`

**Interfaces:**
- Consumes: `db.SupportsFetch`, `models.KpiSummary`.
- Produces: `queries.kpis(db: SupportsFetch) -> KpiSummary`. Issues exactly 3 fetches in order: (1) status counts, (2) failed count, (3) lines + production_today.

- [ ] **Step 1: Write the failing test**

`web-system/tests/test_queries_kpis.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_queries_kpis.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'queries'`.

- [ ] **Step 3: Write minimal implementation**

`web-system/queries.py`:
```python
"""Read-only query functions. Each takes a SupportsFetch and returns models."""
from db import SupportsFetch
from models import KpiSummary

_STATUS_COUNTS_SQL = """
SELECT
    count(*) FILTER (WHERE status = 'normal')    AS ok
  , count(*) FILTER (WHERE status = 'alerta')    AS alerta
  , count(*) FILTER (WHERE status = 'sem_dados') AS sem_dados
FROM sensor_status
"""

_FAILED_COUNT_SQL = """
SELECT
    count(*) FILTER (WHERE is_failed) AS failed
FROM sensor_liveness
"""

_LINES_AND_PRODUCTION_SQL = """
SELECT
    (SELECT count(*) FROM production_line) AS lines
  , coalesce((
        SELECT sum(daily.throughput)
        FROM (
            SELECT
                max(r.value) - min(r.value) AS throughput
            FROM sensor_reading r
            JOIN sensor s ON s.sensor_id = r.sensor_id
            WHERE s.metric = 'production_count'
              AND r.time >= date_trunc('day', now())
            GROUP BY r.sensor_id
        ) daily
    ), 0) AS production_today
"""


def kpis(db: SupportsFetch) -> KpiSummary:
    counts = db.fetch(_STATUS_COUNTS_SQL)[0]
    failed = db.fetch(_FAILED_COUNT_SQL)[0]
    totals = db.fetch(_LINES_AND_PRODUCTION_SQL)[0]
    return KpiSummary(
        ok=counts["ok"],
        alerta=counts["alerta"],
        sem_dados=counts["sem_dados"],
        failed=failed["failed"],
        lines=totals["lines"],
        production_today=float(totals["production_today"] or 0.0),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_queries_kpis.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add web-system/queries.py web-system/tests/test_queries_kpis.py
git commit -m "web-system: KPI summary query"
```

---

### Task 5: Operational queries (status + liveness)

**Files:**
- Modify: `web-system/queries.py`
- Test: `web-system/tests/test_queries_operational.py`

**Interfaces:**
- Consumes: `db.SupportsFetch`, `models.SensorStatusRow`, `models.LivenessRow`.
- Produces:
  - `queries.sensor_status(db, line_id: int | None = None) -> list[SensorStatusRow]`.
  - `queries.failed_sensors(db, line_id: int | None = None) -> list[LivenessRow]`.

- [ ] **Step 1: Write the failing test**

`web-system/tests/test_queries_operational.py`:
```python
from datetime import datetime, timezone

from db import FakeDatabase
from models import LivenessRow, SensorStatusRow
from queries import failed_sensors, sensor_status

T = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)


def test_sensor_status_maps_rows_and_passes_line_filter():
    fake = FakeDatabase([[
        {
            "sensor_id": 101, "line_id": 1, "line_name": "Linha Sucos 01",
            "metric": "temperature", "unit": "°C", "value": 80.0,
            "last_time": T, "status": "normal",
        },
    ]])
    rows = sensor_status(fake, line_id=1)
    assert rows == [SensorStatusRow(101, 1, "Linha Sucos 01", "temperature", "°C", 80.0, T, "normal")]
    assert fake.calls[0][1] == {"line_id": 1}


def test_sensor_status_default_line_is_none():
    fake = FakeDatabase([[]])
    assert sensor_status(fake) == []
    assert fake.calls[0][1] == {"line_id": None}


def test_failed_sensors_maps_rows():
    fake = FakeDatabase([[
        {
            "sensor_id": 205, "line_id": 2, "metric": "line_speed",
            "last_time": None, "seconds_since_last": None, "is_failed": True,
        },
    ]])
    rows = failed_sensors(fake, line_id=2)
    assert rows == [LivenessRow(205, 2, "line_speed", None, None, True)]
    assert fake.calls[0][1] == {"line_id": 2}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_queries_operational.py -v`
Expected: FAIL — `ImportError: cannot import name 'sensor_status'`.

- [ ] **Step 3: Write minimal implementation**

Append to `web-system/queries.py`:
```python
from models import LivenessRow, SensorStatusRow

_SENSOR_STATUS_SQL = """
SELECT
    ss.sensor_id
  , ss.line_id
  , pl.name AS line_name
  , ss.metric
  , ss.unit
  , ss.value
  , ss.last_time
  , ss.status
FROM sensor_status ss
JOIN production_line pl ON pl.line_id = ss.line_id
WHERE (%(line_id)s IS NULL OR ss.line_id = %(line_id)s)
ORDER BY ss.line_id, ss.sensor_id
"""

_FAILED_SENSORS_SQL = """
SELECT
    sl.sensor_id
  , sl.line_id
  , sl.metric
  , sl.last_time
  , sl.seconds_since_last
  , sl.is_failed
FROM sensor_liveness sl
WHERE sl.is_failed
  AND (%(line_id)s IS NULL OR sl.line_id = %(line_id)s)
ORDER BY sl.line_id, sl.sensor_id
"""


def sensor_status(db: SupportsFetch, line_id: int | None = None) -> list[SensorStatusRow]:
    rows = db.fetch(_SENSOR_STATUS_SQL, {"line_id": line_id})
    return [
        SensorStatusRow(
            sensor_id=r["sensor_id"],
            line_id=r["line_id"],
            line_name=r["line_name"],
            metric=r["metric"],
            unit=r["unit"],
            value=r["value"],
            last_time=r["last_time"],
            status=r["status"],
        )
        for r in rows
    ]


def failed_sensors(db: SupportsFetch, line_id: int | None = None) -> list[LivenessRow]:
    rows = db.fetch(_FAILED_SENSORS_SQL, {"line_id": line_id})
    return [
        LivenessRow(
            sensor_id=r["sensor_id"],
            line_id=r["line_id"],
            metric=r["metric"],
            last_time=r["last_time"],
            seconds_since_last=r["seconds_since_last"],
            is_failed=r["is_failed"],
        )
        for r in rows
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_queries_operational.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add web-system/queries.py web-system/tests/test_queries_operational.py
git commit -m "web-system: operational status and liveness queries"
```

---

### Task 6: Performance queries (timeseries + violations)

**Files:**
- Modify: `web-system/queries.py`
- Test: `web-system/tests/test_queries_performance.py`

**Interfaces:**
- Consumes: `db.SupportsFetch`, `selectors.pick_aggregate`, `selectors.value_expr`, `models.TimeseriesPoint`, `models.ViolationRow`.
- Produces:
  - `queries.timeseries(db, sensor_id: int, metric: str, window_seconds: int) -> list[TimeseriesPoint]`.
  - `queries.violations(db, line_id: int | None, window_seconds: int) -> list[ViolationRow]`.

- [ ] **Step 1: Write the failing test**

`web-system/tests/test_queries_performance.py`:
```python
from datetime import datetime, timezone

from db import FakeDatabase
from models import TimeseriesPoint, ViolationRow
from queries import timeseries, violations

T = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)


def test_timeseries_selects_aggregate_by_window_and_maps_points():
    fake = FakeDatabase([[{"time": T, "value": 80.0}]])
    pts = timeseries(fake, sensor_id=101, metric="temperature", window_seconds=3600)
    assert pts == [TimeseriesPoint(T, 80.0)]
    query, params = fake.calls[0]
    rendered = query.as_string(None)
    assert "sensor_reading_1m" in rendered
    assert "sum_value / nullif(count_value, 0)" in rendered
    assert params == {"sensor_id": 101, "window": "3600 seconds"}


def test_timeseries_uses_throughput_and_coarser_view_for_wide_window():
    fake = FakeDatabase([[]])
    timeseries(fake, sensor_id=106, metric="production_count", window_seconds=90 * 24 * 3600)
    rendered = fake.calls[0][0].as_string(None)
    assert "sensor_reading_1h" in rendered
    assert "max_value - min_value" in rendered


def test_violations_maps_rows_and_passes_params():
    fake = FakeDatabase([[
        {"bucket": T, "sensor_id": 101, "line_id": 1, "metric": "temperature"},
    ]])
    rows = violations(fake, line_id=1, window_seconds=24 * 3600)
    assert rows == [ViolationRow(T, 101, 1, "temperature")]
    assert fake.calls[0][1] == {"line_id": 1, "window": "86400 seconds"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_queries_performance.py -v`
Expected: FAIL — `ImportError: cannot import name 'timeseries'`.

- [ ] **Step 3: Write minimal implementation**

Append to `web-system/queries.py`:
```python
from psycopg import sql

from models import TimeseriesPoint, ViolationRow
from selectors import pick_aggregate, value_expr

_VIOLATIONS_SQL = """
SELECT
    bucket
  , sensor_id
  , line_id
  , metric
FROM sensor_out_of_range_1h
WHERE violated
  AND (%(line_id)s IS NULL OR line_id = %(line_id)s)
  AND bucket >= now() - %(window)s::interval
ORDER BY bucket DESC
"""


def timeseries(
    db: SupportsFetch, sensor_id: int, metric: str, window_seconds: int
) -> list[TimeseriesPoint]:
    view = pick_aggregate(window_seconds)
    query = sql.SQL(
        """
        SELECT
            bucket AS time
          , {value} AS value
        FROM {view}
        WHERE sensor_id = %(sensor_id)s
          AND bucket >= now() - %(window)s::interval
        ORDER BY bucket
        """
    ).format(value=value_expr(metric), view=sql.Identifier(view))
    rows = db.fetch(
        query, {"sensor_id": sensor_id, "window": f"{window_seconds} seconds"}
    )
    return [TimeseriesPoint(time=r["time"], value=r["value"]) for r in rows]


def violations(
    db: SupportsFetch, line_id: int | None, window_seconds: int
) -> list[ViolationRow]:
    rows = db.fetch(
        _VIOLATIONS_SQL,
        {"line_id": line_id, "window": f"{window_seconds} seconds"},
    )
    return [
        ViolationRow(
            bucket=r["bucket"],
            sensor_id=r["sensor_id"],
            line_id=r["line_id"],
            metric=r["metric"],
        )
        for r in rows
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_queries_performance.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add web-system/queries.py web-system/tests/test_queries_performance.py
git commit -m "web-system: timeseries and violations queries"
```

---

### Task 7: Sensor metadata query

**Files:**
- Modify: `web-system/queries.py`
- Test: `web-system/tests/test_queries_sensor.py`

**Interfaces:**
- Consumes: `db.SupportsFetch`, `models.SensorMeta`.
- Produces: `queries.sensor_meta(db, sensor_id: int) -> SensorMeta | None` — `None` when the sensor does not exist.

- [ ] **Step 1: Write the failing test**

`web-system/tests/test_queries_sensor.py`:
```python
from db import FakeDatabase
from models import SensorMeta
from queries import sensor_meta


def test_sensor_meta_maps_row():
    fake = FakeDatabase([[
        {
            "sensor_id": 101, "line_id": 1, "metric": "temperature",
            "unit": "°C", "min_limit": 70.0, "max_limit": 95.0,
            "description": "Temperatura de pasteurização",
        },
    ]])
    assert sensor_meta(fake, 101) == SensorMeta(
        101, 1, "temperature", "°C", 70.0, 95.0, "Temperatura de pasteurização"
    )


def test_sensor_meta_returns_none_when_absent():
    fake = FakeDatabase([[]])
    assert sensor_meta(fake, 999) is None
    assert fake.calls[0][1] == {"sensor_id": 999}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_queries_sensor.py -v`
Expected: FAIL — `ImportError: cannot import name 'sensor_meta'`.

- [ ] **Step 3: Write minimal implementation**

Append to `web-system/queries.py`:
```python
from models import SensorMeta

_SENSOR_META_SQL = """
SELECT
    sensor_id
  , line_id
  , metric
  , unit
  , min_limit
  , max_limit
  , description
FROM sensor
WHERE sensor_id = %(sensor_id)s
"""


def sensor_meta(db: SupportsFetch, sensor_id: int) -> SensorMeta | None:
    rows = db.fetch(_SENSOR_META_SQL, {"sensor_id": sensor_id})
    if not rows:
        return None
    r = rows[0]
    return SensorMeta(
        sensor_id=r["sensor_id"],
        line_id=r["line_id"],
        metric=r["metric"],
        unit=r["unit"],
        min_limit=r["min_limit"],
        max_limit=r["max_limit"],
        description=r["description"],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_queries_sensor.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add web-system/queries.py web-system/tests/test_queries_sensor.py
git commit -m "web-system: sensor metadata query"
```

---

### Task 8: App factory, base layout, overview + KPIs partial

**Files:**
- Create: `web-system/app.py`
- Create: `web-system/templates/base.html`
- Create: `web-system/templates/overview.html`
- Create: `web-system/templates/partials/kpis.html`
- Create: `web-system/static/app.css`
- Test: `web-system/tests/test_app_overview.py`

**Interfaces:**
- Consumes: `db.SupportsFetch`, `queries.kpis`.
- Produces: `app.create_app(db: SupportsFetch, refresh_seconds: int = 5) -> FastAPI`. Routes so far: `GET /` (overview page), `GET /api/kpis` (KPI partial). Templates receive `request`, `refresh_seconds`, and page data. `app.safe(fn, default)` runs a query, returning `default` and setting a page-level `db_error` flag on failure.

- [ ] **Step 1: Write the failing test**

`web-system/tests/test_app_overview.py`:
```python
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
    assert "sem conexão com o banco" in resp.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_app_overview.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app'`.

- [ ] **Step 3: Write minimal implementation**

`web-system/app.py`:
```python
"""FastAPI app factory for the Serra Clara IIoT dashboard."""
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from db import SupportsFetch
from queries import (
    failed_sensors,
    kpis,
    sensor_meta,
    sensor_status,
    timeseries,
    violations,
)

_BASE = Path(__file__).parent
_TEMPLATES = Jinja2Templates(directory=str(_BASE / "templates"))


class _DbError:
    """Mutable flag threaded into a template render."""

    def __init__(self) -> None:
        self.failed = False


def safe(flag: "_DbError", fn: Callable[[], Any], default: Any) -> Any:
    """Run a query; on any failure set the error flag and return default."""
    try:
        return fn()
    except Exception:
        flag.failed = True
        return default


def create_app(db: SupportsFetch, refresh_seconds: int = 5) -> FastAPI:
    app = FastAPI(title="Serra Clara Bebidas — IIoT Dashboard")
    app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")

    def ctx(request: Request, **extra: Any) -> dict:
        base = {"request": request, "refresh_seconds": refresh_seconds}
        base.update(extra)
        return base

    @app.get("/", response_class=HTMLResponse)
    def overview(request: Request):
        return _TEMPLATES.TemplateResponse("overview.html", ctx(request, active="overview"))

    @app.get("/api/kpis", response_class=HTMLResponse)
    def api_kpis(request: Request):
        flag = _DbError()
        data = safe(flag, lambda: kpis(db), None)
        return _TEMPLATES.TemplateResponse(
            "partials/kpis.html", ctx(request, kpi=data, db_error=flag.failed)
        )

    return app
```

`web-system/templates/base.html`:
```html
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Serra Clara Bebidas — Painel IIoT</title>
  <link rel="stylesheet" href="/static/app.css">
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
</head>
<body>
  <header class="topbar">
    <h1>Serra Clara Bebidas — Painel IIoT</h1>
    <nav>
      <a href="/" class="{{ 'on' if active == 'overview' else '' }}">Visão geral</a>
      <a href="/operational" class="{{ 'on' if active == 'operational' else '' }}">Operational Hub</a>
      <a href="/performance" class="{{ 'on' if active == 'performance' else '' }}">Performance Insights</a>
    </nav>
  </header>

  <section id="kpis" hx-get="/api/kpis" hx-trigger="load, every {{ refresh_seconds }}s" hx-swap="innerHTML">
    <p class="muted">Carregando indicadores…</p>
  </section>

  <main>
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

`web-system/templates/overview.html`:
```html
{% extends "base.html" %}
{% block content %}
<p class="muted">
  Selecione <strong>Operational Hub</strong> para o estado em tempo real ou
  <strong>Performance Insights</strong> para o histórico.
</p>
{% endblock %}
```

`web-system/templates/partials/kpis.html`:
```html
{% if db_error %}
<div class="banner error">Sem conexão com o banco. Indicadores indisponíveis.</div>
{% else %}
<div class="kpi-grid">
  <div class="kpi ok"><span class="n">{{ kpi.ok }}</span><span class="l">Sensores OK</span></div>
  <div class="kpi warn"><span class="n">{{ kpi.alerta }}</span><span class="l">Em alerta</span></div>
  <div class="kpi mute"><span class="n">{{ kpi.sem_dados }}</span><span class="l">Sem dados</span></div>
  <div class="kpi bad"><span class="n">{{ kpi.failed }}</span><span class="l">Sensores falhos</span></div>
  <div class="kpi"><span class="n">{{ kpi.lines }}</span><span class="l">Linhas</span></div>
  <div class="kpi"><span class="n">{{ "%.0f"|format(kpi.production_today) }}</span><span class="l">Produção hoje</span></div>
</div>
{% endif %}
```

`web-system/static/app.css`:
```css
:root { --bg:#0f1720; --card:#182534; --ink:#e6edf3; --mut:#8b98a5; --ok:#2ea043; --warn:#d29922; --bad:#f85149; --accent:#f0883e; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 system-ui, sans-serif; }
.topbar { padding:16px 24px; background:#0b1219; border-bottom:1px solid #223; }
.topbar h1 { font-size:18px; margin:0 0 8px; }
nav a { color:var(--mut); text-decoration:none; margin-right:16px; padding-bottom:4px; }
nav a.on { color:var(--accent); border-bottom:2px solid var(--accent); }
main, #kpis { padding:16px 24px; }
.muted { color:var(--mut); }
.kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; }
.kpi { background:var(--card); border-radius:10px; padding:14px; display:flex; flex-direction:column; gap:4px; }
.kpi .n { font-size:26px; font-weight:700; }
.kpi .l { color:var(--mut); font-size:12px; }
.kpi.ok .n{color:var(--ok);} .kpi.warn .n{color:var(--warn);} .kpi.bad .n{color:var(--bad);} .kpi.mute .n{color:var(--mut);}
table { width:100%; border-collapse:collapse; }
th, td { text-align:left; padding:8px 10px; border-bottom:1px solid #223; }
th { color:var(--mut); font-weight:600; font-size:12px; text-transform:uppercase; }
.pill { padding:2px 8px; border-radius:999px; font-size:12px; }
.pill.normal{background:#12331e;color:var(--ok);} .pill.alerta{background:#3a2a12;color:var(--warn);} .pill.sem_dados{background:#2a2f36;color:var(--mut);}
.banner.error { background:#3a1417; color:var(--bad); padding:10px 14px; border-radius:8px; }
.controls { display:flex; gap:12px; align-items:center; margin-bottom:16px; }
select, a.btn { background:var(--card); color:var(--ink); border:1px solid #223; border-radius:8px; padding:6px 10px; text-decoration:none; }
canvas { background:var(--card); border-radius:10px; padding:10px; }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_app_overview.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add web-system/app.py web-system/templates web-system/static web-system/tests/test_app_overview.py
git commit -m "web-system: app factory, base layout, overview + KPIs partial"
```

---

### Task 9: Operational Hub page

**Files:**
- Modify: `web-system/app.py`
- Create: `web-system/templates/operational.html`
- Create: `web-system/templates/partials/operational_table.html`
- Test: `web-system/tests/test_app_operational.py`

**Interfaces:**
- Consumes: `queries.sensor_status`, `queries.failed_sensors`.
- Produces: routes `GET /operational` (page; optional `?line_id=`) and `GET /api/operational` (table partial; optional `?line_id=`).

- [ ] **Step 1: Write the failing test**

`web-system/tests/test_app_operational.py`:
```python
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app import create_app

T = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)


class FakeByCall:
    """Returns responses keyed by SQL substring so route order is irrelevant."""

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
        # KPI header queries (base layout triggers them on load):
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
    assert "line_speed" in body  # failed sensor listed
```

Note: the KPI-header substrings (`"FROM sensor_status\n"`, `"FROM sensor_liveness\n"`, `"production_today"`) are matched before the operational ones because Python dicts preserve insertion order and `FakeByCall` returns the first match — but `"FROM sensor_status ss"` and `"FROM sensor_liveness sl"` are distinct substrings, so operational and KPI queries never collide.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_app_operational.py -v`
Expected: FAIL — 404 on `/operational` (route not defined).

- [ ] **Step 3: Write minimal implementation**

Add these routes inside `create_app` in `web-system/app.py`, before `return app`:
```python
    def _line_id(value: str | None) -> int | None:
        return int(value) if value not in (None, "", "all") else None

    @app.get("/operational", response_class=HTMLResponse)
    def operational(request: Request, line_id: str | None = None):
        return _TEMPLATES.TemplateResponse(
            "operational.html",
            ctx(request, active="operational", line_id=line_id or "all"),
        )

    @app.get("/api/operational", response_class=HTMLResponse)
    def api_operational(request: Request, line_id: str | None = None):
        flag = _DbError()
        lid = _line_id(line_id)
        rows = safe(flag, lambda: sensor_status(db, lid), [])
        failed = safe(flag, lambda: failed_sensors(db, lid), [])
        return _TEMPLATES.TemplateResponse(
            "partials/operational_table.html",
            ctx(request, rows=rows, failed=failed, db_error=flag.failed),
        )
```

`web-system/templates/operational.html`:
```html
{% extends "base.html" %}
{% block content %}
<div class="controls">
  <label for="line">Linha:</label>
  <select id="line" name="line_id"
          hx-get="/api/operational" hx-target="#op-table" hx-swap="innerHTML"
          hx-trigger="change">
    <option value="all">Todas</option>
    <option value="1">Linha Sucos 01</option>
    <option value="2">Linha Águas Saborizadas 01</option>
    <option value="3">Linha Chás Gelados 01</option>
  </select>
</div>
<div id="op-table"
     hx-get="/api/operational" hx-trigger="load, every {{ refresh_seconds }}s"
     hx-include="#line" hx-swap="innerHTML">
  <p class="muted">Carregando…</p>
</div>
{% endblock %}
```

`web-system/templates/partials/operational_table.html`:
```html
{% if db_error %}
<div class="banner error">Sem conexão com o banco. Estado indisponível.</div>
{% else %}
{% if failed %}
<div class="banner error">
  {{ failed|length }} sensor(es) sem leituras recentes:
  {% for f in failed %}{{ f.sensor_id }} ({{ f.metric }}){% if not loop.last %}, {% endif %}{% endfor %}
</div>
{% endif %}
<table>
  <thead>
    <tr><th>Sensor</th><th>Linha</th><th>Métrica</th><th>Valor</th><th>Última leitura</th><th>Status</th></tr>
  </thead>
  <tbody>
    {% for r in rows %}
    <tr>
      <td><a class="btn" href="/sensor/{{ r.sensor_id }}">{{ r.sensor_id }}</a></td>
      <td>{{ r.line_name }}</td>
      <td>{{ r.metric }}</td>
      <td>{% if r.value is not none %}{{ "%.2f"|format(r.value) }} {{ r.unit }}{% else %}—{% endif %}</td>
      <td>{{ r.last_time.strftime("%d/%m %H:%M:%S") if r.last_time else "—" }}</td>
      <td><span class="pill {{ r.status }}">{{ r.status }}</span></td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% endif %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_app_operational.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add web-system/app.py web-system/templates/operational.html web-system/templates/partials/operational_table.html web-system/tests/test_app_operational.py
git commit -m "web-system: Operational Hub page and table partial"
```

---

### Task 10: Performance Insights page + timeseries JSON

**Files:**
- Modify: `web-system/app.py`
- Create: `web-system/templates/performance.html`
- Create: `web-system/static/charts.js`
- Test: `web-system/tests/test_app_performance.py`

**Interfaces:**
- Consumes: `queries.timeseries`, `queries.sensor_meta`, `queries.violations`.
- Produces:
  - `GET /performance` (page).
  - `GET /api/timeseries?sensor_id=&window=` → JSON `{"points":[{"time": iso, "value": float|null}], "limits":{"min":..,"max":..}, "metric":..,"unit":..}`. `window` in seconds (default 3600). 404 when the sensor is unknown.

- [ ] **Step 1: Write the failing test**

`web-system/tests/test_app_performance.py`:
```python
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
        "FROM sensor_reading_": [{"time": T, "value": 80.0}],
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_app_performance.py -v`
Expected: FAIL — 404 on `/performance` (route not defined) / JSON assertions error.

- [ ] **Step 3: Write minimal implementation**

Add routes inside `create_app` in `web-system/app.py`, before `return app`:
```python
    @app.get("/performance", response_class=HTMLResponse)
    def performance(request: Request):
        return _TEMPLATES.TemplateResponse(
            "performance.html", ctx(request, active="performance")
        )

    @app.get("/api/timeseries")
    def api_timeseries(sensor_id: int, window: int = 3600):
        meta = sensor_meta(db, sensor_id)
        if meta is None:
            raise HTTPException(status_code=404, detail="sensor não encontrado")
        points = timeseries(db, sensor_id, meta.metric, window)
        return JSONResponse({
            "metric": meta.metric,
            "unit": meta.unit,
            "limits": {"min": meta.min_limit, "max": meta.max_limit},
            "points": [
                {"time": p.time.isoformat(), "value": p.value} for p in points
            ],
        })
```

`web-system/templates/performance.html`:
```html
{% extends "base.html" %}
{% block content %}
<div class="controls">
  <label for="sensor">Sensor:</label>
  <select id="sensor">
    <optgroup label="Linha Sucos 01">
      <option value="101">101 · temperature</option>
      <option value="102">102 · pressure</option>
      <option value="103">103 · flow</option>
      <option value="105">105 · line_speed</option>
      <option value="106">106 · production_count</option>
      <option value="109">109 · brix</option>
    </optgroup>
    <optgroup label="Linha Águas Saborizadas 01">
      <option value="201">201 · temperature</option>
      <option value="206">206 · production_count</option>
      <option value="209">209 · co2</option>
    </optgroup>
    <optgroup label="Linha Chás Gelados 01">
      <option value="301">301 · temperature</option>
      <option value="306">306 · production_count</option>
      <option value="309">309 · infusion_temp</option>
    </optgroup>
  </select>
  <label for="window">Janela:</label>
  <select id="window">
    <option value="3600">1 hora</option>
    <option value="21600">6 horas</option>
    <option value="86400" selected>24 horas</option>
    <option value="604800">7 dias</option>
  </select>
</div>
<canvas id="chart" height="120"></canvas>
<script src="/static/charts.js"></script>
{% endblock %}
```

`web-system/static/charts.js`:
```javascript
(function () {
  const sensorSel = document.getElementById("sensor");
  const windowSel = document.getElementById("window");
  const ctx = document.getElementById("chart");
  let chart;

  async function load() {
    const sid = sensorSel.value;
    const win = windowSel.value;
    const res = await fetch(`/api/timeseries?sensor_id=${sid}&window=${win}`);
    if (!res.ok) return;
    const data = await res.json();
    const labels = data.points.map((p) => p.time.slice(5, 16).replace("T", " "));
    const values = data.points.map((p) => p.value);
    const datasets = [{ label: `${data.metric} (${data.unit})`, data: values, borderColor: "#f0883e", tension: 0.2, pointRadius: 0 }];
    for (const [key, color] of [["min", "#f85149"], ["max", "#f85149"]]) {
      const lim = data.limits[key];
      if (lim !== null) datasets.push({ label: `${key} limit`, data: values.map(() => lim), borderColor: color, borderDash: [6, 4], pointRadius: 0 });
    }
    if (chart) chart.destroy();
    chart = new Chart(ctx, {
      type: "line",
      data: { labels, datasets },
      options: { responsive: true, plugins: { legend: { labels: { color: "#e6edf3" } } }, scales: { x: { ticks: { color: "#8b98a5" } }, y: { ticks: { color: "#8b98a5" } } } },
    });
  }

  sensorSel.addEventListener("change", load);
  windowSel.addEventListener("change", load);
  load();
})();
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_app_performance.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add web-system/app.py web-system/templates/performance.html web-system/static/charts.js web-system/tests/test_app_performance.py
git commit -m "web-system: Performance Insights page and timeseries JSON"
```

---

### Task 11: Sensor detail page

**Files:**
- Modify: `web-system/app.py`
- Create: `web-system/templates/sensor_detail.html`
- Test: `web-system/tests/test_app_sensor.py`

**Interfaces:**
- Consumes: `queries.sensor_meta`, `queries.violations`, `GET /api/timeseries` (reused by the page's chart).
- Produces: `GET /sensor/{sensor_id}` — page with sensor meta, an embedded chart (reusing `/api/timeseries`), and recent violations. 404 when the sensor is unknown.

- [ ] **Step 1: Write the failing test**

`web-system/tests/test_app_sensor.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_app_sensor.py -v`
Expected: FAIL — 404 on `/sensor/101` because the route is undefined (both tests currently see 404; the first must instead render 200).

- [ ] **Step 3: Write minimal implementation**

Add route inside `create_app` in `web-system/app.py`, before `return app`:
```python
    @app.get("/sensor/{sensor_id}", response_class=HTMLResponse)
    def sensor_detail(request: Request, sensor_id: int):
        meta = sensor_meta(db, sensor_id)
        if meta is None:
            raise HTTPException(status_code=404, detail="sensor não encontrado")
        flag = _DbError()
        recent = safe(flag, lambda: violations(db, meta.line_id, 7 * 24 * 3600), [])
        sensor_violations = [v for v in recent if v.sensor_id == sensor_id]
        return _TEMPLATES.TemplateResponse(
            "sensor_detail.html",
            ctx(request, meta=meta, violations=sensor_violations, db_error=flag.failed),
        )
```

`web-system/templates/sensor_detail.html`:
```html
{% extends "base.html" %}
{% block content %}
<a class="btn" href="/operational">← Voltar</a>
<h2>Sensor {{ meta.sensor_id }} · {{ meta.metric }} ({{ meta.unit }})</h2>
<p class="muted">{{ meta.description }} — Linha {{ meta.line_id }}. Limites:
  {{ meta.min_limit if meta.min_limit is not none else "—" }} …
  {{ meta.max_limit if meta.max_limit is not none else "—" }} {{ meta.unit }}.
</p>

<div class="controls">
  <label for="window">Janela:</label>
  <select id="window">
    <option value="3600">1 hora</option>
    <option value="21600">6 horas</option>
    <option value="86400" selected>24 horas</option>
    <option value="604800">7 dias</option>
  </select>
</div>
<canvas id="chart" height="120"></canvas>

<h3>Violações recentes (7 dias)</h3>
{% if violations %}
<table>
  <thead><tr><th>Hora (bucket)</th><th>Métrica</th></tr></thead>
  <tbody>
    {% for v in violations %}
    <tr><td>{{ v.bucket.strftime("%d/%m %H:%M") }}</td><td>{{ v.metric }}</td></tr>
    {% endfor %}
  </tbody>
</table>
{% else %}
<p class="muted">Nenhuma violação registrada na janela.</p>
{% endif %}

<script>
  const SENSOR_ID = {{ meta.sensor_id }};
</script>
<script>
(function () {
  const windowSel = document.getElementById("window");
  const ctx = document.getElementById("chart");
  let chart;
  async function load() {
    const res = await fetch(`/api/timeseries?sensor_id=${SENSOR_ID}&window=${windowSel.value}`);
    if (!res.ok) return;
    const data = await res.json();
    const labels = data.points.map((p) => p.time.slice(5, 16).replace("T", " "));
    const values = data.points.map((p) => p.value);
    const datasets = [{ label: `${data.metric} (${data.unit})`, data: values, borderColor: "#f0883e", tension: 0.2, pointRadius: 0 }];
    for (const key of ["min", "max"]) {
      const lim = data.limits[key];
      if (lim !== null) datasets.push({ label: `${key} limit`, data: values.map(() => lim), borderColor: "#f85149", borderDash: [6, 4], pointRadius: 0 });
    }
    if (chart) chart.destroy();
    chart = new Chart(ctx, { type: "line", data: { labels, datasets },
      options: { responsive: true, plugins: { legend: { labels: { color: "#e6edf3" } } }, scales: { x: { ticks: { color: "#8b98a5" } }, y: { ticks: { color: "#8b98a5" } } } } });
  }
  windowSel.addEventListener("change", load);
  load();
})();
</script>
{% endblock %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web-system && ./.venv/bin/python -m pytest tests/test_app_sensor.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add web-system/app.py web-system/templates/sensor_detail.html web-system/tests/test_app_sensor.py
git commit -m "web-system: sensor detail page with chart and violations"
```

---

### Task 12: Entry point, Dockerfile, README, full suite

**Files:**
- Create: `web-system/main.py`
- Create: `web-system/Dockerfile`
- Create: `web-system/.dockerignore`
- Create: `web-system/README.md`
- Modify: root `the project guidance file` (record web-system run/test commands)

**Interfaces:**
- Consumes: `config.load_settings`, `db.create_pool`, `db.Database`, `app.create_app`.
- Produces: `main.app` — the ASGI app for `uvicorn main:app`.

- [ ] **Step 1: Write the entry point**

`web-system/main.py`:
```python
"""ASGI entry point. `uvicorn main:app` serves the dashboard."""
from app import create_app
from config import load_settings
from db import Database, create_pool

_settings = load_settings()
_pool = create_pool(_settings.database_url)
app = create_app(Database(_pool), refresh_seconds=_settings.refresh_seconds)


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=_settings.host, port=_settings.port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the container + ignore files**

`web-system/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
ENV HOST=0.0.0.0 PORT=8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`web-system/.dockerignore`:
```
.venv
__pycache__
.pytest_cache
tests
.env
*.md
```

- [ ] **Step 3: Write the README**

`web-system/README.md`:
```markdown
# web-system

Dashboard IIoT da **Serra Clara Bebidas S.A.** (FastAPI + HTMX + Chart.js).
Lê o Tiger Cloud (TimescaleDB, serviço `h3bmabyk97`) em modo **somente leitura**
e mostra indicadores operacionais e históricos.

## Telas

- **Visão geral** (`/`): cartões de KPI (OK / alerta / sem dados / falhos / linhas / produção do dia).
- **Operational Hub** (`/operational`): status por sensor em tempo real + sensores falhos, filtro por linha.
- **Performance Insights** (`/performance`): séries temporais dos agregados contínuos.
- **Detalhe do sensor** (`/sensor/{id}`): série com limites min/max + violações recentes.

## Configuração

Copie `.env.example` para `.env` (git-ignored) e defina `DATABASE_URL`:

    cp .env.example .env
    # edite DATABASE_URL

Variáveis: `DATABASE_URL` (obrigatória), `REFRESH_SECONDS` (padrão 5), `HOST`, `PORT`.

## Rodar

    python -m venv .venv
    ./.venv/bin/pip install -r requirements.txt
    ./.venv/bin/python main.py      # http://127.0.0.1:8000

Ou via Uvicorn com reload em dev:

    ./.venv/bin/python -m uvicorn main:app --reload

## Testes

    ./.venv/bin/python -m pytest -v

Os testes usam duplês (`FakeDatabase`) e não exigem banco vivo.

## Deploy

`Dockerfile` empacota a app para deploy futuro em VPC (VPC Peering / Private Link
ao Tiger Cloud, provisionado pelo `terraform`):

    docker build -t serraclara-web .
    docker run -p 8000:8000 --env-file .env serraclara-web

## Arquitetura

`config.py` (env) → `db.py` (pool read-only + `fetch`) → `queries.py`
(SQL puro por indicador) → `app.py` (rotas FastAPI, páginas Jinja2 + fragmentos
HTMX + JSON p/ Chart.js). `selectors.py` escolhe o agregado por janela e a
expressão de valor por métrica. `models.py` tipa os retornos.
```

- [ ] **Step 4: Run the full suite**

Run: `cd web-system && ./.venv/bin/python -m pytest -v`
Expected: PASS — all tests across `test_config`, `test_db`, `test_selectors`, `test_queries_*`, `test_app_*`.

- [ ] **Step 5: Update root the project guidance file**

In root `the project guidance file`, under a `web-system` note (add if absent), record: run `cd web-system && ./.venv/bin/python main.py`; test `cd web-system && ./.venv/bin/python -m pytest -v`; needs `web-system/.env` with `DATABASE_URL` (git-ignored, never commit).

- [ ] **Step 6: Commit**

```bash
git add web-system/main.py web-system/Dockerfile web-system/.dockerignore web-system/README.md the project guidance file
git commit -m "web-system: entry point, Dockerfile, README, docs"
```

---

## Verification checklist (after all tasks)

- [ ] `cd web-system && ./.venv/bin/python -m pytest -v` — all green.
- [ ] With a valid `web-system/.env` and the simulador running, `./.venv/bin/python main.py`, open `http://127.0.0.1:8000`: KPIs populate, Operational Hub table refreshes, Performance chart draws with limit lines, `/sensor/101` renders. (Manual — needs live DB; not part of CI.)
- [ ] Stop the DB / use a bad `DATABASE_URL`: pages still render with the "sem conexão com o banco" banner instead of 500s.
- [ ] Confirm `.gitignore` covers `web-system/.env` and `web-system/.venv` before any commit that could include them.
```
