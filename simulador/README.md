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

## Status

Complete. Full unit suite (16 tests) passes. Live write smoke test against service
`h3bmabyk97` verified: a short run wrote 120 rows across all 30 sensors,
`sensor_status` classified them (normal + alerta), and `sensor_liveness` correctly
flags sensors as failed once they stop reporting. `sensor_reading` is left empty; run
`python main.py` to stream live data.
