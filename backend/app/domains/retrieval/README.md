# Retrieval Domain

Owns the current UniAssist AI query pipeline while the platform migrates toward
the Phase 2 modular monolith.

Current responsibilities:
- Intent classification and routing decisions
- Tool registry and tool execution
- Structured mock-data retrieval
- Response formatting
- Query and trace schemas

Temporary ownership:
- The Phase 1 router and tools live here until orchestration, ingestion, and
  canonical retrieval systems are introduced.

TODO:
- Split orchestration planning into `domains/orchestration`.
- Replace JSON-backed tools with repository-backed retrieval.
- Add citation-aware retrieval interfaces.
