# SatQuery AI — Technical Implementation (tech.md)

> Real, shipped implementation notes for SIH26167. Everything here reflects code that exists
> on `main`, passes CI, and runs live on Render + Vercel. No aspirational features.

---

## 1. System Layout

```
frontend (Vercel: sih-26167.vercel.app)
  React 19 + Vite 8 + MapLibre GL v6 + TypeScript (oxlint)
  App.tsx, components/MapComponent.tsx, components/SplitSlider.tsx

backend (Render: sih26167-xqgi.onrender.com, port 8000)
  FastAPI + rasterio + numpy + opencv-headless + langgraph + httpx
  app/main.py           -> HTTP layer, all endpoints
  app/raster_engine.py  -> GeoTIFF open, NDWI/NDVI, SAR dB + Lee filter, area, vectors
  app/change_engine.py  -> bi-temporal alignment, delta, change raster PNG
  app/agent_router.py   -> intent classifier + tool executor (agentic dispatch)
  app/vlm_adapter.py    -> hosted VLM narrative via OpenRouter (image + metrics)
  app/sample_data.py    -> deterministic demo GeoTIFF generators
  tests/                -> pytest suite (50 passed, 1 live-gated)

farm/farm.py            -> Daytona parallel worker-farm gate (stdlib-only)
.github/workflows/ci-cd.yml -> 3 jobs: backend pytest, frontend build+lint, deploy hooks
```

No Nginx, no Docker-for-frontend, no GPU inference in the live path. Two static hosts.

---

## 2. Backend API (all live)

| Endpoint | Purpose |
|---|---|
| `GET /health`, `GET /healthz` | Render health checks (both 200) |
| `POST /api/v1/ingest` | Upload GeoTIFF (multipart), sanitized path, persists to `backend/data/uploads/`, registers by SAR heuristic |
| `POST /api/v1/query` | Natural-language query → intent → real raster tools → GeoJSON + metrics + narrative |
| `POST /api/v1/analyze-change` | Explicit pre/post paths → all four bands, bi-temporal metrics |
| `POST /api/v1/demo/cloud-penetration` | Optical (cloud-blocked) vs SAR water masks, live monsoon demo |
| `POST /api/v1/demo/change-detect` | T1/T2 aligned demo pair → growing-water change vectors + km² |
| `GET /api/v1/demo/change-raster/{pre\|post}` | Rendered acquisition PNG (percentile RGB + water tint), `Cache-Control: max-age=300` |

### `/api/v1/query` intent routing (`agent_router.classify_intent`)
- `BITEMPORAL_CHANGE_DETECTION` ← "change / flood / bitemporal / compare"
- `CROSS_MODAL_SAR_FUSION` ← "sar / radar / cloud"
- `SINGLE_IMAGE_VQA` default
- Missing bitemporal paths lazily fall back to the demo pair (no 400).

**Path resolution order:** request body → module registry (`last_optical`/`last_sar` from `/ingest`) →
lazy generated `data/demo/` sample. `data_source` always returned.

---

## 3. Real raster math (nothing synthetic)

All arrays come from `rasterio.open(...).read()` on actual 16-bit GeoTIFFs.

- **NDWI** `(green - nir) / (green + nir)` on bands 2/3; **water mask** `ndwi > 0.1`.
- **NDVI** `(nir - red) / (nir + red)`.
- **SAR**: band-1 amplitude → dB (`20 * log10`), statistical **Lee speckle filter**
  (boxFilter local mean/var, `k = var_noise/var_local` clamped `[0,1]`, `m + k(x - m)`),
  water mask `sigma0 <= -18 dB`.
- **Bi-temporal**: `reproject` (bilinear) warps T2 onto T1's grid, ΔNDWI, newly-inundated mask.
- **Area**: pixel counts × true pixel size from the affine transform → `km²` and `hectares`.
- **Vectors**: pixel mask → polygon outline → **affine-transformed to EPSG:4326 lon/lat** →
  `FeatureCollection` (never raw pixel boxes). Min polygon area `8 px`.

---

## 4. VLM narrative (`vlm_adapter.py`)

- `render_raster_preview`: bands → 2–98 percentile stretch → ≤512 px PNG data URL (cv2).
- Sends image + real pipeline metrics to OpenRouter; `temperature=0`, 30 s timeout.
- Model chain: `SATQUERY_VLM_MODEL` (default `google/gemini-3.5-flash-lite`) →
  `google/gemini-3.7-flash` → `meta/llama-3.2-90b-vision-instruct`. Per-model fallback.
- **No API key** or `SATQUERY_VLM_ENABLED=0` → deterministic offline narrative (CI-safe).
- `_sanitize_narrative` strips Markdown (`**`, `*`, `__`, headings, bullets) and repairs
  corrupted floats (`0.37.56` → `0.3756`).

Env: `OPEN_ROUTER` (or `OPENROUTER_API_KEY`), `SATQUERY_VLM_MODEL`, `SATQUERY_VLM_ENABLED`.

---

## 5. Frontend (React + MapLibre GL v6 + Vite 8)

- **MapLibre worker**: imported as `maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url` so Vite
  bundles worker + its `maplibre-gl-shared.mjs` dependency into one **self-contained classic
  script**. Plain `?url` 404s on the shared chunk → blank map.
- **Source gating**: `addSource`/`addLayer` run only after `map.load` (`loaded` state gates both
  effects), fixing "Style is not done loading" on basemap swaps.
- **Basemaps** (bottom-left): Voyager / Dark (CARTO, keyed tiles) + Esri Satellite.
- **Overlays**: EPSG:4326 GeoJSON fill+line, colored per intent (NDWI blue, NDVI green,
  SAR purple, change red). `fitBounds` on new data, reset-to-India button, ScaleControl.
- **Fullscreen**: Fullscreen API toggle (`⛶/🗗`) + `map.resize()` on `fullscreenchange`.
- **SplitSlider**: real T1/T2 `<img>` swipe (clip-path), optional gradient fallback.
- **First-visit guide**: 5-step overlay, `localStorage` dismissal, `?` help in header.
- **Narrative cleaning**: belt-and-suspenders `cleanNarrative` strips markdown on render.
- **Deploy**: `vercel.json` rewrites `/api/:path*` → Render (server-side, no CORS), SPA
  fallback `/(.*)` → `/index.html`.

---

## 6. Demo data (deterministic, generated at runtime)

- `sample_data.make_optical`: synthetic flood GeoTIFF (RGBN uint16).
- `make_cloudy_optical`: same scene + thick cloud deck (blocks optical NDWI).
- `make_bitemporal_pair`: aligned pre/post pair; water grows 26% → 34% (optional shift for
  misalignment tests). Demo files live in `data/demo/`, gitignored as `data/*.tif`.

---

## 7. CI / Deploy

- `test-backend`: ubuntu + GDAL apt, `pip install -r backend/requirements.txt`, pytest from
  `backend/`. No `|| true` anywhere.
- `build-frontend`: node 20, `npm ci`, `npm run build`, `npm run lint` (oxlint + tsc).
- `trigger-deploys` (push to `main`/`staging` only): POST Render + Vercel deploy hooks.
- Render: `backend/Dockerfile`, context `backend/`, code at `/app/app/`, `DEMO_DIR=/app/data/demo/`.
- Vercel: Root Directory `frontend/`, Vite build, Rewrites to Render.

---

## 8. Daytona farm (`farm/farm.py`, stdlib-only)

- Control plane `app.daytona.io/api` + per-sandbox toolbox proxy (`{toolbox}/sandboxId/...`).
- Ships repo as `git archive HEAD` tarball (repo PAT is read-only for Actions → workers
  cannot clone/`/tarball`).
- Probes every `DAYTONA_MACHINES` key at runtime (11 configured → 6 usable, 5 credit-suspended);
  6-machine parallel backend-gate run, failpoint injection test, zero leftover sandboxes.
- `sih-farm-base` snapshot (phoenix org): Ubuntu, python 3.14, rasterio 1.5.1 wheels.

---

## 9. Verification baseline (session close, 2026-09-05)

- Backend `pytest tests/` → **50 passed, 1 skipped** (live VLM test is gated).
- Frontend `npm run lint` + `npm run build` → **exit 0**; MapLibre worker self-contained.
- Live smoke: NDWI 0.4183 → 0.7657 km² (T1→T2), +0.3474 km² inundated; SAR recovers
  ~22.9% under cloud vs 0% optical; change-raster PNGs differ byte-wise.