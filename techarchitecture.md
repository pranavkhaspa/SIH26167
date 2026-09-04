# Technical Architecture Specification
## SatQuery AI — System Topography & Infrastructure Blueprint

---

## 1. System Architecture Overview

SatQuery AI uses a modular, microservices-ready architecture comprising four primary layers:
1. **Presentation & Geospatial Visualization Layer (React + MapLibre GL 3D)**
2. **API & Agentic Orchestration Layer (FastAPI + LangGraph)**
3. **Geospatial Processing Engine (GDAL / Rasterio / OpenCV)**
4. **Multimodal Inference Engine (Qwen2-VL-7B / PyTorch / Transformers)**

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    CLIENT LAYER (Browser / Field Terminal)                      │
│  - React 18 SPA + Tailwind CSS                                                 │
│  - MapLibre GL 3D (Web Workers for Vector Rendering)                           │
│  - Synchronized Bi-Temporal Split Canvas                                        │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │ REST / WebSocket API
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│              ORCHESTRATION & AGENTIC LAYER (FastAPI + LangGraph)                │
│  - Request Router & Input Inspector                                            │
│  - LangGraph State Machine & Tool Dispatcher                                    │
│  - Session & GeoJSON Memory Buffer                                             │
└─────────┬──────────────────────────────┬──────────────────────────────┬─────────┘
          │                              │                              │
          ▼                              ▼                              ▼
┌──────────────────┐           ┌──────────────────┐           ┌──────────────────┐
│ GEOSPATIAL RASTER│           │   BI-TEMPORAL    │           │ REMOTE SENSING   │
│ PROCESSING ENGINE│           │  CHANGE ENGINE   │           │    VLM ENGINE    │
│ - Rasterio/GDAL  │           │ - Co-Registration│           │ - Qwen2-VL-7B    │
│ - Spectral Math  │           │ - Siamese Diff   │           │   (4-bit AWQ)    │
│   (NDWI/NDVI)    │           │ - Contour Vector │           │ - LoRA Adapter   │
│ - SAR dB Filter  │           │   Extraction     │           │ - Visual Grounding│
└──────────────────┘           └──────────────────┘           └──────────────────┘
```

---

## 2. Component Design & Deep Tech Specifications

### Component A: Geospatial Processing Core (`rasterio` + `numpy` + `gdal`)
- **Multi-Band Extraction:** Reads 16-bit unsigned integer data from GeoTIFF rasters, converting arrays into `float32` arrays for numerical stability during index calculation.
- **Affine Coordinate Transformation:** Binds raster pixels $(x, y)$ to spatial coordinates $(X, Y)$ using the affine matrix:
  $$\begin{bmatrix} X \\ Y \\ 1 \end{bmatrix} = \begin{bmatrix} a & b & c \\ d & e & f \\ 0 & 0 & 1 \end{bmatrix} \begin{bmatrix} x \\ y \\ 1 \end{bmatrix}$$
- **WGS84 Transformation:** Transforms project coordinates (e.g., UTM Zone 45N) into EPSG:4326 (WGS84) for web mapping compatibility.
- **SAR Radar Processing Pipeline:**
  - Input: Sentinel-1 C-band SAR (Intensity).
  - Radiometric Calibration: Conversion to decibel backscatter ($\sigma^0$).
  - Speckle Noise Reduction: 5x5 Median / Lee Filtering.
  - Thresholding: Specular reflection water detection at $\sigma^0 \le -18.0\text{ dB}$.

### Component B: Bi-Temporal Siamese Difference Engine
- **Input:** Baseline Raster ($T_1$) and Post-Event Raster ($T_2$).
- **Spectral Index Difference:** $\Delta\text{NDWI} = \text{NDWI}_{T_2} - \text{NDWI}_{T_1}$.
- **Vector Mask Generation:** Thresholding $\Delta\text{NDWI} > 0.30$ isolates newly flooded terrain, converting binary masks into GeoJSON FeatureCollections via contour extraction (`cv2.findContours`).

### Component C: Remote Sensing VLM Engine
- **Model Base:** Qwen2-VL-7B-Instruct (or Florence-2-large for ultra-fast local CPU/GPU inference).
- **Fine-Tuning Architecture:** Low-Rank Adaptation (LoRA) applied to Query ($Q$) and Value ($V$) projection layers of visual and language transformers ($r=16, \alpha=32$).
- **Benchmark Corpus:** Fine-tuned on BigEarthNet multi-label satellite dataset and RSVQA remote sensing question-answering pairs.
- **Visual Grounding Pipeline:** Normalizes pixel bounding boxes $[y_1, x_1, y_2, x_2]$ to $[0, 1000]$, projecting them onto the raster's affine matrix to produce real-world geographic bounding polygons.

### Component D: LangGraph Agentic Supervisor
- State Schema:
  ```python
  class SatQueryState(TypedDict):
      user_query: str
      image_paths: List[str]
      modality: str  # single_optical, optical_sar_pair, bitemporal_pair
      detected_intent: str
      computed_metrics: Dict[str, Any]
      geojson_data: Dict[str, Any]
      agent_narrative: str
  ```
- **State Graph Workflow:** `Input Inspection ➔ Intent Classification ➔ Tool Routing ➔ Execution ➔ Response Synthesis`.

---

## 3. Data Flow & Sequence Diagram

```
User               Client (React)         FastAPI Router        LangGraph Agent      Raster Engine       VLM Model
 │                       │                      │                      │                   │                 │
 │── Types Query ───────►│                      │                      │                   │                 │
 │   & Uploads GeoTIFF   │── POST /query ──────►│                      │                   │                 │
 │                       │                      │── Invoke Graph ─────►│                   │                 │
 │                       │                      │                      │── Inspect Intent ─►                 │
 │                       │                      │                      │── Execute Math ──►│                 │
 │                       │                      │                      │◄─ Return Metrics ─│                 │
 │                       │                      │                      │── Execute VQA ────────────────────►│
 │                       │                      │                      │◄─ Return Grounding BBoxes ─────────│
 │                       │                      │◄─ Return GeoJSON ────│                                     │
 │                       │                      │   + Markdown Text    │                                     │
 │◄── Renders 3D Map ────│                      │                      │                                     │
 │    + Highlights BBox  │                      │                      │                                     │
```

---

## 4. Hardware, Environment & API Interfaces

### Backend Environment Requirements
- **Language:** Python 3.11+
- **Key Dependencies:** `rasterio`, `gdal`, `geopandas`, `shapely`, `torch`, `transformers`, `peft`, `langgraph`, `fastapi`, `uvicorn`.
- **Inference Runtime:** PyTorch 2.2+ with CUDA 12.1 (GPU) or ONNX Runtime (CPU).

### Frontend Environment Requirements
- **Framework:** React 18 + Vite
- **Libraries:** `maplibre-gl`, `tailwindcss`, `lucide-react`, `recharts`.

### API Specifications
- `POST /api/v1/ingest`: Uploads GeoTIFF files, extracts metadata, bounds, and band count.
- `POST /api/v1/query`: Accepts natural language prompt, triggers LangGraph agent, streams text response + GeoJSON payload.
- `GET /api/v1/export/report`: Generates downloadable PDF assessment report.
