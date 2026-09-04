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
| [`PRD.md`](./PRD.md) | Product Requirements Document (User personas, Functional & Non-Functional Requirements, Success Metrics) |
| [`techarchitecture.md`](./techarchitecture.md) | Deep Technical Architecture (Affine coordinate math, SAR dB calculations, LangGraph schema, API specs) |
| [`deployment.md`](./deployment.md) | CI/CD Automation, Docker Containerization & Autonomous Building Pipeline |
| [`plan.md`](./plan.md) | 4-Week Step-by-Step Implementation Roadmap with daily self-check milestones |
| [`CLAUDE.md`](./CLAUDE.md) | Project instructions, coding rules, environment setup, and anti-disqualification standards |
| [`SIH26167.md`](./SIH26167.md) | Master Problem Statement specification, code templates, and 3-5 minute judge pitch script |
| [`SIH26167_SatQuery_AI.md`](./SIH26167_SatQuery_AI.md) | Executive winning strategy and Claude token feasibility analysis |

---

## ⚡ Key Technical Features

1. **Native 16-Bit GeoTIFF Ingestion:** Preserves all multi-spectral bands (NIR, Red-Edge, SWIR) without lossy 8-bit RGB down-sampling.
2. **C-Band SAR Cloud Penetration:** Converts Sentinel-1 radar intensity to decibels ($\sigma^0$) with Lee filtering for all-weather flood detection.
3. **Bi-Temporal Siamese Difference Engine:** Computes $\Delta\text{NDWI}$ across $T_1$ and $T_2$ rasters to extract newly inundated land area ($\text{km}^2$) and vector boundaries.
4. **Agentic Tool Orchestrator (LangGraph):** Automatically classifies user queries and executes spatial tools.
5. **Real-World Coordinate Grounding:** Transforms pixel bounding boxes into WGS84 (EPSG:4326) GeoJSON polygons via affine transformation matrices.
6. **3D Web Console (React + MapLibre GL):** Synchronized temporal split-slider with token-streaming conversational assistant.

---

## 🚀 Quickstart

### Backend Setup (FastAPI + Python 3.11+)
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install fastapi uvicorn rasterio numpy opencv-python-headless geopandas shapely langgraph torch transformers

# Start backend server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup (React + Vite)
```bash
cd frontend
npm install
npm run dev
```

---

## 🏆 SIH Winning Highlights
- **No JPEG wrappers:** Native GeoTIFF array parsing via `rasterio`.
- **True Cross-Modal Fusion:** Optical + SAR joint reasoning for monsoon conditions.
- **ISRO Benchmark Aligned:** Adapted on the public BigEarthNet dataset.
