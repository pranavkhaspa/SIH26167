# SatQuery AI — Frontend Console

React 19 + TypeScript + Vite 8 + MapLibre GL v6, linted with oxlint.

## What's here
- `src/App.tsx` — main dashboard: VQA & SAR Analysis tab, Bi-Temporal Swipe tab, query/preset/upload
  controls, Operational Inspection Report, first-visit guide overlay.
- `src/components/MapComponent.tsx` — MapLibre map: basemap switcher (Voyager/Dark/Satellite),
  EPSG:4326 overlay, fullscreen, ScaleControl, reset-to-India, tile-error chip.
- `src/components/SplitSlider.tsx` — swipe-compare for real T1/T2 rasters (gradient fallback).
- `src/index.css` — dark responsive baseline (`color-scheme: dark`, `.app-layout` grid).

## Key gotcha: MapLibre worker
MapLibre v6's `maplibre-gl-worker.mjs` is ESM that imports a sibling shared chunk. It must be imported
with Vite's **`?worker&url`** query so the worker AND its dependency graph bundle into one
self-contained script:

```ts
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
setWorkerUrl(maplibreWorkerUrl);
```

Plain `?url` emits only the worker file → the shared chunk 404s in production → blank map.

## Commands
```bash
npm install
npm run dev        # proxies /api → http://localhost:8000
npm run lint       # oxlint (exit 0 = clean)
npm run build      # Vite build (exit 0 = clean; verifies worker bundles)
npm run preview    # serve the built dist locally
```

## Deploy
Vercel: Root Directory = `frontend/`. `vercel.json` rewrites `/api/:path*` → the Render backend
(server-side, no CORS) and `/(.*)` → `/index.html` (SPA fallback).