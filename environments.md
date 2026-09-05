# SatQuery AI — Environments, Variables & Secrets (as deployed)

**Document Target:** The real environments (local / staging / production), the runtime env vars the
app reads, and the secrets GitHub Actions needs. Reflects live as of 2026-09-05.

---

## 1. Environment matrix (live)

| Env | Backend | Frontend | Notes |
|---|---|---|---|
| **Local dev** | `http://localhost:8000` | `http://localhost:5173` | Vite dev proxy: `/api` → localhost:8000 (defined in `frontend/vite.config.ts`) |
| **Staging** | Render (`sih26167-xqgi.onrender.com`) | Vercel (deploy previews + `sih-26167.vercel.app`) | pushed `staging` branch |
| **Production** | Render (same service) | Vercel (`sih-26167.vercel.app`) | `main` branch → deploy hooks |

Both hosting tiers share one Render service + one Vercel project; branch push redeploys. The frontend
calls the backend through Vercel's server-side rewrite (`vercel.json`), so there are **no CORS concerns**
in production. `docker-compose.yml` remains a local-only convenience and is not part of the live path.

---

## 2. Runtime environment variables (read by the app)

Backend `.env` (gitignored; template in `.env.example`):

| Variable | Used by | Default | Purpose |
|---|---|---|---|
| `OPEN_ROUTER` / `OPENROUTER_API_KEY` | `vlm_adapter.py` | — | OpenRouter key for live VLM narratives |
| `OPENROUTER_BASE_URL` | `vlm_adapter.py` | `https://openrouter.ai/api/v1` | API base |
| `SATQUERY_VLM_MODEL` | `vlm_adapter.py` | `google/gemini-3.5-flash-lite` | Primary image-model |
| `SATQUERY_VLM_ENABLED` | `agent_router.py` | `1` | `0` → deterministic offline narratives (judge stations / CI) |
| `BACKEND_HOST` / `BACKEND_PORT` | main.py | `0.0.0.0` / `8000` | uvicorn bind |
| `DEMO_DIR` | main.py | `backend/data/demo/` | where lazy demo GeoTIFFs are written (Render: `/app/data/demo/`) |

Frontend build-time: `VITE_API_BASE_URL` is **not required** — the app uses relative `/api/*`, and
Vercel rewrites it to Render.

---

## 3. Secrets for CI (`github.com/pranavkhaspa/SIH26167` settings → Secrets)

| Secret | Used by (job) | Value |
|---|---|---|
| `RENDER_DEPLOY_HOOK` | trigger-deploys | Render deploy hook URL (fire when tests pass on main/staging push) |
| `VERCEL_DEPLOY_HOOK` | trigger-deploys | Vercel build-hook URL |

`PAT` in the local `.env` is a fine-grained GitHub token (Actions + repo minimum) used for farm API
calls and releases. It is **not** a CI secret.

---

## 4. Local dev setup

```bash
cp .env.example .env            # then fill real keys (gitignored)
python3 -m venv venv && source venv/bin/activate
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload --port 8000 &
cd frontend && npm install && npm run dev
```

`/api/v1/query`, `/ingest`, all `/demo/*` and `/health(z)` are reachable on the staging backend today;
local dev is feature-identical.