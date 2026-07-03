-- Seed: três linhas de produção (uma por tipo de produto) e seus sensores.
-- 8 sensores comuns + 2 sensores específicos por linha = 30 sensores no total.
-- sensor_id codifica a linha: linha 1 -> 1xx, linha 2 -> 2xx, linha 3 -> 3xx.

INSERT INTO production_line (line_id, name, product_type, description) VALUES
    (1, 'Linha Sucos 01',            'suco',            'Linha de produção de sucos')
  , (2, 'Linha Águas Saborizadas 01','agua_saborizada', 'Linha de produção de águas saborizadas')
  , (3, 'Linha Chás Gelados 01',     'cha_gelado',      'Linha de produção de chás gelados');

-- Sensores comuns (presentes em toda linha). limits são faixas operacionais.
-- metric, unit, min, max modelados por linha abaixo.
INSERT INTO sensor (sensor_id, line_id, metric, unit, min_limit, max_limit, sample_interval_s, description) VALUES
  -- Linha 1 (sucos) comuns
    (101, 1, 'temperature',      '°C',    70.0, 95.0, 5, 'Temperatura de pasteurização')
  , (102, 1, 'pressure',         'bar',    1.0,  3.5, 5, 'Pressão da linha de enchimento')
  , (103, 1, 'flow',             'L/min', 20.0, 60.0, 5, 'Vazão de enchimento')
  , (104, 1, 'tank_level',       '%',     10.0, 95.0, 5, 'Nível do tanque de mistura')
  , (105, 1, 'line_speed',       'bpm',  200.0,600.0, 5, 'Velocidade da linha (garrafas/min)')
  , (106, 1, 'production_count', 'count',  0.0, NULL, 5, 'Contador acumulado de produção')
  , (107, 1, 'ph',               'pH',     3.0,  4.5, 5, 'pH do produto')
  , (108, 1, 'ambient_temp',     '°C',    15.0, 30.0, 5, 'Temperatura ambiente')
  -- Linha 1 (sucos) específicos
  , (109, 1, 'brix',             '°Bx',   10.0, 14.0, 5, 'Teor de açúcar (°Brix)')
  , (110, 1, 'turbidity',        'NTU',    0.0, 50.0, 5, 'Turbidez')
  -- Linha 2 (águas saborizadas) comuns
  , (201, 2, 'temperature',      '°C',    70.0, 95.0, 5, 'Temperatura de pasteurização')
  , (202, 2, 'pressure',         'bar',    1.0,  3.5, 5, 'Pressão da linha de enchimento')
  , (203, 2, 'flow',             'L/min', 20.0, 60.0, 5, 'Vazão de enchimento')
  , (204, 2, 'tank_level',       '%',     10.0, 95.0, 5, 'Nível do tanque de mistura')
  , (205, 2, 'line_speed',       'bpm',  200.0,600.0, 5, 'Velocidade da linha (garrafas/min)')
  , (206, 2, 'production_count', 'count',  0.0, NULL, 5, 'Contador acumulado de produção')
  , (207, 2, 'ph',               'pH',     3.0,  4.5, 5, 'pH do produto')
  , (208, 2, 'ambient_temp',     '°C',    15.0, 30.0, 5, 'Temperatura ambiente')
  -- Linha 2 (águas saborizadas) específicos
  , (209, 2, 'co2',              'g/L',    4.0,  8.0, 5, 'CO2 dissolvido')
  , (210, 2, 'conductivity',     'µS/cm', 50.0,500.0, 5, 'Condutividade da água')
  -- Linha 3 (chás gelados) comuns
  , (301, 3, 'temperature',      '°C',    70.0, 95.0, 5, 'Temperatura de pasteurização')
  , (302, 3, 'pressure',         'bar',    1.0,  3.5, 5, 'Pressão da linha de enchimento')
  , (303, 3, 'flow',             'L/min', 20.0, 60.0, 5, 'Vazão de enchimento')
  , (304, 3, 'tank_level',       '%',     10.0, 95.0, 5, 'Nível do tanque de mistura')
  , (305, 3, 'line_speed',       'bpm',  200.0,600.0, 5, 'Velocidade da linha (garrafas/min)')
  , (306, 3, 'production_count', 'count',  0.0, NULL, 5, 'Contador acumulado de produção')
  , (307, 3, 'ph',               'pH',     3.0,  6.0, 5, 'pH do produto')
  , (308, 3, 'ambient_temp',     '°C',    15.0, 30.0, 5, 'Temperatura ambiente')
  -- Linha 3 (chás gelados) específicos
  , (309, 3, 'infusion_temp',    '°C',    80.0, 98.0, 5, 'Temperatura de infusão')
  , (310, 3, 'turbidity',        'NTU',    0.0, 50.0, 5, 'Turbidez');
