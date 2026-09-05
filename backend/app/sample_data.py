"""Synthetic-but-REAL sample GeoTIFF generator (Task 03).

Writes actual 16-bit multi-band GeoTIFFs to disk with a proper CRS + affine so the
engine, tests, and demo all run on real rasterio-parsed files (never fake arrays).

Three presets:
- optical: 4-band Sentinel-2-like scene (R,G,NIR + SWIR) with a water body.
- cloudy_optical: same scene but with an optically-thick cloud deck over the water (monsoon).
- sar: 1-band Sentinel-1-like amplitude scene with low-backscatter water region.
"""
from __future__ import annotations

import numpy as np
import rasterio
from rasterio.transform import from_origin
from pathlib import Path
from typing import Optional


def _write(tif_path: Path, bands: list[np.ndarray], crs_epsg: int, x0: float, y0: float, res: float) -> Path:
    height, width = bands[0].shape
    transform = from_origin(x0, y0, res, res)
    count = len(bands)
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": count,
        "dtype": "uint16",
        "crs": f"EPSG:{crs_epsg}",
        "transform": transform,
        "compress": "lzw",
        "nodata": 0,
    }
    tif_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(str(tif_path), "w", **profile) as dst:
        for i, band in enumerate(bands, start=1):
            dst.write(np.clip(np.round(band), 0, 65535).astype(np.uint16), i)
    return tif_path


def _optical_scene(size: int, seed: int, rx: float, ry: float) -> list[np.ndarray]:
    """Build the 4-band optical scene for a water ellipse of given radii (as fraction of size)."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float64)
    cx, cy = size * 0.5, size * 0.45
    water = ((xx - cx) / (rx * size)) ** 2 + ((yy - cy) / (ry * size)) ** 2 <= 1.0
    veg = ((xx - cx) / (rx * size * 1.6)) ** 2 + ((yy - cy) / (ry * size * 1.6)) ** 2 <= 1.0
    veg &= ~water

    rng = np.random.default_rng(seed)
    base = rng.normal(1800, 120, size=(size, size))
    red = np.where(water, 400, np.where(veg, 900, base)).astype(np.float64)
    green = np.where(water, 650, np.where(veg, 1600, base + 200)).astype(np.float64)
    nir = np.where(water, 300, np.where(veg, 4200, base + 300)).astype(np.float64)
    swir = np.where(water, 700, np.where(veg, 1500, base + 500)).astype(np.float64)

    red += rng.normal(0, 25, size=(size, size))
    green += rng.normal(0, 25, size=(size, size))
    nir += rng.normal(0, 25, size=(size, size))
    swir += rng.normal(0, 25, size=(size, size))
    return [red, green, nir, swir]


def make_optical(
    out_path: str | Path,
    size: int = 256,
    crs_epsg: int = 32645,  # UTM Zone 45N (Assam/large part of NE India)
    x0: float = 500000.0,
    y0: float = 3000000.0,
    res: float = 10.0,
    water_frac: float = 0.22,
) -> Path:
    """Generate a 4-band optical scene with a well-defined dark water region."""
    bands = _optical_scene(size, seed=42, rx=0.30, ry=0.22)
    return _write(Path(out_path), bands, crs_epsg, x0, y0, res)


def make_bitemporal_pair(
    out_dir: str | Path,
    size: int = 256,
    crs_epsg: int = 32645,
    x0: float = 500000.0,
    y0: float = 3000000.0,
    res: float = 10.0,
    shift_pixels: float = 0.0,
) -> tuple[Path, Path]:
    """Generate a synthetic-but-REAL aligned T1/T2 optical pair (flood grows between acquisitions).

    Writes ``pre.tif`` (smaller water) and ``post.tif`` (larger water) into ``out_dir`` with an
    identical CRS + affine grid. Pass ``shift_pixels > 0`` to offset T2's origin by that many pixels
    (upsampled transform, not resampled) so callers can exercise real geospatial alignment.
    """
    pre_bands = _optical_scene(size, seed=42, rx=0.26, ry=0.20)
    post_bands = _optical_scene(size, seed=43, rx=0.34, ry=0.28)

    out_dir = Path(out_dir)
    pre = _write(out_dir / "pre.tif", pre_bands, crs_epsg, x0, y0, res)
    post_x0 = x0 + shift_pixels * res
    post = _write(out_dir / "post.tif", post_bands, crs_epsg, post_x0, y0, res)
    return pre, post


def make_sar(
    out_path: str | Path,
    size: int = 256,
    crs_epsg: int = 32645,
    x0: float = 500000.0,
    y0: float = 3000000.0,
    res: float = 10.0,
    water_frac: float = 0.22,
) -> Path:
    """Generate a 1-band SAR amplitude scene; water = very low backscatter (specular)."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float64)
    cx, cy, rx, ry = size * 0.5, size * 0.5, size * 0.28, size * 0.26
    water = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0

    rng = np.random.default_rng(7)
    amp = rng.gamma(shape=2.0, scale=8.0, size=(size, size)).astype(np.float64)
    amp[water] = rng.gamma(shape=0.4, scale=1.0, size=int(np.sum(water))).astype(np.float64)
    # Water: specular (very low) backscatter so sigma0 dB < -18 for reliable detection
    amp[water] *= 0.06
    amp[amp < 0.001] = 0.001
    return _write(Path(out_path), [amp], crs_epsg, x0, y0, res)


def make_cloudy_optical(
    out_path: str | Path,
    size: int = 256,
    crs_epsg: int = 32645,
    x0: float = 500000.0,
    y0: float = 3000000.0,
    res: float = 10.0,
    water_frac: float = 0.22,
    cloud_cover: float = 0.75,
) -> Path:
    """Generate a 4-band optical scene with a thick cloud deck masking ~75% of the water body."""
    import cv2

    yy, xx = np.mgrid[0:size, 0:size].astype(np.float64)
    cx, cy, rx, ry = size * 0.5, size * 0.45, size * 0.30, size * 0.22
    water = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0
    veg = ((xx - cx) / (rx * 1.6)) ** 2 + ((yy - cy) / (ry * 1.6)) ** 2 <= 1.0
    veg &= ~water

    rng = np.random.default_rng(42)
    base = rng.normal(1800, 120, size=(size, size))
    red = np.where(water, 400, np.where(veg, 900, base)).astype(np.float64)
    green = np.where(water, 650, np.where(veg, 1600, base + 200)).astype(np.float64)
    nir = np.where(water, 300, np.where(veg, 4200, base + 300)).astype(np.float64)
    swir = np.where(water, 700, np.where(veg, 1500, base + 500)).astype(np.float64)

    # Optically-thick cloud deck seeded over a random subset of the water ellipse
    cloud_seed = rng.random((size, size)) < cloud_cover
    cloud_mask = cloud_seed & water
    cloud_f = cv2.GaussianBlur(cloud_mask.astype(np.float32), (15, 15), 0)
    cloud = cloud_f >= 0.15  # soft edges, natural-looking deck

    bright = rng.normal(7500, 700, size=(size, size)).astype(np.float64)
    bright += rng.normal(0, 60, size=(size, size))
    for band in (red, green, nir, swir):
        band[cloud] = bright[cloud]

    red += rng.normal(0, 25, size=(size, size))
    green += rng.normal(0, 25, size=(size, size))
    nir += rng.normal(0, 25, size=(size, size))
    swir += rng.normal(0, 25, size=(size, size))

    return _write(Path(out_path), [red, green, nir, swir], crs_epsg, x0, y0, res)


if __name__ == "__main__":
    outdir = Path(__file__).resolve().parent.parent / "data" / "samples"
    print(make_optical(outdir / "sample_optical.tif"))
    print(make_sar(outdir / "sample_sar.tif"))