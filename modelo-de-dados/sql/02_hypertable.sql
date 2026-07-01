-- Fact hypertable: raw sensor readings.

CREATE TABLE sensor_reading (
    time       timestamptz      NOT NULL
  , sensor_id  int              NOT NULL REFERENCES sensor (sensor_id)
  , value      double precision NOT NULL
  , quality    smallint         NOT NULL DEFAULT 0
);

SELECT create_hypertable(
    'sensor_reading'
  , 'time'
  , chunk_time_interval => INTERVAL '12 hours'
);

CREATE INDEX sensor_reading_sensor_time_idx
    ON sensor_reading (sensor_id, time DESC);
