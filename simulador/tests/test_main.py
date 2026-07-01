from main import sleep_seconds


def test_sleep_seconds_aligns_to_next_tick():
    # 12s into a 5s cadence -> next boundary is 15s -> sleep 3s.
    assert sleep_seconds(5.0, 12.0) == 3.0


def test_sleep_seconds_on_boundary_is_full_tick():
    # Exactly on a boundary -> wait a whole tick, never 0.
    assert sleep_seconds(5.0, 10.0) == 5.0
