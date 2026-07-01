# Simulador IIoT (Python) Implementation Plan


**Goal:** Build a Python process that continuously generates realistic IIoT sensor readings (mean-reverting random walk + rare anomalies + dropouts) and writes them every 5 seconds to the `sensor_reading` hypertable on the Tiger Cloud service `h3bmabyk97`.

**Architecture:** Modules split by responsibility. `generator.py` is pure (no I/O, injected RNG) and holds the value model and per-sensor state; `config.py`/`catalog.py`/`writer.py` isolate configuration and all database I/O; `main.py` owns the timed loop and signal handling. Credentials come from a git-ignored `.env`.

**Tech Stack:** Python 3.11+, psycopg 3, python-dotenv, pytest.

---

## Conventions

- All commands run from the component directory: `cd "simulador"` unless stated otherwise.
- Modules are flat inside `simulador/`; tests live in `simulador/tests/`. `pytest.ini` sets `pythonpath = .` so tests import `config`, `generator`, etc.
- The database password is NEVER committed. It lives only in `simulador/.env` (git-ignored). `.env.example` documents the keys with placeholders. This plan intentionally does NOT contain the password.
- Commit after each task. Do NOT push (the controller pushes).
- Connection string for the smoke test (Task 7): host `h3bmabyk97.tgqtelaqv0.db.az.tigerdata.com`, port `31836`, user `tsdbadmin`, db `tsdb`, `sslmode=require`. The password is supplied out-of-band by the controller/user at execution time — never write it into this file or any committed file.

## File Structure

- Create: `simulador/requirements.txt` — dependencies
- Create: `simulador/pytest.ini` — pytest config (`pythonpath = .`)
- Create: `simulador/.env.example` — config template (committed)
- Modify: `.gitignore` — ignore `.env`, `__pycache__`, venvs
- Create: `simulador/config.py` — `Settings` dataclass + `load_settings()`
- Create: `simulador/catalog.py` — `SensorSpec` dataclass + `load_catalog(conn)`
- Create: `simulador/generator.py` — `Reading`, `SensorState`, `Generator` (pure value model)
- Create: `simulador/writer.py` — `insert_readings(conn, readings)`
- Create: `simulador/main.py` — timed loop, SIGINT, reconnect, `sleep_seconds`
- Create: `simulador/tests/test_config.py`, `tests/test_generator.py`, `tests/test_writer.py`, `tests/test_main.py`
- Create: `simulador/README.md` — how to run

---

### Task 1: Scaffold (deps, config template, gitignore, venv)

**Files:**
- Create: `simulador/requirements.txt`
- Create: `simulador/pytest.ini`
- Create: `simulador/.env.example`
- Modify: `.gitignore`

- [ ] **Step 1: Write `simulador/requirements.txt`**
```
psycopg[binary]>=3.1
python-dotenv>=1.0
pytest>=8.0
```

- [ ] **Step 2: Write `simulador/pytest.ini`**
```ini
[pytest]
pythonpath = .
testpaths = tests
```

- [ ] **Step 3: Write `simulador/.env.example`**
```
# Copy this file to .env and fill in real values. .env is git-ignored.
# psycopg DSN for the Tiger Cloud service (password stays here only).
DATABASE_URL=postgresql://tsdbadmin:PASSWORD@HOST:PORT/tsdb?sslmode=require

# Optional overrides (defaults shown):
TICK_SECONDS=5
# SEED=42
P_ANOMALY=0.005
P_DROPOUT=0.002
```

- [ ] **Step 4: Append Python + secrets rules to the repo-root `.gitignore`**

Add these lines to `.gitignore` (keep existing content):
```
# Python
__pycache__/
*.pyc
.venv/
venv/

# Secrets
.env
simulador/.env
```

- [ ] **Step 5: Create venv and install deps**

Run:
```bash
cd "simulador" && python3 -m venv .venv && ./.venv/bin/pip install -q -r requirements.txt && ./.venv/bin/python -c "import psycopg, dotenv, pytest; print('deps ok')"
```
Expected: prints `deps ok`.

- [ ] **Step 6: Verify pytest runs (no tests yet)**

Run: `cd "simulador" && ./.venv/bin/python -m pytest -q`
Expected: exits cleanly with "no tests ran".

- [ ] **Step 7: Commit**
```bash
git add simulador/requirements.txt simulador/pytest.ini simulador/.env.example .gitignore
git commit -m "simulador: scaffold deps, pytest config, env template, gitignore"
```

---

### Task 2: Configuration (`config.py`)

**Files:**
- Create: `simulador/config.py`
- Create: `simulador/tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Create `simulador/tests/test_config.py`:
```python
import pytest

from config import load_settings


def test_load_settings_reads_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("TICK_SECONDS", "5")
    monkeypatch.setenv("P_ANOMALY", "0.01")
    monkeypatch.setenv("P_DROPOUT", "0.02")
    monkeypatch.setenv("SEED", "42")

    settings = load_settings(load_env=False)

    assert settings.database_url == "postgresql://x"
    assert settings.tick_seconds == 5.0
    assert settings.p_anomaly == 0.01
    assert settings.p_dropout == 0.02
    assert settings.seed == 42


def test_defaults_applied(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.delenv("TICK_SECONDS", raising=False)
    monkeypatch.delenv("P_ANOMALY", raising=False)
    monkeypatch.delenv("P_DROPOUT", raising=False)
    monkeypatch.delenv("SEED", raising=False)

    settings = load_settings(load_env=False)

    assert settings.tick_seconds == 5.0
    assert settings.p_anomaly == 0.005
    assert settings.p_dropout == 0.002
    assert settings.seed is None


def test_missing_database_url_raises(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        load_settings(load_env=False)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "simulador" && ./.venv/bin/python -m pytest tests/test_config.py -q`
Expected: FAIL (ImportError / module `config` has no `load_settings`).

- [ ] **Step 3: Write `simulador/config.py`**
```python
"""Configuration loaded from environment (.env is git-ignored)."""
from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_url: str
    tick_seconds: float
    seed: int | None
    p_anomaly: float
    p_dropout: float


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
            "DATABASE_URL is required. Copy simulador/.env.example to "
            "simulador/.env and set it."
        )

    seed_raw = os.environ.get("SEED")
    return Settings(
        database_url=database_url,
        tick_seconds=float(os.environ.get("TICK_SECONDS", "5")),
        seed=int(seed_raw) if seed_raw else None,
        p_anomaly=float(os.environ.get("P_ANOMALY", "0.005")),
        p_dropout=float(os.environ.get("P_DROPOUT", "0.002")),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "simulador" && ./.venv/bin/python -m pytest tests/test_config.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**
```bash
git add simulador/config.py simulador/tests/test_config.py
git commit -m "simulador: add env-based configuration loader"
```

---

### Task 3: Sensor catalog (`catalog.py`)

**Files:**
- Create: `simulador/catalog.py`
- Create: `simulador/tests/test_catalog.py`

- [ ] **Step 1: Write the failing test**

Create `simulador/tests/test_catalog.py`:
```python
from catalog import SensorSpec, load_catalog


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql):
        self.sql = sql

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return _FakeCursor(self._rows)


def test_sensor_spec_fields():
    spec = SensorSpec(101, 1, "temperature", 70.0, 95.0)
    assert spec.sensor_id == 101
    assert spec.line_id == 1
    assert spec.metric == "temperature"
    assert spec.min_limit == 70.0
    assert spec.max_limit == 95.0


def test_load_catalog_maps_rows_to_specs():
    rows = [
        (101, 1, "temperature", 70.0, 95.0),
        (106, 1, "production_count", 0.0, None),
    ]
    specs = load_catalog(_FakeConn(rows))
    assert specs == [
        SensorSpec(101, 1, "temperature", 70.0, 95.0),
        SensorSpec(106, 1, "production_count", 0.0, None),
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "simulador" && ./.venv/bin/python -m pytest tests/test_catalog.py -q`
Expected: FAIL (module `catalog` not found).

- [ ] **Step 3: Write `simulador/catalog.py`**
```python
"""Load the sensor catalog (dimension table) from the database."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SensorSpec:
    sensor_id: int
    line_id: int
    metric: str
    min_limit: float | None
    max_limit: float | None


def load_catalog(conn) -> list[SensorSpec]:
    """Read every sensor's identity and operating limits, ordered by id."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT sensor_id, line_id, metric, min_limit, max_limit "
            "FROM sensor ORDER BY sensor_id"
        )
        return [SensorSpec(*row) for row in cur.fetchall()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "simulador" && ./.venv/bin/python -m pytest tests/test_catalog.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**
```bash
git add simulador/catalog.py simulador/tests/test_catalog.py
git commit -m "simulador: add sensor catalog loader"
```

---

### Task 4: Value generator (`generator.py`) — the core model

**Files:**
- Create: `simulador/generator.py`
- Create: `simulador/tests/test_generator.py`

This is the pure value model. Write all tests first, watch them fail, then implement.

- [ ] **Step 1: Write the failing tests**

Create `simulador/tests/test_generator.py`:
```python
import random
from datetime import datetime, timedelta, timezone

from catalog import SensorSpec
from generator import Generator, Reading, COUNTER_METRIC

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def temp_spec():
    return SensorSpec(101, 1, "temperature", 70.0, 95.0)


def counter_spec():
    return SensorSpec(106, 1, COUNTER_METRIC, 0.0, None)


def _values(gen, n, start=T0, step_s=5):
    out = []
    for i in range(n):
        readings = gen.tick(start + timedelta(seconds=step_s * i))
        out.append(readings)
    return out


def test_tick_returns_one_reading_per_active_sensor():
    gen = Generator([temp_spec()], random.Random(1), p_anomaly=0, p_dropout=0)
    readings = gen.tick(T0)
    assert len(readings) == 1
    assert isinstance(readings[0], Reading)
    assert readings[0].sensor_id == 101
    assert readings[0].time == T0
    assert readings[0].quality == 0


def test_determinism_same_seed_same_output():
    specs = [temp_spec()]
    g1 = Generator(specs, random.Random(42), p_anomaly=0, p_dropout=0)
    g2 = Generator(specs, random.Random(42), p_anomaly=0, p_dropout=0)
    v1 = [t[0].value for t in _values(g1, 20)]
    v2 = [t[0].value for t in _values(g2, 20)]
    assert v1 == v2


def test_counter_is_strictly_monotonic():
    gen = Generator([counter_spec()], random.Random(1), p_anomaly=0, p_dropout=0)
    vals = [t[0].value for t in _values(gen, 50)]
    assert vals[0] > 0
    assert all(b > a for a, b in zip(vals, vals[1:]))


def test_random_walk_stays_within_slack_bounds():
    spec = temp_spec()
    gen = Generator([spec], random.Random(7), p_anomaly=0, p_dropout=0)
    span = spec.max_limit - spec.min_limit
    slack = span * 0.1
    for t in _values(gen, 2000):
        value = t[0].value
        assert spec.min_limit - slack <= value <= spec.max_limit + slack


def test_mean_reversion_keeps_average_near_baseline():
    spec = temp_spec()
    baseline = (spec.min_limit + spec.max_limit) / 2
    gen = Generator([spec], random.Random(3), p_anomaly=0, p_dropout=0)
    vals = [t[0].value for t in _values(gen, 3000)]
    avg = sum(vals) / len(vals)
    assert abs(avg - baseline) < (spec.max_limit - spec.min_limit) * 0.15


def test_anomaly_forces_value_out_of_range():
    spec = temp_spec()
    gen = Generator([spec], random.Random(1), p_anomaly=1.0, p_dropout=0)
    value = gen.tick(T0)[0].value
    assert value < spec.min_limit or value > spec.max_limit


def test_dropout_suppresses_emissions_for_the_window():
    spec = temp_spec()
    gen = Generator(
        [spec], random.Random(1), p_anomaly=0, p_dropout=1.0,
        dropout_min_s=30, dropout_max_s=30,
    )
    # First tick starts a dropout -> nothing emitted.
    assert gen.tick(T0) == []
    # Every tick inside the 30s window is also silent.
    assert gen.tick(T0 + timedelta(seconds=5)) == []
    assert gen.tick(T0 + timedelta(seconds=25)) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "simulador" && ./.venv/bin/python -m pytest tests/test_generator.py -q`
Expected: FAIL (module `generator` not found).

- [ ] **Step 3: Write `simulador/generator.py`**
```python
"""Pure IIoT value model: per-sensor mean-reverting random walk with rare
anomalies and dropouts. No database or wall-clock access — all randomness is
injected so behavior is deterministic under a seeded RNG."""
from dataclasses import dataclass
from datetime import datetime, timedelta

from catalog import SensorSpec

COUNTER_METRIC = "production_count"

_STEP_FRAC = 0.02       # random-walk step stddev as a fraction of the range
_REVERT_FRAC = 0.05     # pull toward baseline each tick
_SLACK_FRAC = 0.10      # how far past the limits a normal value may wander
_ANOMALY_FRAC = (0.05, 0.20)  # how far past a limit an anomaly is pushed


@dataclass
class Reading:
    time: datetime
    sensor_id: int
    value: float
    quality: int = 0


@dataclass
class SensorState:
    last_value: float
    dropout_until: datetime | None = None
    counter: float = 0.0


class Generator:
    def __init__(
        self,
        specs,
        rng,
        p_anomaly: float = 0.005,
        p_dropout: float = 0.002,
        dropout_min_s: float = 30.0,
        dropout_max_s: float = 120.0,
    ):
        self._specs = list(specs)
        self._rng = rng
        self._p_anomaly = p_anomaly
        self._p_dropout = p_dropout
        self._dropout_min_s = dropout_min_s
        self._dropout_max_s = dropout_max_s
        self._state: dict[int, SensorState] = {
            spec.sensor_id: SensorState(last_value=self._baseline(spec))
            for spec in self._specs
        }

    @staticmethod
    def _baseline(spec: SensorSpec) -> float:
        if spec.min_limit is not None and spec.max_limit is not None:
            return (spec.min_limit + spec.max_limit) / 2
        return 0.0

    def tick(self, now: datetime) -> list[Reading]:
        readings: list[Reading] = []
        for spec in self._specs:
            state = self._state[spec.sensor_id]

            # 1. Currently dropped out -> stay silent until the window ends.
            if state.dropout_until is not None:
                if now < state.dropout_until:
                    continue
                state.dropout_until = None

            # 2. Maybe start a new dropout.
            if self._rng.random() < self._p_dropout:
                secs = self._rng.uniform(self._dropout_min_s, self._dropout_max_s)
                state.dropout_until = now + timedelta(seconds=secs)
                continue

            # 3. Monotonic counter (production_count) ignores the random walk.
            if spec.metric == COUNTER_METRIC:
                state.counter += self._rng.randint(1, 8)
                readings.append(Reading(now, spec.sensor_id, state.counter))
                continue

            # 4. Mean-reverting random walk, clamped to limits + slack.
            span = spec.max_limit - spec.min_limit
            baseline = self._baseline(spec)
            step = self._rng.gauss(0, span * _STEP_FRAC)
            pulled = state.last_value + step + (baseline - state.last_value) * _REVERT_FRAC
            slack = span * _SLACK_FRAC
            value = min(max(pulled, spec.min_limit - slack), spec.max_limit + slack)

            # 5. Rare anomaly pushes the value out of range (drives 'alerta').
            if self._rng.random() < self._p_anomaly:
                value = self._anomaly(spec, span)

            state.last_value = value
            readings.append(Reading(now, spec.sensor_id, value))
        return readings

    def _anomaly(self, spec: SensorSpec, span: float) -> float:
        lo, hi = _ANOMALY_FRAC
        overshoot = self._rng.uniform(lo, hi) * span
        if self._rng.random() < 0.5:
            return spec.min_limit - overshoot
        return spec.max_limit + overshoot
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "simulador" && ./.venv/bin/python -m pytest tests/test_generator.py -q`
Expected: 7 passed.

- [ ] **Step 5: Commit**
```bash
git add simulador/generator.py simulador/tests/test_generator.py
git commit -m "simulador: add pure value generator (random walk + anomalies + dropouts)"
```

---

### Task 5: Batch writer (`writer.py`)

**Files:**
- Create: `simulador/writer.py`
- Create: `simulador/tests/test_writer.py`

- [ ] **Step 1: Write the failing tests**

Create `simulador/tests/test_writer.py`:
```python
from datetime import datetime, timezone

from generator import Reading
from writer import insert_readings

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


class _FakeCursor:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def executemany(self, sql, rows):
        self.calls.append((sql, rows))


class _FakeConn:
    def __init__(self):
        self.cur = _FakeCursor()
        self.committed = False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True


def test_insert_readings_batches_rows_and_commits():
    conn = _FakeConn()
    readings = [Reading(T0, 101, 85.0, 0), Reading(T0, 102, 5.0, 0)]

    n = insert_readings(conn, readings)

    assert n == 2
    assert conn.committed is True
    sql, rows = conn.cur.calls[0]
    assert "INSERT INTO sensor_reading" in sql
    assert rows == [(T0, 101, 85.0, 0), (T0, 102, 5.0, 0)]


def test_insert_readings_empty_is_noop():
    conn = _FakeConn()
    n = insert_readings(conn, [])
    assert n == 0
    assert conn.committed is False
    assert conn.cur.calls == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "simulador" && ./.venv/bin/python -m pytest tests/test_writer.py -q`
Expected: FAIL (module `writer` not found).

- [ ] **Step 3: Write `simulador/writer.py`**
```python
"""Persist generated readings to the sensor_reading hypertable."""

_INSERT_SQL = (
    "INSERT INTO sensor_reading (time, sensor_id, value, quality) "
    "VALUES (%s, %s, %s, %s)"
)


def insert_readings(conn, readings) -> int:
    """Insert a tick's readings in one transaction. Returns rows written."""
    if not readings:
        return 0
    rows = [(r.time, r.sensor_id, r.value, r.quality) for r in readings]
    with conn.cursor() as cur:
        cur.executemany(_INSERT_SQL, rows)
    conn.commit()
    return len(rows)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "simulador" && ./.venv/bin/python -m pytest tests/test_writer.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**
```bash
git add simulador/writer.py simulador/tests/test_writer.py
git commit -m "simulador: add batch reading writer"
```

---

### Task 6: Timed loop and orchestration (`main.py`)

**Files:**
- Create: `simulador/main.py`
- Create: `simulador/tests/test_main.py`

- [ ] **Step 1: Write the failing test**

Create `simulador/tests/test_main.py`:
```python
from main import sleep_seconds


def test_sleep_seconds_aligns_to_next_tick():
    # 12s into a 5s cadence -> next boundary is 15s -> sleep 3s.
    assert sleep_seconds(5.0, 12.0) == 3.0


def test_sleep_seconds_on_boundary_is_full_tick():
    # Exactly on a boundary -> wait a whole tick, never 0.
    assert sleep_seconds(5.0, 10.0) == 5.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "simulador" && ./.venv/bin/python -m pytest tests/test_main.py -q`
Expected: FAIL (module `main` not found / no `sleep_seconds`).

- [ ] **Step 3: Write `simulador/main.py`**
```python
"""Continuous IIoT simulator: every tick, generate readings and write them.

Run:  python main.py     (reads simulador/.env for DATABASE_URL)
Stop: Ctrl+C             (clean shutdown)
"""
import random
import signal
import sys
import time
from datetime import datetime, timezone

import psycopg

from catalog import load_catalog
from config import load_settings
from generator import Generator
from writer import insert_readings

_running = True


def _handle_sigint(signum, frame):
    global _running
    _running = False


def sleep_seconds(tick: float, monotonic_now: float) -> float:
    """Seconds to sleep so ticks land on multiples of `tick` (no drift)."""
    remainder = monotonic_now % tick
    return tick - remainder if remainder else tick


def _reconnect(dsn: str, attempts: int = 5) -> "psycopg.Connection":
    delay = 1.0
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return psycopg.connect(dsn)
        except psycopg.OperationalError as error:
            last_error = error
            time.sleep(delay)
            delay = min(delay * 2, 30.0)
    raise RuntimeError(f"could not reconnect after {attempts} attempts") from last_error


def main() -> int:
    settings = load_settings()
    rng = random.Random(settings.seed)
    signal.signal(signal.SIGINT, _handle_sigint)

    conn = psycopg.connect(settings.database_url)
    specs = load_catalog(conn)
    generator = Generator(
        specs, rng, p_anomaly=settings.p_anomaly, p_dropout=settings.p_dropout
    )
    print(
        f"simulador: {len(specs)} sensors, tick={settings.tick_seconds}s. Ctrl+C to stop."
    )

    while _running:
        now = datetime.now(timezone.utc)
        readings = generator.tick(now)
        try:
            written = insert_readings(conn, readings)
        except psycopg.OperationalError as error:
            print(f"db error: {error}; reconnecting...", file=sys.stderr)
            conn = _reconnect(settings.database_url)
            continue
        print(f"{now.isoformat()} wrote {written} readings")
        time.sleep(sleep_seconds(settings.tick_seconds, time.monotonic()))

    conn.close()
    print("simulador: stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "simulador" && ./.venv/bin/python -m pytest tests/test_main.py -q`
Expected: 2 passed.

- [ ] **Step 5: Run the full suite**

Run: `cd "simulador" && ./.venv/bin/python -m pytest -q`
Expected: all tests pass (config 3 + catalog 2 + generator 7 + writer 2 + main 2 = 16).

- [ ] **Step 6: Commit**
```bash
git add simulador/main.py simulador/tests/test_main.py
git commit -m "simulador: add timed loop, signal handling, and reconnect"
```

---

### Task 7: Live smoke test against Tiger Cloud + README

**Files:**
- Create: `simulador/.env` (LOCAL ONLY — must NOT be committed; it is git-ignored)
- Create: `simulador/README.md`

- [ ] **Step 1: Create the local `.env` (never committed)**

Create `simulador/.env` using the DSN supplied by the controller at execution time
(host/port/user/db from the Conventions section + the password provided out-of-band):
```
DATABASE_URL=postgresql://tsdbadmin:<PASSWORD>@h3bmabyk97.tgqtelaqv0.db.az.tigerdata.com:31836/tsdb?sslmode=require
SEED=42
```
Then confirm git ignores it: `cd "simulador" && git check-ignore .env` → expected output: `.env`.
If `.env` is NOT ignored, STOP and fix `.gitignore` before continuing.

- [ ] **Step 2: Record the baseline row count**

Run:
```bash
cd "simulador" && ./.venv/bin/python -c "import psycopg, os; from dotenv import load_dotenv; load_dotenv(); c=psycopg.connect(os.environ['DATABASE_URL']); cur=c.cursor(); cur.execute('SELECT count(*) FROM sensor_reading'); print('before', cur.fetchone()[0])"
```
Expected: `before 0` (the table was left empty by the modelo-de-dados smoke test).

- [ ] **Step 3: Run the simulator for a few ticks, then stop it**

Run (runs ~12s, i.e. 2–3 ticks, then sends Ctrl+C):
```bash
cd "simulador" && ( ./.venv/bin/python main.py & PID=$!; sleep 12; kill -INT $PID; wait $PID )
```
Expected: log lines like `... wrote 30 readings` (a couple of them), then `simulador: stopped`.

- [ ] **Step 4: Verify rows landed and views react**

Run:
```bash
cd "simulador" && ./.venv/bin/python -c "
import psycopg, os
from dotenv import load_dotenv
load_dotenv()
c = psycopg.connect(os.environ['DATABASE_URL'])
cur = c.cursor()
cur.execute('SELECT count(*) FROM sensor_reading')
print('rows', cur.fetchone()[0])
cur.execute(\"SELECT count(*) FROM sensor_status WHERE status <> 'sem_dados'\")
print('sensors_reporting', cur.fetchone()[0])
cur.execute('SELECT count(*) FROM sensor_liveness WHERE is_failed = false')
print('live_sensors', cur.fetchone()[0])
"
```
Expected: `rows` > 0; `sensors_reporting` > 0 (close to 30); `live_sensors` > 0. This proves writes work end-to-end and the modelo-de-dados views react to live data.

- [ ] **Step 5: Clean up the smoke data (leave the table empty)**

Run:
```bash
cd "simulador" && ./.venv/bin/python -c "import psycopg, os; from dotenv import load_dotenv; load_dotenv(); c=psycopg.connect(os.environ['DATABASE_URL']); c.cursor().execute('TRUNCATE sensor_reading'); c.commit(); print('truncated')"
```
Expected: `truncated`. (Leave the table clean; the user can run `python main.py` whenever they want live data.)

- [ ] **Step 6: Write `simulador/README.md`**
```markdown
# simulador

Continuous IIoT data generator ("PLC") for the Serra Clara Bebidas solution. Every
5 seconds it generates one reading per sensor (mean-reverting random walk, with rare
anomalies and dropouts) and writes them to `sensor_reading` on the Tiger Cloud service.

## Setup

```bash
cd simulador
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env      # then edit .env and set DATABASE_URL (never committed)
```

## Run

```bash
./.venv/bin/python main.py     # Ctrl+C to stop
```

## Test

```bash
./.venv/bin/python -m pytest -q
```

## Configuration (.env)

- `DATABASE_URL` — psycopg DSN for the Tiger Cloud service (required).
- `TICK_SECONDS` — seconds between ticks (default 5).
- `SEED` — optional RNG seed for reproducible runs.
- `P_ANOMALY` — per-reading probability of an out-of-range value (default 0.005).
- `P_DROPOUT` — per-reading probability a sensor goes silent (default 0.002).

## Modules

- `generator.py` — pure value model (no I/O); fully unit-tested.
- `catalog.py` / `writer.py` — database reads/writes.
- `config.py` — env-based settings.
- `main.py` — timed loop, signal handling, reconnect.
```

- [ ] **Step 7: Confirm no secrets are staged, then commit the README**

Run: `cd "simulador" && git status --porcelain` — confirm `.env` is NOT listed.
```bash
git add simulador/README.md
git commit -m "simulador: add README and record verified live write smoke test"
```

---

## Notes for the implementer

- **Never commit `simulador/.env`.** Task 1 adds it to `.gitignore`; Task 7 Step 1 and Step 7 double-check. If `git status` ever shows `.env`, stop and fix.
- **`generator.py` stays pure.** No `psycopg`, no `datetime.now()` inside it — the caller passes `now`. This is what makes the tests deterministic. Do not "optimize" by moving the clock inside.
- **All non-counter seeded sensors have both limits**, so the random-walk branch never sees a `None` limit. `production_count` (NULL max) is handled earlier by the counter branch.
- **Volume is tiny** (~30 rows/5s); `executemany` is fine. Do not add COPY or async — YAGNI.
