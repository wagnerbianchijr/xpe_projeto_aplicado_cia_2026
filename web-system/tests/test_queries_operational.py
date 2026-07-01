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
