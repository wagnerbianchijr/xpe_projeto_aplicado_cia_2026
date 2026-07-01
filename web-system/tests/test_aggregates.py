from aggregates import pick_aggregate, value_expr


def test_pick_aggregate_boundaries():
    assert pick_aggregate(60) == "sensor_reading_1m"
    assert pick_aggregate(3600) == "sensor_reading_1m"
    assert pick_aggregate(3601) == "sensor_reading_15m"
    assert pick_aggregate(6 * 3600) == "sensor_reading_15m"
    assert pick_aggregate(6 * 3600 + 1) == "sensor_reading_30m"
    assert pick_aggregate(24 * 3600) == "sensor_reading_30m"
    assert pick_aggregate(24 * 3600 + 1) == "sensor_reading_1h"
    assert pick_aggregate(90 * 24 * 3600) == "sensor_reading_1h"


def test_value_expr_average_for_normal_metric():
    assert value_expr("temperature").as_string(None) == "sum_value / nullif(count_value, 0)"


def test_value_expr_throughput_for_production_count():
    assert value_expr("production_count").as_string(None) == "max_value - min_value"
