-- Refresh policies (parent refreshes before child via increasing offsets)
-- and 1-year retention on every aggregate level.

-- 1m: refresh the last 10 minutes every minute.
SELECT add_continuous_aggregate_policy('sensor_reading_1m'
  , start_offset      => INTERVAL '10 minutes'
  , end_offset        => INTERVAL '1 minute'
  , schedule_interval => INTERVAL '1 minute');

-- 15m: refresh the last 2 hours every 5 minutes.
SELECT add_continuous_aggregate_policy('sensor_reading_15m'
  , start_offset      => INTERVAL '2 hours'
  , end_offset        => INTERVAL '15 minutes'
  , schedule_interval => INTERVAL '5 minutes');

-- 30m: refresh the last 4 hours every 15 minutes.
SELECT add_continuous_aggregate_policy('sensor_reading_30m'
  , start_offset      => INTERVAL '4 hours'
  , end_offset        => INTERVAL '30 minutes'
  , schedule_interval => INTERVAL '15 minutes');

-- 1h: refresh the last 8 hours every 30 minutes.
SELECT add_continuous_aggregate_policy('sensor_reading_1h'
  , start_offset      => INTERVAL '8 hours'
  , end_offset        => INTERVAL '1 hour'
  , schedule_interval => INTERVAL '30 minutes');

-- Retain every aggregate level for 1 year.
SELECT add_retention_policy('sensor_reading_1m',  INTERVAL '1 year');
SELECT add_retention_policy('sensor_reading_15m', INTERVAL '1 year');
SELECT add_retention_policy('sensor_reading_30m', INTERVAL '1 year');
SELECT add_retention_policy('sensor_reading_1h',  INTERVAL '1 year');
