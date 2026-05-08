## UniAssist AI

Agentic university-information assistant with a FastAPI backend, structured tool
execution, role-based access control, transparent tool traces, and a Next.js chat
frontend.

## Run Locally

Start the backend:

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

Start the frontend:

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000`.

## Analytics Logging

Every `/query` request is persisted to a local SQLite database at
`backend/app/data/query_logs.sqlite3`. The database is generated at runtime and
is intentionally ignored by Git.

Admin-only analytics endpoints:

```text
GET /analytics/summary?role=admin
GET /analytics/tools?role=admin
GET /analytics/roles?role=admin
GET /analytics/recent?role=admin
```

The frontend admin view is available at:

```text
http://localhost:3000/admin/analytics
```

Non-admin analytics requests return `{"error":"Access denied"}`.
