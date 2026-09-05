from fastapi import FastAPI, HTTPException, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
import os
import re
from pathlib import Path

from app.agent_router import SatQueryAgentRouter
from app.raster_engine import RemoteSensingRasterEngine
from app.change_engine import BiTemporalChangeEngine
from app.sample_data import make_cloudy_optical, make_bitemporal_pair

app = FastAPI(
    title="SatQuery AI API",
    description="Remote Sensing GeoTIFF & SAR Multi-Modal Agentic API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://staging.satquery.ai",
        "https://satquery.ai",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads"
DEMO_DIR = Path(__file__).resolve().parent.parent / "data" / "demo"

_uploads: Dict[str, str] = {}
_demo_written = {"optical": False, "sar": False, "cloudy_optical": False, "pre": False, "post": False}


def _register(path: str) -> None:
    name = os.path.basename(path).lower()
    if "sar" in name or "radar" in name:
        _uploads["sar_path"] = path
        _uploads["last_sar"] = path
    else:
        _uploads["optical_path"] = path
        _uploads["last_optical"] = path


def _ensure_demo():
    from app.sample_data import make_optical, make_sar
    if not _demo_written["optical"]:
        p = DEMO_DIR / "demo_optical.tif"
        make_optical(p, size=128)
        _uploads["demo_optical"] = str(p)
        _demo_written["optical"] = True
    if not _demo_written["sar"]:
        p = DEMO_DIR / "demo_sar.tif"
        make_sar(p, size=128)
        _uploads["demo_sar"] = str(p)
        _demo_written["sar"] = True


def _ensure_demo_cloud():
    _ensure_demo()
    if not _demo_written["cloudy_optical"]:
        p = DEMO_DIR / "demo_cloudy_optical.tif"
        make_cloudy_optical(p, size=128, cloud_cover=0.75)
        _uploads["demo_cloudy_optical"] = str(p)
        _demo_written["cloudy_optical"] = True
    return (
        _uploads["demo_cloudy_optical"],
        _uploads["demo_sar"],
    )


def _ensure_demo_bitemporal():
    if not (_demo_written["pre"] and _demo_written["post"]):
        pre, post = make_bitemporal_pair(DEMO_DIR, size=160)
        _uploads["demo_pre"] = str(pre)
        _uploads["demo_post"] = str(post)
        _demo_written["pre"] = True
        _demo_written["post"] = True
    return _uploads["demo_pre"], _uploads["demo_post"]


def _sanitize(name: str) -> str:
    base = os.path.splitext(name)[0]
    base = re.sub(r"[^a-zA-Z0-9_\-]", "_", base)
    suffix = os.path.splitext(name)[1] or ".tif"
    if suffix.lower() not in (".tif", ".tiff", ".gtif"):
        suffix = ".tif"
    return base + suffix


class QueryRequest(BaseModel):
    query: str
    geotiff_path: Optional[str] = None
    sar_path: Optional[str] = None
    pre_event_path: Optional[str] = None
    post_event_path: Optional[str] = None


class ChangeAnalysisRequest(BaseModel):
    pre_event_path: str
    post_event_path: str
    query: Optional[str] = "detect inundation change"


@app.get("/health")
@app.get("/healthz")
def health_check():
    return {"status": "healthy", "service": "satquery-backend"}


@app.post("/api/v1/ingest")
def ingest_geotiff(file: UploadFile = File(...)):
    """Upload a 16-bit GeoTIFF; return real metadata, spectral indices, water area & GeoJSON."""
    filename = file.filename or "upload.tif"
    if not filename.lower().endswith((".tif", ".tiff", ".gtif")):
        raise HTTPException(status_code=400, detail="Only GeoTIFF files (.tif/.tiff) are supported.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_name = _sanitize(filename)
    saved_path = UPLOAD_DIR / saved_name

    with open(saved_path, "wb") as f:
        f.write(file.file.read())

    path = str(saved_path)
    _register(path)

    try:
        with RemoteSensingRasterEngine(path) as engine:
            crs = engine.crs.to_string() if engine.crs else None
            ndwi = engine.dataset_ndwi(green_index=2, nir_index=3)
            ndvi = engine.dataset_ndvi(red_index=1, nir_index=3)
            water_mask = engine.water_mask(ndwi, threshold=0.1)
            area = engine.real_surface_area(water_mask)
            geojson = BiTemporalChangeEngine.extract_vector_polygons(
                water_mask, engine.transform, crs=engine.crs, min_area_pixels=5
            )
            return {
                "status": "success",
                "filename": file.filename,
                "path": path,
                "data_source": path,
                "metadata": {
                    "driver": "GTiff",
                    "crs": crs,
                    "width": engine.width,
                    "height": engine.height,
                    "bands": engine.count,
                    "bounds": list(engine.bounds),
                    "pixel_size_m": area["pixel_size_m"],
                },
                "indices": {
                    "ndwi": {
                        "min": round(float(ndwi.min()), 4),
                        "max": round(float(ndwi.max()), 4),
                    },
                    "ndvi": {
                        "min": round(float(ndvi.min()), 4),
                        "max": round(float(ndvi.max()), 4),
                    },
                },
                "metrics": area,
                "geojson": geojson,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {e}")


@app.post("/api/v1/query")
def process_query(request: QueryRequest) -> Dict[str, Any]:
    try:
        intent = SatQueryAgentRouter.classify_intent({"query": request.query})["intent"]

        state: Dict[str, Any] = {
            "query": request.query,
            "intent": None,
            "metrics": None,
            "geojson": None,
            "narrative": None,
        }

        if intent == "BITEMPORAL_CHANGE_DETECTION":
            pre = request.pre_event_path
            post = request.post_event_path
            if not pre or not post:
                pre, post = _ensure_demo_bitemporal()
            state["pre_event_path"] = pre
            state["post_event_path"] = post
        elif intent == "CROSS_MODAL_SAR_FUSION":
            sar = request.sar_path or _uploads.get("last_sar")
            if not sar:
                _ensure_demo()
                sar = _uploads.get("demo_sar")
            state["sar_path"] = sar
        else:
            geo = request.geotiff_path or _uploads.get("last_optical")
            if not geo:
                _ensure_demo()
                geo = _uploads.get("demo_optical")
            state["geotiff_path"] = geo

        router = SatQueryAgentRouter()
        graph = router.build_graph()
        result = graph.invoke(state)

        data_source = (
            state.get("pre_event_path") and state.get("post_event_path")
            and f"{state['pre_event_path']}+{state['post_event_path']}"
        ) or state.get("geotiff_path") or state.get("sar_path") or ""

        if intent == "BITEMPORAL_CHANGE_DETECTION":
            data_source = f"{state.get('pre_event_path','')},{state.get('post_event_path','')}"

        return {
            "status": "success",
            "intent": result.get("intent"),
            "narrative": result.get("narrative"),
            "metrics": result.get("metrics"),
            "geojson": result.get("geojson"),
            "data_source": data_source,
        }
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/analyze-change")
def analyze_change(request: ChangeAnalysisRequest) -> Dict[str, Any]:
    try:
        router = SatQueryAgentRouter()
        graph = router.build_graph()
        initial_state = {
            "query": request.query,
            "intent": "BITEMPORAL_CHANGE_DETECTION",
            "pre_event_path": request.pre_event_path,
            "post_event_path": request.post_event_path,
            "metrics": None,
            "geojson": None,
            "narrative": None,
        }
        result = graph.invoke(initial_state)
        return {
            "status": "success",
            "intent": result.get("intent"),
            "narrative": result.get("narrative"),
            "metrics": result.get("metrics"),
            "geojson": result.get("geojson"),
            "data_source": f"{request.pre_event_path},{request.post_event_path}",
        }
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/demo/cloud-penetration")
def cloud_penetration_demo() -> Dict[str, Any]:
    """SAR vs optical under cloud: optical NDWI fails, C-band SAR penetrates (all-weather)."""
    try:
        cloudy_optical_path, sar_path = _ensure_demo_cloud()
        out: Dict[str, Any] = {"status": "success", "data_source": {}}

        with RemoteSensingRasterEngine(cloudy_optical_path) as engine:
            ndwi = engine.dataset_ndwi(green_index=2, nir_index=3)
            optical_mask = engine.water_mask(ndwi, threshold=0.1)
            optical_frac = float(optical_mask.mean())
            optical_metrics = engine.real_surface_area(optical_mask)
            optical_geojson = BiTemporalChangeEngine.extract_vector_polygons(
                optical_mask, engine.transform, min_area_pixels=5, crs=engine.crs
            )

        with RemoteSensingRasterEngine(sar_path) as engine:
            sar_amp = engine.read_band(1)
            sigma0_db = engine.process_sar_decibel(sar_amp)
            sar_mask = engine.extract_sar_water_mask(sigma0_db, threshold_db=-18.0)
            sar_frac = float(sar_mask.mean())
            sar_metrics = engine.real_surface_area(sar_mask)
            sar_geojson = BiTemporalChangeEngine.extract_vector_polygons(
                sar_mask, engine.transform, min_area_pixels=5, crs=engine.crs
            )

        out["optical"] = {
            "mask_frac": round(optical_frac, 4),
            "metrics": optical_metrics,
            "geojson": optical_geojson,
        }
        out["sar"] = {
            "mask_frac": round(sar_frac, 4),
            "metrics": sar_metrics,
            "geojson": sar_geojson,
        }
        out["data_source"]["optical"] = cloudy_optical_path
        out["data_source"]["sar"] = sar_path
        out["narrative"] = (
            f"Optical NDWI masked only {optical_frac:.1%} of the monsoon scene: an optically-thick "
            f"cloud deck (high DN in all 4 bands) hides the water body. C-band SAR radars transmit through "
            f"cloud and the -18 dB backscatter mask recovered {sar_frac:.1%} of the scene "
            f"({sar_metrics['area_sq_km']} km2), demonstrating all-weather monsoon capability."
        )
        return out
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cloud-penetration demo failed: {e}")


@app.post("/api/v1/demo/change-detect")
def change_detect_demo() -> Dict[str, Any]:
    """Bi-temporal flood demo: T1 vs T2 aligned pair -> ΔNDWI -> newly inundated vectors + km²."""
    try:
        pre_path, post_path = _ensure_demo_bitemporal()
        with RemoteSensingRasterEngine(pre_path) as eng_pre, RemoteSensingRasterEngine(post_path) as eng_post:
            ndwi_t1 = eng_pre.dataset_ndwi(green_index=2, nir_index=3)
            ndwi_t2 = eng_post.dataset_ndwi(green_index=2, nir_index=3)
            ndwi_t1, ndwi_t2 = BiTemporalChangeEngine.align_ndwi_pair(
                ndwi_t1, eng_pre, ndwi_t2, eng_post
            )
            water_t1 = eng_pre.water_mask(ndwi_t1, threshold=0.1)
            water_t2 = eng_pre.water_mask(ndwi_t2, threshold=0.1)
            delta = BiTemporalChangeEngine.compute_bitemporal_delta_ndwi(ndwi_t1, ndwi_t2)
            inundated = BiTemporalChangeEngine.detect_inundation_change(water_t1, water_t2)

            t1_metrics = eng_pre.real_surface_area(water_t1)
            t2_metrics = eng_pre.real_surface_area(water_t2)
            change_metrics = eng_pre.real_surface_area(inundated)
            geojson = BiTemporalChangeEngine.extract_vector_polygons(
                inundated, eng_pre.transform, crs=eng_pre.crs, min_area_pixels=8
            )
        narrative = (
            f"Bi-temporal change detected: surface water grew from {t1_metrics['area_sq_km']} km2 "
            f"(T1) to {t2_metrics['area_sq_km']} km2 (T2). Newly inundated flood regions cover "
            f"{change_metrics['area_sq_km']} km2 across {change_metrics['pixel_count']} pixels."
        )
        return {
            "status": "success",
            "narrative": narrative,
            "metrics": {
                "t1_water": t1_metrics,
                "t2_water": t2_metrics,
                "change": change_metrics,
                "delta_ndwi": {
                    "min": round(float(delta.min()), 4),
                    "max": round(float(delta.max()), 4),
                },
            },
            "geojson": geojson,
            "data_source": {"pre": pre_path, "post": post_path},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Change-detect demo failed: {e}")


@app.get("/api/v1/demo/change-raster/{acquisition}")
def change_raster_demo(acquisition: str) -> Response:
    acq = acquisition.lower()
    if acq not in ("pre", "post"):
        raise HTTPException(status_code=404, detail="Unknown acquisition")
    pre_path, post_path = _ensure_demo_bitemporal()
    path = pre_path if acq == "pre" else post_path
    with RemoteSensingRasterEngine(path) as engine:
        png = BiTemporalChangeEngine.render_acquisition_overlay_png(engine)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300"},
    )
