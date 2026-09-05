# SatQuery AI — Deployment, CI/CD & Hosting (as deployed)

**Document Target:** The live deployment reality — Render backend, Vercel frontend, GitHub Actions
pipeline, and the deployment gotchas fixed in the 2026-09-05 session.

---

## 1. Architecture (2 static-ish hosts, no Nginx custom)

```
GitHub Actions (ci-cd.yml)
  ├─ test-backend   → GDAL apt + pip install backend/requirements.txt + pytest tests/ (from backend/)
  ├─ build-frontend → node 20 + npm ci + npm run build + npm run lint
  └─ trigger-deploys (push to main | staging only)
       ├─ POST https://api.render.com/... (RENDER_DEPLOY_HOOK secret)
       └─ POST https://api.vercel.com/v1/integrations/... (VERCEL_DEPLOY_HOOK secret)

Render  https://sih26167-xqgi.onrender.com  → FastAPI backend (port 8000)
Vercel  https://sih-26167.vercel.app        → React SPA (Root Dir = frontend/)
```

- **Backend on Render** deploys from `backend/Dockerfile` (Docker context `backend/`), so code lives
  at `/app/app/` in the container → `DEMO_DIR=/app/data/demo/` keeps demo GeoTIFFs writable.
  Health checks hit **both** `/health` and `/healthz` (alias added after the check 404ed at first deploy).
- **Frontend on Vercel** builds via Vite; `frontend/vercel.json` rewrites:
  - `/api/:path*` → `https://sih26167-xqgi.onrender.com/api/:path*` (server-side proxy, no CORS)
  - `/(.*)` → `/index.html` (SPA fallback, kills Vercel 404s on deep paths)

---

## 2. Backend Dockerfile (`backend/Dockerfile`)

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends gdal-bin libgdal-dev \
    build-essential libgl1-mesa-glx libglib2.0-0 curl && rm -rf /var/lib/apt/lists/*
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal C_INCLUDE_PATH=/usr/include/gdal
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

There is **no frontend Dockerfile** in the live path — Vercel serves the static build directly.

---

## 3. GitHub Actions CI/CD (`ci-cd.yml`)

Runs on `push` to `main`/`dev`/`staging` and `pull_request` to `main`/`staging`:

1. **Run Backend Unit Tests** — real GeoTIFF tests, NO `|| true`, `pytest tests/ --doctest-modules`
   from `backend/` (pytest.ini sets `pythonpath = .`). Must finish green.
2. **Build & Lint Frontend** — `npm ci`, `npm run build`, `npm run lint` (oxlint + tsc). Verifies the
   MapLibre worker still bundles self-contained.
3. **Trigger Render & Vercel Deploy Hooks** (push to `main`/`staging` only, needs `test-backend`) —
   curls the two deploy-hook URLs guarded by secrets.

Rule: CI must NEVER swallow failures (`pytest ... || true` is banned).

---

## 4. Gotchas fixed in this release (2026-09-05)

| Symptom | Root cause | Fix |
|---|---|---|
| Render deploy looped (health 404) | check hit `/healthz`, app only had `/health` | added `/healthz` alias + test |
| CARTO basemap watermark | no tile key → free-plan watermark | tile URL `?key=cb1_2xx6_1_513fdfc95d1125751297f712` (≤5M req/mo, keep attribution) |
| Vercel 404 on `/api/*` & deep paths | SPA has no backend routes | `vercel.json` rewrites → Render + `/(.*)` → `/index.html` |
| Blank map in prod | MapLibre `worker.mjs` ESM-imported a shared chunk Vite never emitted | `?worker&url` import → self-contained classic worker script |
| `Style is not done loading` | `addSource` before map `load` | effects gated on `loaded` state |

---

## 5. Deploying a release

1. Work on `staging`, push → CI (3 jobs) + staging Render/Vercel deploys.
2. Open PR `staging → main`, wait PR CI, squash-merge (one clean release commit on `main`).
3. Push to `main` triggers the same 3 jobs incl. deploy hooks → production Render + Vercel.
4. Realign `staging` to `main` (`git reset --hard origin/main` + force-push) so the next PR is a
   clean one-shot diff (histories were squashed/divergent this session).