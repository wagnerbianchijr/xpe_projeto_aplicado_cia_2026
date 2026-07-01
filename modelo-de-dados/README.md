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
