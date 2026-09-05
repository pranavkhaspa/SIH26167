# SatQuery AI — 1-Week Delivery Plan (v2)

**Operational rule:** The build farm works ONE task at a time. The main agent (9router `planning`)
checks this file, picks the highest-priority uncompleted task, writes an elaborated implementation
spec into `entry_point.md`, dispatches the coder (9router `coding`), and the reviewer (9router
`review`) verifies against the acceptance criteria before any push to `staging`.

**Definition of done for every task:** acceptance criteria in `entry_point.md` are all met AND the
verification gate (`backend/tests` via `pytest`, plus `verify.sh`) is green. CI must NEVER swallow
failures (`pytest ... || true` is banned).

**Priority tiers:**
- **P0 = Working core (50-60% app):** real GeoTIFF ingest → real metrics → real EPSG:4326 polygons → shown on a real map → deployed to staging.
- **P1 = Differentiators:** VLM natural-language adapter, SAR cloud-penetration, bi-temporal change.
- **P2 = Wow:** PDF report, offline mode, voice.

---

## Task List

| # | Priority | Task | Status | Acceptance (entry_point.md) |
|---|----------|------|--------|------------------------------|
| 01 | P0 | Real GeoTIFF ingestion engine + WGS84 ground math | ✅ DONE (2026-09-05) | [entry_point.md](./entry_point.md) |
| 02 | P0 | `/api/v1/ingest` endpoint: upload, read bands, compute metrics + polygons, return GeoJSON | ✅ DONE (2026-09-05) | tested via `tests/test_main_api.py` |
| 03 | P0 | Sample-raster generator (synthetic flood GeoTIFF) so demo works offline & tests use real files | ✅ DONE (2026-09-05) | `backend/app/sample_data.py` |
| 04 | P0 | CI gate: drop `|| true`; GitHub Actions runs real tests on a real raster; push to staging only on green | ✅ DONE (2026-09-05) | [ci-cd.yml](./.github/workflows/ci-cd.yml) |
| 05 | P0 | Real map: replace canvas fake with MapLibre GL rendering backend GeoJSON + NDWI raster overlay | ✅ DONE (2026-09-05) | [MapComponent.tsx](./frontend/src/components/MapComponent.tsx) |
| 06 | P0 | `/api/v1/query` agent endpoint: langgraph router wired to REAL ingested state, no hardcoded fallbacks | ✅ DONE (2026-09-05) | [entry_point.md](./entry_point.md) |
| 05b | P0 | Frontend → real backend wiring, no fake data paths | ✅ DONE (2026-09-05) | [entry_point.md](./entry_point.md) Task 07 |
| 07 | P1 | SAR pipeline: ingest Sentinel-1 amplitude, dB conversion, Lee filter, -18 dB water mask, demo cloud-penetration | ✅ DONE (2026-09-05) | [raster_engine.py](./backend/app/raster_engine.py) + `/api/v1/demo/cloud-penetration` |
| 08 | P1 | VLM adapter: route end-user vision queries through OpenRouter/NVIDIA keys (real API calls, no hardcoded bbox) | ✅ DONE (2026-09-05) | [vlm_adapter.py](./backend/app/vlm_adapter.py) — gemini-3.5-flash-lite prime, 3-model chain |
| 09 | P1 | Bi-temporal change: T1/T2 aligned pairs → ΔNDWI → newly inundated polygons + sq km metrics | ✅ DONE (2026-09-05) | `change_engine.align_ndwi_pair` + `/api/v1/demo/change-detect` |
| 10 | P1 | Daytona worker farm: sandbox create/snapshot, parallel task workers, self-hosted CI runners | ✅ DONE (2026-09-05) | `farm/farm.py` — probed 11 keys, 6 usable, 6/6 parallel gate PASS, failpoint FAIL, 0 leftovers |
| 11 | P2 | Split-slider wired to real T1/T2 rasters (currently decorative gradients) | ✅ DONE (2026-09-05) | `GET /api/v1/demo/change-raster/{pre\|post}` + real `<img>` swipe |
| F1 | P2 | MapLibre v6 worker self-contained + basemap switcher + fullscreen + tile-error chip + reset view | ✅ DONE (2026-09-05) | `?worker&url` bundle fix; Voyager/Dark/Satellite; `⛶` Fullscreen API; ScaleControl |
| F2 | P2 | BITEMPORAL demo fallback (no 400) + preset-run UX, dismissible errors, empty state, metric formatting | ✅ DONE (2026-09-05) | lazy demo pair in `/api/v1/query`; `runPreset`; `fmtArea`/`fmtPixels` |
| F3 | P2 | Clean CSS baseline + responsive layout + narrative markdown cleanup | ✅ DONE (2026-09-05) | `index.css` rewrite; `.app-layout` breakpoints; `cleanNarrative`; `_sanitize_narrative` |
| INFRA | P2 | Deploy fixes: `/healthz`, CARTO key, `vercel.json` proxy, Vercel 404/worker chain, first-visit guide | ✅ DONE (2026-09-05) | see adjustment log + [deployment.md](./deployment.md) |
| 12 | P2 | PDF assessment report exporter + offline mode | ⬜ TODO | next session (entry_point.md) |

---

## Next Session (pick up here)

1. **Task 12 — PDF assessment report exporter** (P2): export per-query metrics + geojson + narrative as
   a formatted PDF, plus an offline/demo mode for judge stations without internet.
2. Optional polish backlog: voice input (fastest-wins), token-streaming chat drawer, `dev` branch PR flow.
3. Resume loop from `main` (release baseline): branch off, implement, PR back — staging was realigned
   to `main` at session close (2026-09-05).

---

## Execution Loop (how the farm runs)

```
main agent (planning): pick next task from plan.md → write spec → entry_point.md
coder (coding): implement per entry_point.md
reviewer (review): run verify.sh + review diff; must pass acceptance criteria
if pass: commit → push staging
if fail: feedback → back to coder (max 2 retries, then escalate to human)
human: manual test pass on staging; approve → deploy; else open correction
```

Files that make this loop possible:
- `plan.md` — this file (the WHAT + order)
- `entry_point.md` — the HOW for ONE active task (rewritten each cycle)
- `farm/verify.sh` — deterministic gate (runs real tests, no `|| true`)
- `farm/run_cycle.sh` — orchestrates one full loop
- `CLAUDE.md` — coding rules/constraints for the coder agent

---

## Dynamic Adjustment Log

- **2026-09-05:** v2 plan. Repo audited: docs were overstating implementation; core geo math was real but
  fed synthetic arrays, VLM was a hardcoded stub, frontend map was a canvas fake, CI swallowed failures.
  Rewrote plan around P0 "working core" first. Tasks 01–04 completed same day (ingest + ingest API +
  sample generator + CI gate). CI workflow fixed to install from `backend/requirements.txt` (was missing
  `python-multipart`) and to run pytest from `backend/` so `from app...` imports resolve. Clean single-commit
  history force-pushed to `staging` (aae5c82); old slop history discarded. Tasks 05+ open.
- **2026-09-05:** Task 06 completed. `agent_router.execute_tools` now opens REAL on-disk GeoTIFFs via
  `RemoteSensingRasterEngine` (VQA: NDWI bands 2/3, water mask >0.1, `real_surface_area`,
  `extract_vector_polygons` with real transform/CRS; SAR: read band 1, dB conversion, -18 dB mask;
  bitemporal: pre/post NDWI + `compute_bitemporal_delta_ndwi` + `detect_inundation_change`). Missing
  paths raise `RuntimeError` — no `np.full`/hardcoded `Affine` fallbacks. `/api/v1/query` resolves paths
  via request → module registry (`last_optical`/`last_sar`) → lazy `data/demo/` samples and returns
  `data_source`. `/api/v1/ingest` persists to `backend/data/uploads/` (sanitized, ext-preserving),
  registers by `sar`/`radar` heuristic, keeps prior response + `path`/`data_source` and no longer unlinks.
  `/api/v1/analyze-change` passes pre/post through to the graph. Full backend pytest suite (31 tests) +
  `farm/verify.sh` green.
- **2026-09-05 (Task 05b / frontend wiring):** `App.tsx` no longer fabricates data. Initial state is `null`;
  the catch path shows a real error banner instead of inventing metrics/geojson; a GeoTIFF upload control
  posts to `/api/v1/ingest` and renders real results; on mount the app auto-runs the water-detect demo
  query; layer switches by backend intent. Fixed the pre-existing unused-`err` lint warning. Added a
  `build-frontend` CI job (setup-node 20, `npm ci`, `npm run build`, `npm run lint`) — independent of the
  deploy-hook job. Frontend build+lint green; backend suite still 31 passed.
- **2026-09-05 (Task 07):** SAR pipeline completed. `sar_speckle_filter` replaced with a real
  statistical Lee filter (boxFilter local mean/var, `k = var_noise/var_local` clamped [0,1],
  `m + k(x-m)`; float-scale preserving, edges preserved). `make_cloudy_optical` generator adds a
  thick cloud deck over the water (NDWI can't see it). New `POST /api/v1/demo/cloud-penetration`
  proves all-weather monsoon capability live: optical NDWI finds 0% water under cloud, C-band SAR
  -18 dB mask recovers ~22.9% (0.3756 km²) with true EPSG:4326 polygons. Backend suite now 35 tests;
  `verify.sh` green.
- **2026-09-05 (Task 08):** VLM adapter replacement. Research found `nvidia/rvlm` is NOT hosted on
  `integrate.api.nvidia.com` (only llama-3.2/phi-3 vision, INFERENCE dropped connections), so the live
  route runs through OpenRouter with `google/gemini-3.5-flash-lite` as primary and a 3-model fallback
  chain (→ `google/gemini-3.7-flash` → `meta/llama-3.2-90b-vision-instruct`), all verified working.
  `vlm_adapter.py` rewritten: percentile-stretched band→PNG data URL (cv2, ≤512px) sent as `image_url`
  with the real pipeline metrics (/query, SAR, bitemporal) and a strict no-fabrication system prompt;
  `temperature=0`, 30 s timeout, graceful per-model failure. Hardcoded `predict_grounded_bounding_box`/
  fake narrative deleted. Router narrates via `_vlm_narrative` with deterministic offline fallback
  (`SATQUERY_VLM_ENABLED=0`); `tests/conftest.py` forces offline for CI/net-free pytest. Added
  `python-dotenv` to requirements (was a latent gap). Suite now 38 passed + 1 live-gated; live smoke
  returned a real grounded narrative over a generated GeoTIFF (metrics echoed, e.g. 0.3394 km²).
- **2026-09-05 (Task 09):** Real bi-temporal change. The old `align_and_resample` only cv2-resized
  to equal shapes, ignoring transform/CRS — replaced with `align_to_reference_grid` (rasterio
  `reproject`, bilinear) + `align_ndwi_pair`; the router + demo warp T2 NDWI onto T1's grid so
  misaligned acquisitions produce a correct delta. New `make_bitemporal_pair` generator writes an
  aligned pre/post pair (flood grows: T1 rx/ry 0.26/0.20 → T2 0.34/0.28; optional `shift_pixels`
  offset for misalignment tests). New `POST /api/v1/demo/change-detect` returns per-date water
  metrics, ΔNDWI, true EPSG:4326 change polygons + narrative. Suite now 42 passed + 1 live-gated;
  smoke: T1 0.4183 → T2 0.7657 km², +0.3474 km² newly inundated, first coord (87.007, 27.120).
- **2026-09-05 (Task 10):** Daytona worker farm scaffolded. Live probes verified the full API loop
  (control plane `app.daytona.io/api` + per-sandbox toolbox proxy: `process/execute`, `files/upload`,
  `files/download`, named snapshots). Constraint discovered: the repo `PAT` is fine-grained Actions
  read-only — git clone → 403, `/tarball` → 403, deploy-key POST → 403 — so workers cannot clone the
  private repo; the farm ships the repo as `git archive HEAD` tarball from the host. Credit
  suspension is per-key (jett suspended, phoenix/sage/omen okay) → orchestator probes every key at
  runtime. Sandbox runtime verified: python 3.14, node 25, rasterio 1.5.1 wheels (no GDAL needed),
  backend suite passes (43/1 skip). Task 10 re-scopes "self-hosted CI runners" → "parallel tarball-fed
  sandbox gate workers".
- **2026-09-05 (Task 10 impl/ship):** `farm/farm.py` (stdlib-only) implemented and validated end to
  end. Two real fixes found during live runs: (1) `.env` `DAYTONA_MACHINES` is a multiline JSON —
  load_env had to join continuation lines; (2) the toolbox proxy base `toolboxProxyUrl`
  (`https://proxy.app.daytona.io/toolbox`) already ends in `/toolbox`, so appending another produced
  `/toolbox/toolbox/{sid}` → 401 "Bearer token is invalid"; verified working form is
  `{toolboxProxyUrl}/{sandboxId}/...`. Corrected the entry_point.md spec. Live results: dry-run
  probes 11 keys → 6 usable (phoenix/sage/omen/sova/cypher/reyna), 5 SUSPENDED (jett/killjoy/brimstone/viper/raze,
  depleted credits); real parallel gate on 6 machines → 6/6 PASS with correct pytest artifacts
  (43/1) and summary JSON; `--failpoint` shows injected `test_farm_failpoint` AssertionError → 6/6
  FAIL, exit 1; zero `sih-*` sandboxes left behind in every run. `farm/results/` is gitignored
  (transient). Also deletes leftover stray sandboxes from pre-farm key probing.
- **2026-09-05 (Task 11):** Split-slider wired to real T1/T2 rasters. New `GET
  /api/v1/demo/change-raster/{pre|post}` renders a real acquisition PNG: bands 1-3 percentile-stretched
  RGB base + water mask tinted BGR `[230,120,15]` (cv2.imencode, `Cache-Control: public, max-age=300`;
  unknown acquisition → 404). `SplitSlider.tsx` takes optional `preImageUrl/postImageUrl` and shows real
  swiped `<img>` layers (gradient fallback kept); `App.tsx` runs `/api/v1/demo/change-detect` on mount,
  shows t1/t2/change km² metrics strip + narrative, passes raster URLs only when no error. Bug caught in
  live smoke: water tint covered only 320 px (rows 0/1) instead of 4183 — `water_mask()` returns uint8
  and `canvas[mask] = color` performs integer fancy indexing (advanced-index rows), NOT boolean masking;
  fix is `canvas[mask.astype(bool)] = color`. Added a regression assert (tinted pixel count must equal
  the geospatial water-mask count). Suite now 47 passed + 1 live-gated; smoke pre 4183 → post 7657
  tinted px (matches masks exactly), pre≠post bytes.
- **2026-09-05 (F1 — MapLibre worker + map overhaul):** Prod blank-map crash chased down. `maplibre-gl-worker.mjs`
  is ESM that `import`s `./maplibre-gl-shared.mjs`; Vite's `?url` copy emitted the worker but never the
  shared chunk → 404 text/html → strict-MIME module failure → worker died → nothing rendered. Fix:
  import `maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url` so Vite bundles worker **and** its dependency
  graph into one self-contained classic script (verified zero external imports; dev+preview serve
  `text/javascript`). Second crash (`Style is not done loading`) came from `addSource`/`addLayer` running
  before `map.load` — both effects now early-return until `loaded=true` and re-run on that transition.
  Map overhaul: basemap switcher (Voyager/Dark/Satellite via CARTO+Esri), `ScaleControl`, reset-to-India,
  tile-error chip, loading spinner, `⛶` Fullscreen API toggle + `map.resize()` on `fullscreenchange`.
- **2026-09-05 (F2 — routing/UX):** `/api/v1/query` BITEMPORAL branch no longer 400s when pre/post missing —
  lazily defaults to the demo pair (matches SAR/optical lazy demo pattern). Frontend: presets execute
  immediately, dismissible error banner (✕), empty-state metrics panel, `fmtArea`/`fmtPixels` formatting.
- **2026-09-05 (F3 — CSS + narratives):** `index.css` rewritten to a clean dark baseline
  (`color-scheme: dark`, custom props, responsive `.app-layout` at 1024/640px, dark scrollbars);
  Vite template CSS removed. VLM output sanitized end-to-end: system prompt forbids Markdown,
  `vlm_adapter._sanitize_narrative` strips `**`/`*`/`__`/headings/bullets and repairs corrupted floats
  (`0.37.56` → `0.3756`), frontend `cleanNarrative` is belt-and-suspenders. First-visit 5-step guide
  overlay (localStorage dismissal) + `?` help button. Suite now 50 passed + 1 live-gated.
- **2026-09-05 (INFRA — deploy fixes):** Render health check was hitting `/healthz` → 404 — added the
  alias + test (deploy started passing). CARTO basemap watermark removed by adding the project tile key
  (`cb1_2xx6_1_513fdfc95d1125751297f712`) to tile URLs. Production Vercel 404s fixed with `vercel.json`
  rewrites `/api/:path*` → Render (server-side, kills CORS) + SPA fallback `/(.*)` → `/index.html`.
- **2026-09-05 (Session close):** All P0/P1 shipped. `staging` (17 commits) squash-merged into `main`
  as the v1.0 release baseline; `staging` realigned to `main`. Docs: `tech.md` added; README/deployment/
  environments/mainagent/entry_point/frontend README updated. CI 3/3 green; Render + Vercel deploy on
  `main` push. Next: `entry_point.md` = Task 12.