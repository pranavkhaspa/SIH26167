# Product Requirements Document (PRD)
## SatQuery AI — Vision-Language Assistant for Multimodal Remote Sensing
**Problem Statement ID:** SIH26167  
**Sponsoring Organization:** Indian Space Research Organisation (ISRO)  
**Target Event:** Smart India Hackathon 2026 (Software Track)  
**Document Version:** 1.0.0  
**Status:** Approved for Implementation  

---

## 1. Executive Summary & Vision
SatQuery AI is an agentic, multimodal vision-language intelligence platform designed to democratize satellite Earth Observation (EO) data. It enables non-expert decision-makers (disaster relief teams, district administrations, agriculture officers) to query complex 16-bit multi-spectral (Sentinel-2) and Synthetic Aperture Radar (Sentinel-1 SAR) imagery using natural language queries, returning actionable natural language insights paired with georeferenced spatial vector overlays (EPSG:4326 GeoJSON).

---

## 2. Target Personas & Use Cases

### Persona 1: Disaster Management Officer (NDRF / SDMA)
- **Pain Point:** Optical satellite imagery during monsoon flooding is blocked by dense cloud cover.
- **Workflow in SatQuery AI:** Asks in plain Hindi/English: *"Show flood extent in Silchar under current cloud cover and highlight cutoff roads."*
- **Delivered Output:** System automatically activates Sentinel-1 C-band SAR radar pipeline, computes water backscatter through clouds, delineates inundated zones, and outputs GeoJSON polygons with exact square kilometer figures.

### Persona 2: District Agriculture Officer
- **Pain Point:** Lack of tools to verify crop damage claims after unseasonal hail or flash floods across thousands of fragmented parcels.
- **Workflow in SatQuery AI:** Uploads pre-disaster (T1) and post-disaster (T2) GeoTIFFs: *"Identify crop parcels with severe vegetation index drop."*
- **Delivered Output:** Bi-temporal difference engine computes $\Delta\text{NDVI}$, extracts parcel boundaries, and calculates hectare-level damage metrics.

### Persona 3: Urban Planning Authority
- **Pain Point:** Manual digitizing of urban sprawl, encroachment into water bodies, and infrastructure progress is slow and expensive.
- **Workflow in SatQuery AI:** *"Identify all new construction inside the wetland buffer zone between 2023 and 2025."*
- **Delivered Output:** Change vector analysis delineates new built-up areas (NDBI) intersecting environmental buffer zones.

---

## 3. Product Scope & Functional Requirements

### Module 1: Geospatial Ingestion & Raster Processing (Core)
- **FR-1.1:** Ingestion of native 16-bit GeoTIFF, Cloud-Optimized GeoTIFF (COG), and multi-band Sentinel-2 / Sentinel-1 rasters.
- **FR-1.2:** Extraction of coordinate reference system (CRS), affine transformation matrices, and conversion of pixel coordinates to EPSG:4326 (WGS84) latitude/longitude coordinates.
- **FR-1.3:** Automated calculation of physical spectral indices:
  - $\text{NDWI} = \frac{\text{Green} - \text{NIR}}{\text{Green} + \text{NIR}}$ (Water delineation)
  - $\text{NDVI} = \frac{\text{NIR} - \text{Red}}{\text{NIR} + \text{Red}}$ (Vegetation health)
  - $\text{NDBI} = \frac{\text{SWIR} - \text{NIR}}{\text{SWIR} + \text{NIR}}$ (Built-up index)
- **FR-1.4:** SAR amplitude processing: Lee Speckle Filtering, dB scaling ($10 \cdot \log_{10}(\text{DN}^2)$), and thresholding for all-weather flood detection.

### Module 2: Multimodal Remote Sensing VLM & Fine-Tuning
- **FR-2.1:** Integration of an open-weight Vision-Language model (Qwen2-VL-7B / Florence-2-large).
- **FR-2.2:** Adaptation via PEFT/LoRA on open remote sensing benchmarks (BigEarthNet / RSVQA / ChangeOS).
- **FR-2.3:** Visual Question Answering (VQA) supporting single-image descriptive queries, cross-modal comparison, and bi-temporal change reasoning.
- **FR-2.4:** Text-guided visual grounding: Returns bounding boxes `[ymin, xmin, ymax, xmax]` for queried features (e.g., bridges, water bodies, aircraft, runways).

### Module 3: Bi-Temporal Change Detection Engine
- **FR-3.1:** Co-registration alignment verification between T1 (baseline) and T2 (target) image pairs.
- **FR-3.2:** Siamese difference computation and Change Vector Analysis (CVA).
- **FR-3.3:** Extraction of change contours into standardized GeoJSON polygons containing area statistics (hectares, sq km).

### Module 4: Agentic Tool Orchestration (LangGraph)
- **FR-4.1:** Autonomous intent parsing: Decides whether query requires single-image VQA, SAR radar penetration, or bi-temporal comparison.
- **FR-4.2:** Deterministic spatial tool execution with fallback handling.
- **FR-4.3:** Multi-step reasoning: Chain of Thought (CoT) synthesis combining numerical raster statistics with VLM semantic descriptions.

### Module 5: Interactive Web Console & Geospatial Visualization
- **FR-5.1:** High-performance MapLibre GL 3D / Deck.gl web canvas supporting raster layers and vector overlays.
- **FR-5.2:** Synchronized split-slider comparison mode for T1 vs T2 imagery.
- **FR-5.3:** Natural language chat drawer with token streaming, citations, and interactive click-to-zoom for detected feature polygons.
- **FR-5.4:** Export capabilities: GeoJSON vector export and automated PDF Situation Assessment Report generator.

---

## 4. Non-Functional Requirements (NFRs)

| Metric | Target Specification |
|---|---|
| **Query Latency** | $\le 3.5\text{ seconds}$ for tool execution & VLM response on local GPU / API. |
| **Raster Ingestion Speed** | $\le 2.0\text{ seconds}$ for 1024x1024 multi-band GeoTIFF chip. |
| **Memory Footprint** | Backend runtime $\le 8\text{GB VRAM}$ (4-bit quantized VLM) for edge workstation deployment. |
| **Geospatial Precision** | Zero CRS reprojection drift; polygon vector alignment within 1 pixel ground resolution. |
| **Data Privacy / Security** | Air-gapped / on-premise execution mode for sensitive national satellite feeds. |

---

## 5. Success Metrics & SIH Winning Criteria

1. **Benchmark Accuracy:** F1-Score $\ge 0.86$ on BigEarthNet land-cover classification and mIoU $\ge 0.78$ on flood inundation masks.
2. **Judge Wow-Factor:** 0 to 60-second transition from raw cloud-covered optical feed to cloud-penetrating SAR flood map with live vector export.
3. **ISRO Alignment:** 100% compliance with official problem statement requirements (GeoTIFF ingest, BigEarthNet adaptation, SAR+Optical pair reasoning, bi-temporal change detection).
