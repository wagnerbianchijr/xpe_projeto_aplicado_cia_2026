"""Testes de integração contra um banco real.

Só rodam quando DATABASE_URL está definida (via ambiente ou web-system/.env);
caso contrário são pulados, para não exigir banco vivo no CI. Executam o SQL de
verdade — pegam erros que o FakeDatabase não pega (ex.: tipos de parâmetro).
"""
import os

import pytest
from dotenv import load_dotenv

load_dotenv()

import queries
from db import Database, create_pool

DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="DATABASE_URL não definida; teste de integração pulado"
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
