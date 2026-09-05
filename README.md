# SatQuery AI (SIH26167)
> Interactive Vision-Language Assistant for Multimodal Remote Sensing Image Analysis through Natural Language Queries

**Sponsoring Ministry:** Indian Space Research Organisation (ISRO)  
**Theme:** Space Technology  
**Track:** Software  
**Prize:** ₹1,00,000 INR  

---

## 🛰️ Project Overview
SatQuery AI enables decision-makers to query multi-spectral (Sentinel-2) and Synthetic Aperture Radar (Sentinel-1 SAR) Earth Observation data in plain natural language. The system executes native 16-bit GeoTIFF raster mathematics, computes all-weather SAR flood masks through dense cloud cover, runs bi-temporal Siamese change detection, and renders georeferenced EPSG:4326 vector overlays on an interactive 3D map console.

---

## 📂 Documentation Directory

| Document | Description |
|---|---|
| [`tech.md`](./tech.md) | **Actual shipped implementation** — endpoints, raster math, frontend, deploy, verification baseline |
| [`PRD.md`](./PRD.md) | Product Requirements Document (User personas, Functional & Non-Functional Requirements, Success Metrics) |
| [`techarchitecture.md`](./techarchitecture.md) | Deep Technical Architecture (Affine coordinate math, SAR dB calculations, LangGraph schema, API specs) |
| [`deployment.md`](./deployment.md) | Live CI/CD & hosting setup — Render backend, Vercel frontend, deploy hooks |
| [`plan.md`](./plan.md) | Prioritized task roadmap with status column + next-session TODO |
| [`environments.md`](./environments.md) | Hosting blueprint + runtime environment variables |
| [`entry_point.md`](./entry_point.md) | Spec for the currently-active (next) task |
| [`CLAUDE.md`](./CLAUDE.md) | Project instructions, coding rules, environment setup, and anti-disqualification standards |
| [`mainagent.md`](./mainagent.md) | Build-farm orchestrator operating manual |
| [`SIH26167.md`](./SIH26167.md) | Master Problem Statement specification, code templates, and judge pitch script |
| [`SIH26167_SatQuery_AI.md`](./SIH26167_SatQuery_AI.md) | Executive winning strategy and Claude token feasibility analysis |

---

## ⚡ Key Technical Features

1. **Native 16-Bit GeoTIFF Ingestion:** Preserves all multi-spectral bands (NIR, Red-Edge, SWIR) without lossy 8-bit RGB down-sampling — `rasterio` reads real files, never JPEG/PNG stand-ins.
2. **C-Band SAR Cloud Penetration:** Converts Sentinel-1 radar intensity to decibels ($\sigma^0$) with a real statistical Lee filter for all-weather flood detection.
3. **Bi-Temporal Siamese Difference Engine:** Computes $\Delta\text{NDWI}$ across $T_1$ and $T_2$ rasters (reprojection-aligned) to extract newly inundated land area ($\text{km}^2$) and vector boundaries.
4. **Agentic Tool Orchestrator:** Classifies natural-language queries and executes spatial tools on real ingested state.
5. **Real-World Coordinate Grounding:** Transforms water/change masks into WGS84 (EPSG:4326) GeoJSON polygons via the raster's affine matrix.
6. **Live VLM Narratives:** Hosted vision-language model scores the real raster preview + metrics over OpenRouter (3-model fallback chain, markdown-sanitized).
7. **Web Console (React + MapLibre GL v6):** Basemap switcher (CARTO/Esri), fullscreen, real T1/T2 swipe slider, first-visit guide.

---

## 🌐 Live Deployments

| Host | URL | What |
|---|---|---|
| **Backend** | https://sih26167-xqgi.onrender.com | FastAPI + raster engine (health: `/health`) |
| **Frontend** | https://sih-26167.vercel.app | React + MapLibre console (proxies `/api/*` to Render) |

---

## 🚀 Quickstart

### Backend Setup (FastAPI + Python 3.11+)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

cd backend
uvicorn app.main:app --reload --port 8000

# self-check
python -m pytest tests/          # 50 passed, 1 skipped
```

### Frontend Setup (React + Vite)
```bash
cd frontend
npm install
npm run dev                      # proxies /api → localhost:8000
npm run lint && npm run build    # gate
```

---

## 🏆 SIH Winning Highlights
- **No JPEG wrappers:** Native GeoTIFF array parsing via `rasterio`.
- **Real coordinates:** Every polygon reprojected to EPSG:4326 via the affine matrix.
- **True Cross-Modal Fusion:** SAR recovers water optical NDWI cannot (cloud-penetration demo).
- **Grounded, honest numbers:** 50 passing tests; CI never swallows failures.
