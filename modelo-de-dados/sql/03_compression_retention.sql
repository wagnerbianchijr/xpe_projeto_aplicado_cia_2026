-- Configuração de compressão e políticas de ciclo de vida das leituras cruas.

ALTER TABLE sensor_reading SET (
    timescaledb.compress
  , timescaledb.compress_segmentby = 'sensor_id'
  , timescaledb.compress_orderby   = 'time DESC'
);

-- Comprime chunks com mais de 7 dias.
SELECT add_compression_policy('sensor_reading', INTERVAL '7 days');

-- Remove chunks crus com mais de 90 dias.
SELECT add_retention_policy('sensor_reading', INTERVAL '90 days');
