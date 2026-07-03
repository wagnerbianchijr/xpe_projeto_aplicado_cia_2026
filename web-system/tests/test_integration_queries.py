"""Testes de integração contra um banco real.

Só rodam quando há um banco alcançável (DATABASE_URL definida via ambiente ou
web-system/.env E a conexão responde). Caso contrário são pulados — assim não
exigem banco vivo no CI nem falham quando o banco é privado (ex.: acessível só
de dentro da VPC). Executam o SQL de verdade — pegam erros que o FakeDatabase
não pega (ex.: tipos de parâmetro).
"""
import os

import psycopg
import pytest
from dotenv import load_dotenv

load_dotenv()

import queries
from db import Database, create_pool

DATABASE_URL = os.environ.get("DATABASE_URL")


def _db_reachable() -> bool:
    """Sonda rápida: o banco responde? Evita travar quando é privado/inacessível."""
    if not DATABASE_URL:
        return False
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=3):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_reachable(),
    reason="banco não alcançável (DATABASE_URL ausente ou privado); integração pulada",
)


@pytest.fixture
def db():
    pool = create_pool(DATABASE_URL)
    try:
        yield Database(pool)
    finally:
        pool.close()


def test_kpis_executes(db):
    result = queries.kpis(db)
    assert result.lines >= 0


def test_sensor_status_executes_without_line_filter(db):
    rows = queries.sensor_status(db, None)
    assert isinstance(rows, list)


def test_sensor_status_executes_with_line_filter(db):
    rows = queries.sensor_status(db, 1)
    assert isinstance(rows, list)


def test_failed_sensors_executes_without_line_filter(db):
    rows = queries.failed_sensors(db, None)
    assert isinstance(rows, list)


def test_violations_executes_without_line_filter(db):
    rows = queries.violations(db, None, 24 * 3600)
    assert isinstance(rows, list)


def test_timeseries_executes(db):
    rows = queries.timeseries(db, 101, "temperature", 3600)
    assert isinstance(rows, list)


def test_failing_sensors_executes(db):
    rows = queries.failing_sensors(db)
    assert isinstance(rows, list)


def test_line_overview_executes(db):
    rows = queries.line_overview(db)
    assert isinstance(rows, list) and len(rows) >= 1
