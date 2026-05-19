# Shared Observability

Owns cross-domain telemetry infrastructure.

Current responsibilities:
- SQLite query log storage
- Query log writer
- Query telemetry models

TODO:
- Add structured log exporters.
- Add request tracing middleware after API boundaries stabilize.
- Move to Postgres-backed telemetry for production deployments.
