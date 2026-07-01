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
