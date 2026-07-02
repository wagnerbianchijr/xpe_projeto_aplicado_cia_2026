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
