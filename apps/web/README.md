# Web Control Room

Minimal Next.js interface for Phase 1.

From `apps/web`:

```bash
npm install
npm run dev
```

By default the UI expects the FastAPI service at `http://localhost:8000`.
Set `NEXT_PUBLIC_API_BASE_URL` to override it.

The API must allow the browser origin with `WEB_ORIGIN` (default:
`http://localhost:3000`).
