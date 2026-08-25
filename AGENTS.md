# crawlio.io — Agent Notes

## IMPORTANT: Production deployment scheduled for tomorrow
- Deploy this project (backend + frontend) to production in the next session.
- Localhost setup that already works:
  - Backend: uvicorn on 127.0.0.1:8001, SQLite (`backend/crawlio.db`, all migrations applied via `alembic upgrade heads`)
  - Frontend: Vite dev server on localhost:5173, `VITE_API_URL=http://127.0.0.1:8001` (see `frontend/.env`)
  - Auth: Clerk dev instance `fit-badger-93.clerk.accounts.dev` — JWKS/issuer already configured in `backend/.env`

### Before production deploy
- [ ] Switch `DATABASE_URL` from SQLite to real PostgreSQL + run `alembic upgrade heads`
- [ ] Set up Redis + run Celery worker & beat (`docker-compose.yml` has the full prod topology)
- [ ] Fill real keys in `backend/.env`: `CLERK_SECRET_KEY`, `SUPER_ADMIN_EMAILS` (user's email still missing), Tavily/Brevo/Mistral as needed
- [ ] Frontend build: `npm run build` with production `VITE_API_URL` + live Clerk publishable key

## Session log (2026-08-25)
- Fixed location-filter leak: expansion-round candidates lacked `search_city`; now every candidate path sets both `search_city` + `result_city` defaults (`discovery_service.py`). Filter drops leads whose address doesn't contain the filter city.
- Fixed wikidata/wikipedia/overpass being called even when `use_osm=false` (gated now) — was causing multi-minute hangs.
- Exact-count discovery verified: limit=1→1, 3→3, 5→5, 10→10; quality gate ≥30 enforced; `completeness` score attached to each lead.
- Known flaky externals: Overpass mirrors (502/429), Google Maps crawler slow (~55s). Redis not installed locally → Celery background jobs offline.
