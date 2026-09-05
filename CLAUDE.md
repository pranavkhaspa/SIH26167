# CLAUDE.md — Execution Instructions for SatQuery AI (SIH26167)

This file defines project instructions, developer workflows, and operational standards for Claude Code while building SatQuery AI.

---

## 1. Project Context & Objectives
- **Target:** Build **SatQuery AI** (SIH26167) — Vision-Language Assistant for Remote Sensing.
- **Sponsor:** Indian Space Research Organisation (ISRO).
- **Core Philosophy:** High efficiency, zero bloat, stdlib/native tools first, strict focus on real 16-bit GeoTIFF and C-band SAR processing (no generic screenshot wrappers).

---

## 2. Working Principles & Development Guidelines
- **One Task at a Time:** Focus entirely on the active task assigned in `plan.md`. Finish, verify, update status, then move to the next task.
- **Terse & Technical:** Keep descriptions concise and code-focused. Omit pleasantries, filler, and fluff.
- **Shortest Working Diff:** Use standard libraries (`math`, `json`, `pathlib`, `numpy`, `rasterio`) before pulling in new dependencies.
- **Fail-Fast Error Handling:** Ensure all raster transforms handle out-of-bounds inputs, invalid CRS representations, and missing spectral bands gracefully.

---

## 3. Directory Layout & File Responsibilities

```
/home/pro/Documents/sih/
├── PRD.md                       # Product Requirements Document
├── techarchitecture.md          # Technical Architecture & Pipeline Specs
├── CLAUDE.md                    # Project Rules & Claude Instructions (This file)
├── plan.md                      # 4-Week Step-by-Step Execution Plan
├── backend/                     # Python FastAPI Backend
│   ├── app/
│   │   ├── main.py              # FastAPI Entry Point
│   │   ├── raster_engine.py     # GeoTIFF, NDWI/NDVI, SAR Processing
│   │   ├── change_engine.py     # Bi-Temporal Difference & Vector Extraction
│   │   ├── agent_router.py      # LangGraph Agentic Tool Dispatcher
│   │   └── vlm_adapter.py       # Fine-tuned Remote Sensing VLM Wrapper
│   └── tests/                   # Assert-based Unit Tests
└── frontend/                    # React + MapLibre GL Frontend Console
    ├── src/
    │   ├── App.jsx              # Main Dashboard Component
    │   ├── components/          # Map, Chat Drawer, Split Slider
    │   └── utils/               # GeoJSON Helpers
    └── package.json
```

---

## 4. Key Commands & Running Guidelines

### Backend Setup & Execution
```bash
# Environment setup
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# Start Backend Server
cd backend && uvicorn app.main:app --reload --port 8000

# Run Verification Self-Checks
cd backend && python -m pytest tests/        # 50 passed, 1 live-gated
```

### Frontend Setup & Execution
```bash
# Node setup
cd frontend
npm install
npm run dev
npm run lint && npm run build               # gate (must be exit 0)
```

---

## 5. Live Environments & Known Gotchas (2026-09-05)

- **Backend (Render):** `https://sih26167-xqgi.onrender.com` — Dockerfile context is `backend/`, so
  code lives at `/app/app/` in the container (`DEMO_DIR=/app/data/demo/`). Health: `/health`, `/healthz`.
- **Frontend (Vercel):** `https://sih-26167.vercel.app` — Root Dir `frontend/`; `vercel.json`
  proxies `/api/*` → Render and `/(.*)` → `/index.html`.
- **MapLibre worker:** import MUST use `?worker&url` (not `?url`) or the shared chunk 404s → blank map.
- **VLM narrative:** plain text only — `_sanitize_narrative` strips Markdown + repairs `0.37.56` →
  `0.3756`. Runtime keys: `OPEN_ROUTER` (or `OPENROUTER_API_KEY`), `SATQUERY_VLM_MODEL`,
  `SATQUERY_VLM_ENABLED=0` = deterministic offline.
- **CARTO tile key** `cb1_2xx6_1_513fdfc95d1125751297f712` lives in MapComponent; keep attribution.
- **Branches:** `main` = release baseline; `staging` = working branch; ship via squash PR, then
  realign `staging` to `main`.

---

## 6. Defense against Hackathon Disqualifications
1. **Never mock GeoTIFF parsing with plain JPEGs.** Always use `rasterio` or `gdal`.
2. **Never return raw pixel bounding boxes.** Always convert pixel coordinates to EPSG:4326 Lat/Lon polygons using the raster's affine matrix.
3. **Always demonstrate SAR radar handling** for all-weather/monsoon cloud-penetration scenarios.
