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
    assert gen.tick(T0) == []
    assert gen.tick(T0 + timedelta(seconds=5)) == []
    assert gen.tick(T0 + timedelta(seconds=25)) == []
