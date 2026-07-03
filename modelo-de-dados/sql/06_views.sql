-- Views de apoio para o dashboard web.

-- Status em tempo real: última leitura crua por sensor vs. seus limites operacionais.
-- Intenção do limite NULL: sensores production_count têm max_limit = NULL (sem
-- limite superior). `value > NULL` é NULL, então o ramo 'alerta' é ignorado e eles
-- ficam 'normal' a menos que value < min_limit (0). Isso é proposital; não faça
-- COALESCE de max_limit para +inf "para corrigir".
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

-- Liveness: sensores que perderam sua janela esperada de leitura.
-- is_failed quando nunca houve dado, ou última leitura mais velha que 2x o intervalo de amostragem.
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

-- Histórico fora de faixa: buckets horários cujo min/max violou os limites do sensor.
-- COALESCE para FALSE para que os buckets nunca retornem NULL (production_count tem
-- max_limit NULL -> a comparação superior é NULL); quem consome pode usar com
-- segurança `WHERE violated` ou `WHERE violated = FALSE`.
CREATE VIEW sensor_out_of_range_1h AS
SELECT
    a.bucket
  , a.sensor_id
  , s.line_id
  , s.metric
  , COALESCE(a.min_value < s.min_limit OR a.max_value > s.max_limit, false) AS violated
FROM sensor_reading_1h a
JOIN sensor s ON s.sensor_id = a.sensor_id;
