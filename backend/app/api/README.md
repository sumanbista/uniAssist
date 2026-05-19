# API Layer

Owns HTTP entrypoints and FastAPI application assembly.

Current responsibilities:
- Health endpoint
- Query endpoint
- Tool testing endpoints
- Admin analytics endpoints

TODO:
- Split endpoints into domain routers under `api/routers`.
- Add versioned API namespaces.
- Add API-level dependencies for auth and tenant scoping.
