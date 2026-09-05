import pytest
import numpy as np
import rasterio
from app.change_engine import BiTemporalChangeEngine
from app.sample_data import make_bitemporal_pair
from app.raster_engine import RemoteSensingRasterEngine

def test_bitemporal_delta_ndwi():
    t1 = np.array([[0.2, 0.4], [0.1, 0.5]], dtype=np.float32)
    t2 = np.array([[0.6, 0.4], [0.7, 0.1]], dtype=np.float32)
    delta = BiTemporalChangeEngine.compute_bitemporal_delta_ndwi(t1, t2)
    assert delta.shape == (2, 2)
    assert np.isclose(delta[0, 0], 0.4)
    assert np.isclose(delta[0, 1], 0.0)

def test_detect_inundation_change():
    t1 = np.array([[0, 1], [0, 0]], dtype=np.uint8)
    t2 = np.array([[1, 1], [1, 0]], dtype=np.uint8)
    new_flood = BiTemporalChangeEngine.detect_inundation_change(t1, t2)
    assert new_flood.shape == (2, 2)
    assert new_flood[0, 0] == 1
    assert new_flood[0, 1] == 0  # Already water in T1
    assert new_flood[1, 0] == 1
    assert new_flood[1, 1] == 0

def test_extract_vector_polygons():
    mask = np.zeros((20, 20), dtype=np.uint8)
    mask[5:15, 5:15] = 1  # 100 pixels
    transform = rasterio.Affine(10.0, 0.0, 500000.0, 0.0, -10.0, 3000000.0)
    geojson = BiTemporalChangeEngine.extract_vector_polygons(mask, transform, min_area_pixels=5)
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) >= 1
    feature = geojson["features"][0]
    assert feature["geometry"]["type"] == "Polygon"
    assert len(feature["geometry"]["coordinates"][0]) >= 4  # Closed ring

def test_make_bitemporal_pair_grows_water(tmp_path_factory):
    pre, post = make_bitemporal_pair(tmp_path_factory.mktemp("pair") / "pre_post", size=128)
    assert pre.exists() and post.exists()
    with rasterio.open(str(pre)) as a, rasterio.open(str(post)) as b:
        assert a.crs == b.crs == rasterio.CRS.from_epsg(32645)
        assert a.transform == b.transform
        assert a.count == b.count == 4
        assert a.width == b.width == 128
    with RemoteSensingRasterEngine(str(pre)) as e1, RemoteSensingRasterEngine(str(post)) as e2:
        ndwi1 = e1.dataset_ndwi(green_index=2, nir_index=3)
        ndwi2 = e2.dataset_ndwi(green_index=2, nir_index=3)
        f1 = float((e1.water_mask(ndwi1, 0.1) > 0).mean())
        f2 = float((e2.water_mask(ndwi2, 0.1) > 0).mean())
    assert f2 > f1  # flood grows between T1 and T2

def test_align_ndwi_pair_real_grid(tmp_path_factory):
    pre0, post0 = make_bitemporal_pair(tmp_path_factory.mktemp("al") / "same", size=128)
    with RemoteSensingRasterEngine(str(pre0)) as e1, RemoteSensingRasterEngine(str(post0)) as e2:
        ndwi1 = e1.dataset_ndwi(green_index=2, nir_index=3)
        ndwi2 = e2.dataset_ndwi(green_index=2, nir_index=3)
        a1, a2 = BiTemporalChangeEngine.align_ndwi_pair(ndwi1, e1, ndwi2, e2)
    assert a1.shape == a2.shape == (128, 128)
    assert np.isfinite(a2).all()

def test_align_to_reference_grid_misaligned_pair(tmp_path_factory):
    # T2 offset east by 3 pixels -> grids differ; alignment must bring T2 onto T1's grid.
    pre, post = make_bitemporal_pair(
        tmp_path_factory.mktemp("misl") / "pre_post", size=128, shift_pixels=3.0
    )
    with rasterio.open(str(pre)) as a, rasterio.open(str(post)) as b:
        assert a.transform != b.transform
    with RemoteSensingRasterEngine(str(pre)) as e1, RemoteSensingRasterEngine(str(post)) as e2:
        ndwi1 = e1.dataset_ndwi(green_index=2, nir_index=3)
        ndwi2 = e2.dataset_ndwi(green_index=2, nir_index=3)
        t1, t2 = BiTemporalChangeEngine.align_ndwi_pair(ndwi1, e1, ndwi2, e2)
        # after alignment both live on T1's grid; new-flood ring is detected from real data
        water1 = e1.water_mask(t1, 0.1)
        water2 = (t2 > 0.1).astype(np.uint8)
        inundated = BiTemporalChangeEngine.detect_inundation_change(water1, water2)
    assert t1.shape == t2.shape == (128, 128)
    assert float(inundated.mean()) > 0.0
    with rasterio.open(str(pre)) as a:
        geojson = BiTemporalChangeEngine.extract_vector_polygons(
            inundated, a.transform, crs=a.crs, min_area_pixels=5
        )
    assert geojson["features"], "misaligned pair must still yield detected change polygons"
