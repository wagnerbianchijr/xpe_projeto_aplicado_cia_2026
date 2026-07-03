-- Tabelas dimensão: linhas de produção e o catálogo de sensores.

CREATE TABLE production_line (
    line_id       smallint PRIMARY KEY
  , name          text     NOT NULL
  , product_type  text     NOT NULL
      CHECK (product_type IN ('suco', 'agua_saborizada', 'cha_gelado'))
  , description   text
);

CREATE TABLE sensor (
    sensor_id          int      PRIMARY KEY
  , line_id            smallint NOT NULL REFERENCES production_line (line_id)
  , metric             text     NOT NULL
  , unit               text     NOT NULL
  , min_limit          double precision
  , max_limit          double precision
  , sample_interval_s  smallint NOT NULL DEFAULT 5
  , description        text
  , CONSTRAINT sensor_limits_ck CHECK (max_limit IS NULL OR min_limit IS NULL OR max_limit >= min_limit)
);

CREATE INDEX sensor_line_id_idx ON sensor (line_id);
