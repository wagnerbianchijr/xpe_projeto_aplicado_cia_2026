from main import sleep_seconds


def test_sleep_seconds_aligns_to_next_tick():
    # 12s numa cadência de 5s -> próximo múltiplo é 15s -> dormir 3s.
    assert sleep_seconds(5.0, 12.0) == 3.0


def test_sleep_seconds_on_boundary_is_full_tick():
    # Exatamente num múltiplo -> espera um tick inteiro, nunca 0.
    assert sleep_seconds(5.0, 10.0) == 5.0
