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
