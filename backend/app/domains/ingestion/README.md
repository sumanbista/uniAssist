# Ingestion Domain

Foundational Caldwell University ingestion for allowlisted forms and academic
calendar sources.

Implemented scope:
- explicit Caldwell source registry
- async HTML fetch and validation
- deterministic parsing and text sanitization
- canonical form and academic calendar extraction models
- pending-review canonical persistence
- retry-safe source-hash dedupe
- internal event emission
- admin-triggered API runs

Intentionally out of scope:
- scheduled jobs
- autonomous crawling
- PDF extraction
- AI extraction
- embeddings generation
- analytics consumers
