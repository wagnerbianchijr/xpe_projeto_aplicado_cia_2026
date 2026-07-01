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
