from typing import Dict, Any, List, TypedDict, Optional
import os
from langgraph.graph import StateGraph, END
from app.raster_engine import RemoteSensingRasterEngine
from app.change_engine import BiTemporalChangeEngine
from app.vlm_adapter import RemoteSensingVLMAdapter

class SatQueryState(TypedDict, total=False):
    query: str
    intent: Optional[str]
    geotiff_path: Optional[str]
    sar_path: Optional[str]
    pre_event_path: Optional[str]
    post_event_path: Optional[str]
    metrics: Optional[Dict[str, Any]]
    geojson: Optional[Dict[str, Any]]
    narrative: Optional[str]

class SatQueryAgentRouter:
    """LangGraph Agentic Tool Dispatcher and State Router."""

    @staticmethod
    def classify_intent(state: SatQueryState) -> SatQueryState:
        """Classify user query into operational execution intent."""
        query = state["query"].lower()
        if "change" in query or "flood" in query or "bitemporal" in query or "compare" in query:
            state["intent"] = "BITEMPORAL_CHANGE_DETECTION"
        elif "sar" in query or "radar" in query or "cloud" in query:
            state["intent"] = "CROSS_MODAL_SAR_FUSION"
        else:
            state["intent"] = "SINGLE_IMAGE_VQA"
        return state

    @staticmethod
    def execute_tools(state: SatQueryState) -> SatQueryState:
        """Execute raster or change tools based on classified intent using REAL files."""
        intent = state.get("intent", "SINGLE_IMAGE_VQA")

        if intent == "SINGLE_IMAGE_VQA":
            path = state.get("geotiff_path")
            if not path:
                raise RuntimeError("SINGLE_IMAGE_VQA requires geotiff_path to be set")
            with RemoteSensingRasterEngine(path) as engine:
                ndwi = engine.dataset_ndwi(green_index=2, nir_index=3)
                mask = engine.water_mask(ndwi, threshold=0.1)
                metrics = engine.real_surface_area(mask)
                geojson = BiTemporalChangeEngine.extract_vector_polygons(
                    mask, engine.transform, crs=engine.crs, min_area_pixels=5
                )
                state["metrics"] = metrics
                state["geojson"] = geojson
                state["narrative"] = SatQueryAgentRouter._vlm_narrative(
                    state.get("query", ""),
                    metrics,
                    path,
                    (
                        f"Single Image Water Analysis Complete. Detected {metrics['area_sq_km']} sq km "
                        f"surface water across {metrics['pixel_count']} pixels."
                    ),
                )

        elif intent == "CROSS_MODAL_SAR_FUSION":
            path = state.get("sar_path") or state.get("geotiff_path")
            if not path:
                raise RuntimeError("CROSS_MODAL_SAR_FUSION requires sar_path or geotiff_path to be set")
            with RemoteSensingRasterEngine(path) as engine:
                band = engine.read_band(1)
                sigma0_db = RemoteSensingRasterEngine.process_sar_decibel(band)
                mask = RemoteSensingRasterEngine.extract_sar_water_mask(sigma0_db, threshold_db=-18.0)
                metrics = engine.real_surface_area(mask)
                geojson = BiTemporalChangeEngine.extract_vector_polygons(
                    mask, engine.transform, crs=engine.crs, min_area_pixels=5
                )
                state["metrics"] = metrics
                state["geojson"] = geojson
                state["narrative"] = SatQueryAgentRouter._vlm_narrative(
                    state.get("query", ""),
                    metrics,
                    path,
                    (
                        f"All-Weather C-Band SAR Water Mask Extracted. Identified {metrics['area_sq_km']} sq km "
                        f"water body area across {metrics['pixel_count']} pixels."
                    ),
                )

        elif intent == "BITEMPORAL_CHANGE_DETECTION":
            pre = state.get("pre_event_path")
            post = state.get("post_event_path")
            if not pre or not post:
                raise RuntimeError("BITEMPORAL_CHANGE_DETECTION requires pre_event_path and post_event_path to be set")
            with RemoteSensingRasterEngine(pre) as eng_pre, RemoteSensingRasterEngine(post) as eng_post:
                ndwi_t1 = eng_pre.dataset_ndwi(green_index=2, nir_index=3)
                ndwi_t2 = eng_post.dataset_ndwi(green_index=2, nir_index=3)
                ndwi_t1, ndwi_t2 = BiTemporalChangeEngine.align_ndwi_pair(
                    ndwi_t1, eng_pre, ndwi_t2, eng_post
                )
                water_t1 = eng_pre.water_mask(ndwi_t1, threshold=0.1)
                water_t2 = eng_pre.water_mask(ndwi_t2, threshold=0.1)
                delta = BiTemporalChangeEngine.compute_bitemporal_delta_ndwi(ndwi_t1, ndwi_t2)
                inundated = BiTemporalChangeEngine.detect_inundation_change(water_t1, water_t2)
                metrics = eng_pre.real_surface_area(inundated)
                geojson = BiTemporalChangeEngine.extract_vector_polygons(
                    inundated, eng_pre.transform, crs=eng_pre.crs, min_area_pixels=5
                )
                state["metrics"] = metrics
                state["geojson"] = geojson
                state["narrative"] = SatQueryAgentRouter._vlm_narrative(
                    state.get("query", ""),
                    metrics,
                    state["post_event_path"],
                    (
                        f"Bi-Temporal Change Detection Complete. Newly inundated flood region: "
                        f"{metrics['area_sq_km']} sq km across {metrics['pixel_count']} pixels."
                    ),
                )

        return state

    @staticmethod
    def _vlm_narrative(query: str, metrics: Dict[str, Any], raster_path: str, fallback: str) -> str:
        """Return a live VLM narrative when enabled; deterministic fallback otherwise."""
        if os.environ.get("SATQUERY_VLM_ENABLED", "1") != "0":
            try:
                return RemoteSensingVLMAdapter().generate_vlm_narrative(query, metrics, raster_path)
            except Exception:
                pass
        return fallback

    def build_graph(self):
        """Construct LangGraph execution pipeline."""
        workflow = StateGraph(SatQueryState)
        workflow.add_node("classify_intent", self.classify_intent)
        workflow.add_node("execute_tools", self.execute_tools)
        workflow.set_entry_point("classify_intent")
        workflow.add_edge("classify_intent", "execute_tools")
        workflow.add_edge("execute_tools", END)
        return workflow.compile()
