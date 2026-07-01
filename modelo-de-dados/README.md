# modelo-de-dados

TimescaleDB schema for the Serra Clara Bebidas IIoT solution, applied to an
existing Tiger Cloud service via psql (Tiger MCP auth is currently unavailable).

## Tiger Cloud service

- Service: `db-73561`
- service_id: `h3bmabyk97`

## Apply order

Apply the SQL files in numeric order (each is safe on a fresh schema):

1. `sql/01_dimensions.sql`
2. `sql/02_hypertable.sql`
3. `sql/03_compression_retention.sql`
4. `sql/04_continuous_aggregates.sql`
5. `sql/05_ca_policies.sql`
6. `sql/06_views.sql`
7. `sql/07_seed.sql`

## Verify

See `docs/plans/2026-07-01-modelo-de-dados.md` for the per-object
verification queries.

## Status

Complete — schema built and validated on service `h3bmabyk97` (TimescaleDB 2.27.2).

Verified inventory: 1 hypertable (`sensor_reading`, 12h chunks), 4 continuous
aggregates (1m/15m/30m/1h), 3 support views (`sensor_status`, `sensor_liveness`,
`sensor_out_of_range_1h`), 30 sensors across 3 production lines. Compression after
7 days, raw retention 90 days, aggregate retention 1 year. Behavioral smoke test
passed (status classification, liveness detection, 1m aggregate avg=sum/count).
