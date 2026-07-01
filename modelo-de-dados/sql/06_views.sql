-- Support views for the web dashboard.

-- Real-time status: latest raw reading per sensor vs its operating limits.
-- NULL-limit intent: production_count sensors have max_limit = NULL (no upper
-- bound). `value > NULL` is NULL, so the alerta branch is skipped and they read
-- 'normal' unless value < min_limit (0). This is deliberate; do not COALESCE
-- max_limit to +inf "to fix" it.
CREATE VIEW sensor_status AS
SELECT
    s.sensor_id
  , s.line_id
  , s.metric
  , s.unit
  , lr.value
  , lr.time AS last_time
  , CASE
        WHEN lr.value IS NULL                                   THEN 'sem_dados'
        WHEN lr.value < s.min_limit OR lr.value > s.max_limit   THEN 'alerta'
        ELSE 'normal'
    END AS status
FROM sensor s
LEFT JOIN LATERAL (
    SELECT r.value, r.time
    FROM sensor_reading r
    WHERE r.sensor_id = s.sensor_id
    ORDER BY r.time DESC
    LIMIT 1
) lr ON true;

-- Liveness: sensors that missed their expected reading window.
-- is_failed when no data ever, or last reading older than 2x sample interval.
CREATE VIEW sensor_liveness AS
SELECT
    s.sensor_id
  , s.line_id
  , s.metric
  , lr.last_time
  , EXTRACT(EPOCH FROM (now() - lr.last_time)) AS seconds_since_last
  , (
        lr.last_time IS NULL
        OR now() - lr.last_time > make_interval(secs => s.sample_interval_s * 2)
    ) AS is_failed
FROM sensor s
LEFT JOIN LATERAL (
    SELECT max(r.time) AS last_time
    FROM sensor_reading r
    WHERE r.sensor_id = s.sensor_id
) lr ON true;

-- Out-of-range history: hourly buckets whose min/max breached the sensor limits.
-- COALESCE to FALSE so buckets never return NULL (production_count has a NULL
-- max_limit -> the upper comparison is NULL); callers can safely use
-- `WHERE violated` or `WHERE violated = FALSE`.
CREATE VIEW sensor_out_of_range_1h AS
SELECT
    a.bucket
  , a.sensor_id
  , s.line_id
  , s.metric
  , COALESCE(a.min_value < s.min_limit OR a.max_value > s.max_limit, false) AS violated
FROM sensor_reading_1h a
JOIN sensor s ON s.sensor_id = a.sensor_id;
