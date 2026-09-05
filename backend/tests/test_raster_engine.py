import pytest
import numpy as np
import rasterio
from pathlib import Path
from app.raster_engine import RemoteSensingRasterEngine
from app.sample_data import make_optical, make_sar, make_cloudy_optical


@pytest.fixture(scope="module")
def optical_tif(tmp_path_factory):
    return make_optical(tmp_path_factory.mktemp("rasters") / "optical.tif", size=128)


@pytest.fixture(scope="module")
def sar_tif(tmp_path_factory):
    return make_sar(tmp_path_factory.mktemp("rasters") / "sar.tif", size=128)


def test_ingest_reads_real_geotiff(optical_tif):
    with RemoteSensingRasterEngine(str(optical_tif)) as engine:
        assert engine.count == 4
        assert engine.width == 128 and engine.height == 128
        assert engine.transform is not None
        assert engine.crs is not None
        assert engine.crs.to_epsg() == 32645  # UTM Zone 45N


def test_read_band_returns_real_data(optical_tif):
    with RemoteSensingRasterEngine(str(optical_tif)) as engine:
        green = engine.read_band(2)
        nir = engine.read_band(3)
        assert green.shape == (128, 128)
        assert green.dtype == np.float32
        # Values must be real (high dynamic range), i.e. not synthetic zeros
        assert green.max() > 1000
        assert nir.max() > 1000


def test_band_out_of_range_fails_fast(optical_tif):
    with RemoteSensingRasterEngine(str(optical_tif)) as engine:
        with pytest.raises(ValueError, match="out of range"):
            engine.read_band(9)


def test_ndwi_ndvi_real_bands(optical_tif):
    with RemoteSensingRasterEngine(str(optical_tif)) as engine:
        ndwi = engine.dataset_ndwi(green_index=2, nir_index=3)
        ndvi = engine.dataset_ndvi(red_index=1, nir_index=3)
        assert ndwi.shape == (128, 128)
        assert np.all(ndwi >= -1.0) and np.all(ndwi <= 1.0)
        assert np.all(ndvi >= -1.0) and np.all(ndvi <= 1.0)


def test_water_mask_detects_water_region(optical_tif):
    with RemoteSensingRasterEngine(str(optical_tif)) as engine:
        ndwi = engine.dataset_ndwi(green_index=2, nir_index=3)
        mask = engine.water_mask(ndwi, threshold=0.1)
        frac = mask.mean()
        assert frac > 0.10  # water body present (expected ~0.2-0.3 of scene)


def test_real_surface_area_uses_pixel_size(optical_tif):
    with RemoteSensingRasterEngine(str(optical_tif)) as engine:
        ndwi = engine.dataset_ndwi(green_index=2, nir_index=3)
        mask = engine.water_mask(ndwi, threshold=0.1)
        area = engine.real_surface_area(mask)
        assert area["pixel_size_m"] == pytest.approx(10.0)
        assert area["pixel_count"] == int(mask.sum())
        assert area["area_sq_km"] > 0


def test_pixel_to_lonlat_reprojects_utm_to_wgs84(optical_tif):
    with RemoteSensingRasterEngine(str(optical_tif)) as engine:
        lon, lat = engine.pixel_to_lonlat(10, 10)
        # EPSG:32645 → WGS84 near Assam, India
        assert 67.0 < lon < 98.0
        assert 5.0 < lat < 37.0
        # Reprojected value should be DIFFERENT from the raw UTM coords
        x, y = engine.pixel_to_crs(10, 10)
        assert abs(lon - x) > 1e-5


def test_pixel_to_polygon_valid_closed_ring(optical_tif):
    with RemoteSensingRasterEngine(str(optical_tif)) as engine:
        feat = engine.pixel_to_polygon(30, 40, 20, 10)
        ring = feat["geometry"]["coordinates"][0]
        assert len(ring) == 5
        assert ring[0] == ring[-1]
        assert all(len(pt) == 2 for pt in ring)


def test_sar_processing_real_band(sar_tif):
    with RemoteSensingRasterEngine(str(sar_tif)) as engine:
        amp = engine.read_band(1)
        sigma0_db = engine.process_sar_decibel(amp)
        mask = engine.extract_sar_water_mask(sigma0_db, threshold_db=-18.0)
        assert mask.shape == (128, 128)
        assert set(np.unique(mask)).issubset({0, 1})
        assert mask.mean() > 0.01  # low-backscatter water region present


def test_lee_filter_reduces_speckle(sar_tif):
    with RemoteSensingRasterEngine(str(sar_tif)) as engine:
        x = engine.read_band(1)
    rng = np.random.default_rng(0)
    noisy = x * (0.5 + rng.random(x.shape))
    filtered = RemoteSensingRasterEngine.sar_speckle_filter(noisy, kernel_size=5)
    assert filtered.shape == noisy.shape
    assert filtered.dtype == noisy.dtype
    assert filtered.std() < noisy.std()  # speckle reduced
    assert filtered.mean() == pytest.approx(noisy.mean(), rel=0.05)  # scale preserved


def test_lee_filter_preserves_scale(sar_tif):
    with RemoteSensingRasterEngine(str(sar_tif)) as engine:
        x = engine.read_band(1)
    filtered = RemoteSensingRasterEngine.sar_speckle_filter(x, kernel_size=5)
    assert filtered.max() > 1.0  # not collapsed to 0..1 uint8 normalization


def test_cloudy_optical_defeats_ndwi(tmp_path_factory):
    d = tmp_path_factory.mktemp("cloudy")
    bare = make_optical(d / "bare.tif", size=128)
    cloudy = make_cloudy_optical(d / "cloudy.tif", size=128, cloud_cover=0.75)
    with RemoteSensingRasterEngine(str(bare)) as engine:
        bare_frac = engine.water_mask(engine.dataset_ndwi(green_index=2, nir_index=3), threshold=0.1).mean()
    with RemoteSensingRasterEngine(str(cloudy)) as engine:
        assert engine.crs.to_epsg() == 32645
        assert engine.count == 4
        cloudy_frac = engine.water_mask(engine.dataset_ndwi(green_index=2, nir_index=3), threshold=0.1).mean()
    assert cloudy_frac < 0.10  # cloud defeats optical water detection
    assert bare_frac > 0.15  # bare-water contrast proves the demo is meaningful


def test_missing_file_fails_fast(tmp_path):
    with pytest.raises(FileNotFoundError):
        RemoteSensingRasterEngine(str(tmp_path / "does_not_exist.tif"))