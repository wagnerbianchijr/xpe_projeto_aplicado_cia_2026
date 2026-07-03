-- Políticas de refresh (o pai atualiza antes do filho via offsets crescentes)
-- e retenção de 1 ano em cada nível de agregado.

-- 1m: atualiza os últimos 10 minutos a cada minuto.
SELECT add_continuous_aggregate_policy('sensor_reading_1m'
  , start_offset      => INTERVAL '10 minutes'
  , end_offset        => INTERVAL '1 minute'
  , schedule_interval => INTERVAL '1 minute');

-- 15m: atualiza as últimas 2 horas a cada 5 minutos.
SELECT add_continuous_aggregate_policy('sensor_reading_15m'
  , start_offset      => INTERVAL '2 hours'
  , end_offset        => INTERVAL '15 minutes'
  , schedule_interval => INTERVAL '5 minutes');

-- 30m: atualiza as últimas 4 horas a cada 15 minutos.
SELECT add_continuous_aggregate_policy('sensor_reading_30m'
  , start_offset      => INTERVAL '4 hours'
  , end_offset        => INTERVAL '30 minutes'
  , schedule_interval => INTERVAL '15 minutes');

-- 1h: atualiza as últimas 8 horas a cada 30 minutos.
SELECT add_continuous_aggregate_policy('sensor_reading_1h'
  , start_offset      => INTERVAL '8 hours'
  , end_offset        => INTERVAL '1 hour'
  , schedule_interval => INTERVAL '30 minutes');

-- Retém cada nível de agregado por 1 ano.
SELECT add_retention_policy('sensor_reading_1m',  INTERVAL '1 year');
SELECT add_retention_policy('sensor_reading_15m', INTERVAL '1 year');
SELECT add_retention_policy('sensor_reading_30m', INTERVAL '1 year');
SELECT add_retention_policy('sensor_reading_1h',  INTERVAL '1 year');
