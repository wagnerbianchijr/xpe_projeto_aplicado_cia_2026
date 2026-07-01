-- Compression settings and lifecycle policies for raw readings.

ALTER TABLE sensor_reading SET (
    timescaledb.compress
  , timescaledb.compress_segmentby = 'sensor_id'
  , timescaledb.compress_orderby   = 'time DESC'
);

-- Compress chunks older than 7 days.
SELECT add_compression_policy('sensor_reading', INTERVAL '7 days');

-- Drop raw chunks older than 90 days.
SELECT add_retention_policy('sensor_reading', INTERVAL '90 days');
