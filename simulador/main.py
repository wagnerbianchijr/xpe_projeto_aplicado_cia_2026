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
        except (psycopg.OperationalError, psycopg.InterfaceError) as error:
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
