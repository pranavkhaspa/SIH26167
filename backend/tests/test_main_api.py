import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.sample_data import make_optical, make_sar
from app.change_engine import BiTemporalChangeEngine
from app.raster_engine import RemoteSensingRasterEngine
from app.sample_data import make_bitemporal_pair
import cv2
import numpy as np


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_query_bitemporal_demo_fallback(client):
    r = client.post(
        "/api/v1/query",
        json={"query": "Calculate bi-temporal change difference matrix between T1 and T2"},
    )
    assert r.status_code == 200
    d = r.json()
    assert d["intent"] == "BITEMPORAL_CHANGE_DETECTION"
    assert d["metrics"]["area_sq_km"] > 0
    assert d["geojson"]["features"]


def test_ingest_real_geotiff(client, tmp_path_factory):
    tif = make_optical(tmp_path_factory.mktemp("api") / "opt.tif", size=128)
    with open(tif, "rb") as f:
        r = client.post("/api/v1/ingest", files={"file": ("opt.tif", f, "image/tiff")})
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "success"
    assert d["metadata"]["crs"] == "EPSG:32645"
    assert d["metadata"]["bands"] == 4
    assert d["metrics"]["pixel_count"] > 0
    assert d["metrics"]["area_sq_km"] > 0
    assert "path" in d
    assert "data_source" in d
    import os
    assert os.path.exists(d["path"])
    # vector polygons reprojected to real WGS84 (Assam, India)
    for feat in d["geojson"]["features"]:
        ring = feat["geometry"]["coordinates"][0]
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        assert all(67.0 < lon < 98.0 for lon in lons)
        assert all(5.0 < lat < 37.0 for lat in lats)


def test_ingest_rejects_non_geotiff(client):
    r = client.post(
        "/api/v1/ingest", files={"file": ("nota.png", b"PNG!not-a-tiff", "image/png")}
    )
    assert r.status_code == 400
    assert "GeoTIFF" in r.json()["detail"]


def test_query_demo_fallback(client):
    r = client.post("/api/v1/query", json={"query": "detect water"})
    assert r.status_code == 200
    d = r.json()
    assert "data_source" in d
    assert d["data_source"].endswith(".tif")
    assert d["metrics"]["pixel_count"] > 0
    assert d["metrics"]["area_sq_km"] > 0
    for feat in d["geojson"]["features"]:
        ring = feat["geometry"]["coordinates"][0]
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        assert all(67.0 < lon < 98.0 for lon in lons)
        assert all(5.0 < lat < 37.0 for lat in lats)


def test_query_explicit_path(client, tmp_path_factory):
    tif = make_optical(tmp_path_factory.mktemp("q") / "explicit.tif", size=128)
    r = client.post("/api/v1/query", json={"query": "detect water", "geotiff_path": str(tif)})
    assert r.status_code == 200
    d = r.json()
    assert d["data_source"] == str(tif)
    assert d["metrics"]["pixel_count"] > 0
    for feat in d["geojson"]["features"]:
        ring = feat["geometry"]["coordinates"][0]
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        assert all(67.0 < lon < 98.0 for lon in lons)
        assert all(5.0 < lat < 37.0 for lat in lats)


def test_query_sar_explicit_path(client, tmp_path_factory):
    tif = make_sar(tmp_path_factory.mktemp("qs") / "sar.tif", size=128)
    r = client.post("/api/v1/query", json={"query": "process sar radar", "sar_path": str(tif)})
    assert r.status_code == 200
    d = r.json()
    assert d["data_source"] == str(tif)
    assert d["metrics"]["pixel_count"] > 0


def test_query_bitemporal_missing_paths_defaults_to_demo(client):
    r = client.post("/api/v1/query", json={"query": "flood change"})
    assert r.status_code == 200
    d = r.json()
    assert d["intent"] == "BITEMPORAL_CHANGE_DETECTION"
    assert d["metrics"]["area_sq_km"] > 0
    assert d["geojson"]["features"]


def test_analyze_change(client, tmp_path_factory):
    pre = make_optical(tmp_path_factory.mktemp("ac") / "pre.tif", size=128)
    post = make_optical(tmp_path_factory.mktemp("ac") / "post.tif", size=128)
    r = client.post(
        "/api/v1/analyze-change",
        json={"pre_event_path": str(pre), "post_event_path": str(post)},
    )
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "success"
    assert d["intent"] == "BITEMPORAL_CHANGE_DETECTION"
    assert "metrics" in d
    assert d["geojson"]["type"] == "FeatureCollection"
    assert str(pre) in d["data_source"]
    assert str(post) in d["data_source"]


def test_cloud_penetration_demo(client):
    r = client.post("/api/v1/demo/cloud-penetration")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "success"
    assert d["optical"]["mask_frac"] < 0.10  # cloud defeats optical NDWI
    assert d["sar"]["mask_frac"] >= 0.15  # C-band SAR sees water through cloud
    assert "area_sq_km" in d["optical"]["metrics"]
    assert "area_sq_km" in d["sar"]["metrics"]
    assert d["sar"]["geojson"]["type"] == "FeatureCollection"
    assert d["sar"]["geojson"]["features"], "SAR must find water polygons"
    for feat in d["sar"]["geojson"]["features"]:
        ring = feat["geometry"]["coordinates"][0]
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        assert all(67.0 < lon < 98.0 for lon in lons)  # true EPSG:4326 (Assam, India)
        assert all(5.0 < lat < 37.0 for lat in lats)
    assert "optical" in d["data_source"] and "sar" in d["data_source"]
    assert d["data_source"]["optical"].endswith("demo_cloudy_optical.tif")
    assert d["data_source"]["sar"].endswith("demo_sar.tif")
    assert d["narrative"]


def test_change_detect_demo(client):
    r = client.post("/api/v1/demo/change-detect")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "success"
    m = d["metrics"]
    assert m["change"]["area_sq_km"] > 0
    assert m["change"]["pixel_count"] > 0
    assert m["t2_water"]["pixel_count"] > m["t1_water"]["pixel_count"]  # flood grew
    assert "delta_ndwi" in m
    assert d["geojson"]["type"] == "FeatureCollection"
    assert d["geojson"]["features"], "must return newly inundated polygons"
    for feat in d["geojson"]["features"]:
        ring = feat["geometry"]["coordinates"][0]
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        assert all(67.0 < lon < 98.0 for lon in lons)  # true EPSG:4326 (Assam, India)
        assert all(5.0 < lat < 37.0 for lat in lats)
    assert d["data_source"]["pre"].endswith("pre.tif")
    assert d["data_source"]["post"].endswith("post.tif")
    assert d["narrative"]


def test_change_raster_pre(client):
    r = client.get("/api/v1/demo/change-raster/pre")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")
    body = r.content
    assert body[:4] == b"\x89PNG"
    assert len(body) > 500


def test_change_raster_post(client):
    r = client.get("/api/v1/demo/change-raster/post")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")
    body = r.content
    assert body[:4] == b"\x89PNG"
    assert len(body) > 500


def test_change_raster_pre_vs_post_differ(client):
    pre = client.get("/api/v1/demo/change-raster/pre").content
    post = client.get("/api/v1/demo/change-raster/post").content
    assert pre != post
    assert pre[:4] == b"\x89PNG"
    assert post[:4] == b"\x89PNG"


def test_change_raster_unknown_acquisition_404(client):
    r = client.get("/api/v1/demo/change-raster/nope")
    assert r.status_code == 404
    assert r.json()["detail"] == "Unknown acquisition"


def test_render_acquisition_overlay_png_returns_valid_png(tmp_path_factory):
    pre, _ = make_bitemporal_pair(tmp_path_factory.mktemp("ovl") / "pair", size=160)
    with RemoteSensingRasterEngine(str(pre)) as engine:
        ndwi = engine.dataset_ndwi(green_index=2, nir_index=3)
        water = engine.water_mask(ndwi, threshold=0.1)
        png = BiTemporalChangeEngine.render_acquisition_overlay_png(engine)
    assert png[:4] == b"\x89PNG"
    img = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert img is not None
    assert img.shape[0] == 160
    assert img.shape[1] == 160
    assert img.shape[2] == 3
    blue = np.all(np.abs(img.astype(int) - [230, 120, 15]) < 30, axis=-1)
    assert int(blue.sum()) == int(water.sum())
