# SatQuery AI — 4-Week Comprehensive Master Implementation Plan

This execution plan breaks down the development of SatQuery AI into a 4-week structured roadmap. 
**Operational Rule for Claude:** Claude will focus on **ONE specific day/task at a time**, verify its completion using lightweight self-checks, update this plan dynamically based on findings/blockers, and then proceed to the next deliverable.

---

## 📅 WEEK 1: Core Geospatial Raster Engine & Preprocessing Pipeline
**Goal:** Build a high-performance Python engine capable of ingesting 16-bit GeoTIFFs, computing physical spectral indices ($\text{NDWI}, \text{NDVI}$), processing C-band SAR backscatter, and converting pixel coordinates to EPSG:4326 GeoJSON polygons.

### Day 1: Setup & GeoTIFF Ingestion Engine
- [ ] Setup Python environment with `rasterio`, `numpy`, `gdal`, and `shapely`.
- [ ] Create `backend/app/raster_engine.py`.
- [ ] Implement multi-band GeoTIFF loader extracting 16-bit raster arrays, metadata, CRS, and affine transform matrix.
- [ ] Implement pixel-to-WGS84 lat/lon coordinate transformation function.
- [ ] **Self-Check:** Write unit test confirming affine transformation converts top-left pixel $(0,0)$ to accurate bounding coordinates.

### Day 2: Optical Spectral Index Processor
- [ ] Implement $\text{NDWI} = \frac{\text{Green} - \text{NIR}}{\text{Green} + \text{NIR}}$ calculation for water extraction.
- [ ] Implement $\text{NDVI} = \frac{\text{NIR} - \text{Red}}{\text{NIR} + \text{Red}}$ calculation for vegetation health analysis.
- [ ] Implement binary thresholding and compute physical surface area ($\text{km}^2$, hectares) based on pixel ground resolution.
- [ ] **Self-Check:** Verify NDWI calculation on sample multi-spectral GeoTIFF and validate extracted water surface area against baseline calculation.

### Day 3: C-Band SAR Radar Processing Engine
- [ ] Implement Sentinel-1 SAR intensity parsing (VV/VH polarizations).
- [ ] Implement radiometry decibel conversion ($\sigma^0 = 10 \cdot \log_{10}(\text{DN}^2)$).
- [ ] Implement 5x5 Lee/Median Speckle Noise Reduction filter.
- [ ] Implement all-weather water extraction at $\sigma^0 \le -18.0\text{ dB}$ threshold.
- [ ] **Self-Check:** Validate SAR water mask extraction under simulated cloud-covered raster inputs.

### Day 4: Vector Polygon Extractor & GeoJSON Builder
- [ ] Integrate OpenCV contour extraction (`cv2.findContours`) over binary raster masks.
- [ ] Convert contour bounding boxes and complex polygon rings to valid EPSG:4326 GeoJSON FeatureCollections.
- [ ] Implement minimum area filtering to discard single-pixel noise artifacts.
- [ ] **Self-Check:** Export generated GeoJSON file and validate syntax using `geojson.io` / JSON parser.

### Day 5: Week 1 Integration & Benchmarking
- [ ] Package raster processing pipeline into a unified class `RemoteSensingRasterEngine`.
- [ ] Measure processing latency for 1024x1024 GeoTIFF chips ($\text{Target} \le 1.5\text{s}$).
- [ ] **Week 1 Milestone Review:** Core spatial engine fully operational.

---

## 📅 WEEK 2: Bi-Temporal Change Detection & Agentic Orchestration Layer
**Goal:** Build the bi-temporal Siamese difference engine and integrate LangGraph to autonomously route user queries to spatial calculation tools.

### Day 6: Co-Registration & Alignment Verifier
- [ ] Create `backend/app/change_engine.py`.
- [ ] Implement bounding-box spatial intersection check between $T_1$ (baseline) and $T_2$ (post-event) rasters.
- [ ] Handle spatial resolution resampling if $T_1$ and $T_2$ spatial resolutions differ.
- [ ] **Self-Check:** Assert error if user inputs non-overlapping $T_1$ and $T_2$ rasters.

### Day 7: Bi-Temporal Difference & Inundation Change Engine
- [ ] Implement $\Delta\text{NDWI} = \text{NDWI}_{T_2} - \text{NDWI}_{T_1}$ difference matrix calculation.
- [ ] Isolate newly flooded pixels ($\text{Water}_{T_2} \land \neg\text{Water}_{T_1}$).
- [ ] Calculate total newly inundated area ($\text{km}^2$) and extract vector bounding polygons.
- [ ] **Self-Check:** Test difference engine on synthetic pre/post-flood raster pair.

### Day 8: LangGraph State Machine Architecture
- [ ] Create `backend/app/agent_router.py`.
- [ ] Define `SatQueryState` schema (user query, image paths, modality, intent, metrics, GeoJSON output, text narrative).
- [ ] Build Intent Classifier node to categorize prompts into: `SINGLE_IMAGE_VQA`, `CROSS_MODAL_SAR_FUSION`, or `BITEMPORAL_CHANGE_DETECTION`.
- [ ] **Self-Check:** Test intent classification on 20 sample natural language prompts.

### Day 9: Tool Routing & Response Synthesizer
- [ ] Connect `RemoteSensingRasterEngine` and `BiTemporalChangeEngine` as executable tools in the LangGraph graph.
- [ ] Build Response Synthesizer node to format structured markdown reports with exact square kilometer metrics and GeoJSON payload attachments.
- [ ] **Self-Check:** Execute end-to-end agent graph run for a sample query: *"Compare June and August rasters and report flood extent."*

### Day 10: Week 2 Integration & Pipeline Validation
- [ ] Build FastAPI server (`backend/app/main.py`) exposing `/api/v1/ingest` and `/api/v1/query`.
- [ ] Measure total end-to-end processing time ($\text{Target} \le 3.0\text{s}$).
- [ ] **Week 2 Milestone Review:** Agentic backend fully functional.

---

## 📅 WEEK 3: Remote Sensing VLM Fine-Tuning & Adapter Integration
**Goal:** Adapt an open-weight Vision-Language Model (Qwen2-VL-7B or Florence-2) on satellite benchmarks (BigEarthNet / RSVQA) for visual question answering and text-guided visual grounding.

### Day 11: Dataset Preparation & Benchmark Pipeline
- [ ] Download sample subset of BigEarthNet multi-spectral satellite patch dataset.
- [ ] Format satellite QA pairs for instruction fine-tuning (`[Image, Query, Target Answer, Bounding Box]`).
- [ ] Create `backend/app/vlm_adapter.py`.
- [ ] **Self-Check:** Verify dataset loader formats images and token sequences correctly.

### Day 12: PEFT / LoRA Fine-Tuning Recipe Setup
- [ ] Configure 4-bit quantization (bitsandbytes / AWQ) for Qwen2-VL-7B.
- [ ] Setup LoRA configuration ($r=16, \alpha=32$) targeting attention projection layers (`q_proj`, `v_proj`).
- [ ] Write PyTorch training loop (`backend/app/train_vlm.py`).
- [ ] **Self-Check:** Run 1 training epoch on Google Colab T4 / local GPU to confirm loss convergence.

### Day 13: Visual Grounding & Pixel-to-Geo Transform
- [ ] Implement text-guided visual grounding tool returning bounding boxes $[y_1, x_1, y_2, x_2]$ normalized to $[0, 1000]$.
- [ ] Connect VLM bounding box output to `RemoteSensingRasterEngine.pixel_to_geo_coords()`.
- [ ] **Self-Check:** Verify that query *"Locate the bridge"* returns a valid EPSG:4326 polygon around the target feature.

### Day 14: VLM & LangGraph Hybrid Fusion
- [ ] Integrate `vlm_adapter.py` into `agent_router.py` as a specialist node for descriptive VQA questions.
- [ ] Implement hybrid reasoning: Numerical raster statistics + VLM semantic natural language summary.
- [ ] **Self-Check:** Execute hybrid query: *"Describe the terrain and calculate total water surface area."*

### Day 15: Week 3 Integration & Inference Optimization
- [ ] Optimize model inference speed (torch.compile / 4-bit quantization).
- [ ] Ensure VRAM consumption remains below 8GB.
- [ ] **Week 3 Milestone Review:** AI/VLM pipeline integrated with spatial raster backend.

---

## 📅 WEEK 4: Frontend Console, Demo Optimization & Pitch Readiness
**Goal:** Build a modern React + MapLibre GL 3D web interface, complete end-to-end integration, optimize for live demo performance, and prepare judge presentation assets.

### Day 16: React & MapLibre GL 3D Setup
- [ ] Initialize React + Vite application (`frontend/`).
- [ ] Install `maplibre-gl`, `tailwindcss`, `lucide-react`.
- [ ] Build interactive 3D map canvas displaying satellite basemaps (Sentinel-2 cloudless WMS).
- [ ] **Self-Check:** Confirm MapLibre canvas renders smoothly with zoom/pan controls.

### Day 17: Bi-Temporal Split-Slider & Layer Shading
- [ ] Implement synchronized split-screen swipe control ($T_1$ baseline left, $T_2$ post-event right).
- [ ] Implement dynamic layer toggle: Optical RGB, SAR Radar Overlay, NDWI Mask, and GeoJSON Change Polygons.
- [ ] **Self-Check:** Verify smooth split-slider operation across dual raster layers.

### Day 18: Agent Chat Drawer & Streaming Integration
- [ ] Build slide-over chat drawer with Markdown rendering and token streaming.
- [ ] Implement instant interactive map zoom when user clicks on a cited GeoJSON polygon tag.
- [ ] Add raster file drop-zone allowing drag-and-drop GeoTIFF ingestion.
- [ ] **Self-Check:** Test complete user journey: Drag GeoTIFF ➔ Ask query ➔ View streaming narrative ➔ See map highlight polygons.

### Day 19: PDF Report Exporter & Offline Mode
- [ ] Build automated PDF Situation Assessment Report generator (exports map screenshot, quantitative metrics, GeoJSON summary).
- [ ] Build offline fallback mode with pre-cached satellite datasets for reliable hackathon presentation.
- [ ] **Self-Check:** Generate sample PDF report and verify layout.

### Day 20: Dry Run, Demo Scripting & Final Polish
- [ ] Conduct end-to-end 3-minute live pitch rehearsal against official ISRO grading rubric.
- [ ] Fix any visual glitches, alignment issues, or edge cases.
- [ ] Finalize code repository documentation and submission package.
- [ ] **Final Milestone:** SatQuery AI fully ready for SIH 2026 Grand Finale victory!

---

## 🔄 Dynamic Adjustment Log
*(Claude will append updates here when tasks are completed or modified based on runtime discovery)*

- **Date:** 2026-09-04 | **Status:** Plan created. Ready to begin Week 1 execution.
