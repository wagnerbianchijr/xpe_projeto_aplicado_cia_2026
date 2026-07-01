-- Seed: three production lines (one per product type) and their sensors.
-- 8 common sensors + 2 line-specific sensors per line = 30 sensors total.
-- sensor_id encodes line: line 1 -> 1xx, line 2 -> 2xx, line 3 -> 3xx.

INSERT INTO production_line (line_id, name, product_type, description) VALUES
    (1, 'Linha Sucos 01',            'suco',            'Linha de produção de sucos')
  , (2, 'Linha Águas Saborizadas 01','agua_saborizada', 'Linha de produção de águas saborizadas')
  , (3, 'Linha Chás Gelados 01',     'cha_gelado',      'Linha de produção de chás gelados');

-- Common sensors (present on every line). limits are operating ranges.
-- metric, unit, min, max templated per line below.
INSERT INTO sensor (sensor_id, line_id, metric, unit, min_limit, max_limit, sample_interval_s, description) VALUES
  -- Line 1 (sucos) common
    (101, 1, 'temperature',      '°C',    70.0, 95.0, 5, 'Temperatura de pasteurização')
  , (102, 1, 'pressure',         'bar',    1.0,  3.5, 5, 'Pressão da linha de enchimento')
  , (103, 1, 'flow',             'L/min', 20.0, 60.0, 5, 'Vazão de enchimento')
  , (104, 1, 'tank_level',       '%',     10.0, 95.0, 5, 'Nível do tanque de mistura')
  , (105, 1, 'line_speed',       'bpm',  200.0,600.0, 5, 'Velocidade da linha (garrafas/min)')
  , (106, 1, 'production_count', 'count',  0.0, NULL, 5, 'Contador acumulado de produção')
  , (107, 1, 'ph',               'pH',     3.0,  4.5, 5, 'pH do produto')
  , (108, 1, 'ambient_temp',     '°C',    15.0, 30.0, 5, 'Temperatura ambiente')
  -- Line 1 (sucos) specific
  , (109, 1, 'brix',             '°Bx',   10.0, 14.0, 5, 'Teor de açúcar (°Brix)')
  , (110, 1, 'turbidity',        'NTU',    0.0, 50.0, 5, 'Turbidez')
  -- Line 2 (águas saborizadas) common
  , (201, 2, 'temperature',      '°C',    70.0, 95.0, 5, 'Temperatura de pasteurização')
  , (202, 2, 'pressure',         'bar',    1.0,  3.5, 5, 'Pressão da linha de enchimento')
  , (203, 2, 'flow',             'L/min', 20.0, 60.0, 5, 'Vazão de enchimento')
  , (204, 2, 'tank_level',       '%',     10.0, 95.0, 5, 'Nível do tanque de mistura')
  , (205, 2, 'line_speed',       'bpm',  200.0,600.0, 5, 'Velocidade da linha (garrafas/min)')
  , (206, 2, 'production_count', 'count',  0.0, NULL, 5, 'Contador acumulado de produção')
  , (207, 2, 'ph',               'pH',     3.0,  4.5, 5, 'pH do produto')
  , (208, 2, 'ambient_temp',     '°C',    15.0, 30.0, 5, 'Temperatura ambiente')
  -- Line 2 (águas saborizadas) specific
  , (209, 2, 'co2',              'g/L',    4.0,  8.0, 5, 'CO2 dissolvido')
  , (210, 2, 'conductivity',     'µS/cm', 50.0,500.0, 5, 'Condutividade da água')
  -- Line 3 (chás gelados) common
  , (301, 3, 'temperature',      '°C',    70.0, 95.0, 5, 'Temperatura de pasteurização')
  , (302, 3, 'pressure',         'bar',    1.0,  3.5, 5, 'Pressão da linha de enchimento')
  , (303, 3, 'flow',             'L/min', 20.0, 60.0, 5, 'Vazão de enchimento')
  , (304, 3, 'tank_level',       '%',     10.0, 95.0, 5, 'Nível do tanque de mistura')
  , (305, 3, 'line_speed',       'bpm',  200.0,600.0, 5, 'Velocidade da linha (garrafas/min)')
  , (306, 3, 'production_count', 'count',  0.0, NULL, 5, 'Contador acumulado de produção')
  , (307, 3, 'ph',               'pH',     3.0,  6.0, 5, 'pH do produto')
  , (308, 3, 'ambient_temp',     '°C',    15.0, 30.0, 5, 'Temperatura ambiente')
  -- Line 3 (chás gelados) specific
  , (309, 3, 'infusion_temp',    '°C',    80.0, 98.0, 5, 'Temperatura de infusão')
  , (310, 3, 'turbidity',        'NTU',    0.0, 50.0, 5, 'Turbidez');
