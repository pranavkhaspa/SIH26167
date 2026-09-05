import pytest
from app.agent_router import SatQueryAgentRouter
from app.sample_data import make_optical, make_sar

def test_classify_intent():
    router = SatQueryAgentRouter()
    query1 = {"query": "show water change after flood"}
    query2 = {"query": "process sentinel-1 sar radar"}
    query3 = {"query": "what's the NDWI here?"}
    assert router.classify_intent(query1)["intent"] == "BITEMPORAL_CHANGE_DETECTION"
    assert router.classify_intent(query2)["intent"] == "CROSS_MODAL_SAR_FUSION"
    assert router.classify_intent(query3)["intent"] == "SINGLE_IMAGE_VQA"

def test_execute_tools_vqa_real_file(tmp_path_factory):
    tif = make_optical(tmp_path_factory.mktemp("vqa") / "opt.tif", size=128)
    state = {
        "query": "detect water",
        "intent": "SINGLE_IMAGE_VQA",
        "geotiff_path": str(tif),
        "metrics": None, "geojson": None, "narrative": None,
    }
    out = SatQueryAgentRouter.execute_tools(state)
    assert out["intent"] == "SINGLE_IMAGE_VQA"
    assert out["metrics"]["pixel_count"] > 0
    assert out["metrics"]["area_sq_km"] > 0
    for feat in out["geojson"]["features"]:
        ring = feat["geometry"]["coordinates"][0]
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        assert all(67.0 < lon < 98.0 for lon in lons)
        assert all(5.0 < lat < 37.0 for lat in lats)

def test_execute_tools_sar_real_file(tmp_path_factory):
    tif = make_sar(tmp_path_factory.mktemp("sar") / "sar.tif", size=128)
    state = {
        "query": "process sar scene",
        "intent": "CROSS_MODAL_SAR_FUSION",
        "sar_path": str(tif),
        "metrics": None, "geojson": None, "narrative": None,
    }
    out = SatQueryAgentRouter.execute_tools(state)
    assert out["intent"] == "CROSS_MODAL_SAR_FUSION"
    assert out["metrics"]["pixel_count"] > 0
    assert out["metrics"]["area_sq_km"] > 0
    for feat in out["geojson"]["features"]:
        ring = feat["geometry"]["coordinates"][0]
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        assert all(67.0 < lon < 98.0 for lon in lons)
        assert all(5.0 < lat < 37.0 for lat in lats)

def test_execute_tools_bitemporal_real_files(tmp_path_factory):
    pre = make_optical(tmp_path_factory.mktemp("bi") / "pre.tif", size=128)
    post = make_optical(tmp_path_factory.mktemp("bi") / "post.tif", size=128)
    state = {
        "query": "show flood change",
        "intent": "BITEMPORAL_CHANGE_DETECTION",
        "pre_event_path": str(pre),
        "post_event_path": str(post),
        "metrics": None, "geojson": None, "narrative": None,
    }
    out = SatQueryAgentRouter.execute_tools(state)
    assert out["intent"] == "BITEMPORAL_CHANGE_DETECTION"
    assert "metrics" in out and "geojson" in out
    for feat in out["geojson"]["features"]:
        ring = feat["geometry"]["coordinates"][0]
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        assert all(67.0 < lon < 98.0 for lon in lons)
        assert all(5.0 < lat < 37.0 for lat in lats)

def test_execute_tools_missing_path_raises():
    state = {
        "query": "detect water",
        "intent": "SINGLE_IMAGE_VQA",
        "metrics": None, "geojson": None, "narrative": None,
    }
    with pytest.raises(RuntimeError, match="SINGLE_IMAGE_VQA requires geotiff_path"):
        SatQueryAgentRouter.execute_tools(state)

def test_execute_tools_missing_sar_path_raises():
    state = {
        "query": "process sar",
        "intent": "CROSS_MODAL_SAR_FUSION",
        "metrics": None, "geojson": None, "narrative": None,
    }
    with pytest.raises(RuntimeError, match="CROSS_MODAL_SAR_FUSION requires"):
        SatQueryAgentRouter.execute_tools(state)

def test_execute_tools_missing_bitemporal_paths_raises():
    state = {
        "query": "show flood change",
        "intent": "BITEMPORAL_CHANGE_DETECTION",
        "metrics": None, "geojson": None, "narrative": None,
    }
    with pytest.raises(RuntimeError, match="BITEMPORAL_CHANGE_DETECTION requires"):
        SatQueryAgentRouter.execute_tools(state)
