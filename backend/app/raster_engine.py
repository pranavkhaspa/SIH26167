"""Real 16-bit GeoTIFF ingestion & remote-sensing maths (Task 01).

Core guarantee: NO synthetic placeholder arrays. Every method either reads a real
on-disk raster via ``rasterio`` or raises a clear, fail-fast error.

Class layout
------------
* Static helpers (band-array maths, legacy API used by agent_router/tests).
* Instance methods: open a real file, read real bands, compute indices from the
  dataset, compute physical area from the raster's real pixel resolution, and
  reproject pixel coordinates into genuine EPSG:4326 lon/lat regardless of the
  input CRS (UTM etc.).
"""
from __future__ import annotations

import numpy as np
import rasterio
from rasterio.transform import xy as transform_xy
from rasterio.warp import transform as rio_transform
from typing import Dict, Tuple, Any, List, Optional


WGS84 = "EPSG:4326"


class RemoteSensingRasterEngine:
    """Core engine: opens a real GeoTIFF, exposes CRS/affine, computes indices,
    and converts pixel coordinates to real EPSG:4326 (WGS84) geometry."""

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path
        self.dataset = None
        self.crs = None
        self.bounds = None
        self.transform = None
        self.width = 0
        self.height = 0
        self.count = 0
        self._dtype = None
        if file_path is not None:
            self.open(file_path)

    def open(self, file_path: str) -> "RemoteSensingRasterEngine":
        """Open a GeoTIFF on disk. Raises FileNotFoundError if missing."""
        if not file_path:
            raise ValueError("RemoteSensingRasterEngine.open: file_path is required")
        import os

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"GeoTIFF not found: {file_path}")
        try:
            ds = rasterio.open(file_path)
        except Exception as e:
            raise RuntimeError(f"Failed to open GeoTIFF {file_path}: {e}") from e
        self.dataset = ds
        self.file_path = file_path
        self.crs = ds.crs
        self.bounds = ds.bounds
        self.transform = ds.transform
        self.width = ds.width
        self.height = ds.height
        self.count = ds.count
        self._dtype = ds.dtypes[0] if ds.dtypes else ds.dtype
        return self

    def close(self) -> None:
        if self.dataset is not None:
            self.dataset.close()
            self.dataset = None

    def __enter__(self) -> "RemoteSensingRasterEngine":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # Reading real bands
    # ------------------------------------------------------------------ #
    def read_band(self, index: int) -> np.ndarray:
        """Read a real band index (1-based, rasterio convention) as float32."""
        if self.dataset is None:
            raise RuntimeError("Raster not opened. Call .open(path) first.")
        if index < 1 or index > self.count:
            raise ValueError(
                f"raster has {self.count} bands; band index {index} out of range [1,{self.count}]"
            )
        return self.dataset.read(index).astype(np.float32)

    def require_bands(self, *indexes: int) -> List[np.ndarray]:
        """Read several bands with a fail-fast message on the first bad index."""
        bands = []
        for idx in indexes:
            try:
                bands.append(self.read_band(idx))
            except (ValueError, RuntimeError) as e:
                raise ValueError(f"Missing/inaccessible spectral band {idx}: {e}") from e
        return bands

    # ------------------------------------------------------------------ #
    # Static band-array maths (legacy API — kept for agent_router & old tests)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _norm_index(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        a = a.astype(np.float32)
        b = b.astype(np.float32)
        denom = a + b
        denom[denom == 0] = 1e-5
        return np.clip((a - b) / denom, -1.0, 1.0)

    @staticmethod
    def compute_ndwi(green_band: np.ndarray, nir_band: np.ndarray) -> np.ndarray:
        """Compute NDWI = (Green - NIR) / (Green + NIR) from band arrays."""
        return RemoteSensingRasterEngine._norm_index(green_band, nir_band)

    @staticmethod
    def compute_ndvi(red_band: np.ndarray, nir_band: np.ndarray) -> np.ndarray:
        """Compute NDVI = (NIR - Red) / (NIR + Red) from band arrays."""
        return RemoteSensingRasterEngine._norm_index(nir_band, red_band)

    @staticmethod
    def compute_surface_area(binary_mask: np.ndarray, pixel_size_meters: float = 10.0) -> Dict[str, float]:
        """Physical area from an assumed constant pixel GSD (legacy signature)."""
        pixel_count = int(np.sum(binary_mask > 0))
        area_sq_m = pixel_count * (pixel_size_meters ** 2)
        return {
            "pixel_count": pixel_count,
            "area_sq_km": round(area_sq_m / 1e6, 4),
            "area_hectares": round(area_sq_m / 10000.0, 2),
        }

    @staticmethod
    def pixel_to_geo(transform: rasterio.Affine, row: int, col: int) -> Tuple[float, float]:
        """Legacy: pixel -> native-CRS coordinates via affine only (NOT reprojected)."""
        lon, lat = transform_xy(transform, row, col)
        return float(lon), float(lat)

    @staticmethod
    def process_sar_decibel(sar_dn: np.ndarray) -> np.ndarray:
        """Convert SAR digital numbers to radiometric sigma-naught (dB)."""
        dn_clean = np.maximum(sar_dn.astype(np.float32), 1e-5)
        return np.clip(10.0 * np.log10(np.square(dn_clean)), -40.0, 5.0)

    @staticmethod
    def sar_speckle_filter(sar_array: np.ndarray, kernel_size: int = 5) -> np.ndarray:
        """Statistical Lee speckle filter: reduces variance while preserving edges and scale."""
        import cv2

        x = sar_array.astype(np.float64)
        k = kernel_size

        m = cv2.boxFilter(x, cv2.CV_64F, (k, k))
        m2 = cv2.boxFilter(x * x, cv2.CV_64F, (k, k))
        var = np.maximum(m2 - m * m, 0.0)

        v_noise = float(var.mean())
        weight = np.zeros_like(var, dtype=np.float64)
        np.divide(v_noise, var, out=weight, where=var > 0)
        weight = np.clip(weight, 0.0, 1.0)

        out = m + weight * (x - m)
        return out.astype(sar_array.dtype)

    @staticmethod
    def extract_sar_water_mask(sigma0_db: np.ndarray, threshold_db: float = -18.0) -> np.ndarray:
        return (sigma0_db <= threshold_db).astype(np.uint8)

    # ------------------------------------------------------------------ #
    # Real dataset-derived indices (instance API)
    # ------------------------------------------------------------------ #
    def dataset_ndwi(self, green_index: int = 2, nir_index: int = 3) -> np.ndarray:
        """NDWI from REAL bands of the opened raster (Sentinel-2 style order)."""
        green, nir = self.require_bands(green_index, nir_index)
        return self._norm_index(green, nir)

    def dataset_ndvi(self, red_index: int = 1, nir_index: int = 3) -> np.ndarray:
        """NDVI from REAL bands of the opened raster."""
        red, nir = self.require_bands(red_index, nir_index)
        return self._norm_index(nir, red)

    def water_mask(self, ndwi: np.ndarray, threshold: float = 0.1) -> np.ndarray:
        return (ndwi > threshold).astype(np.uint8)

    def vegetation_mask(self, ndvi: np.ndarray, threshold: float = 0.35) -> np.ndarray:
        return (ndvi > threshold).astype(np.uint8)

    def real_surface_area(self, binary_mask: np.ndarray) -> Dict[str, float]:
        """Physical area using the raster's REAL pixel resolution."""
        if self.transform is None:
            raise RuntimeError("Raster not opened. Call .open(path) first.")
        x_res, y_res = self.transform.a, -self.transform.e
        pixel_area = x_res * y_res
        pixel_count = int(np.sum(binary_mask > 0))
        area_sq_m = pixel_count * pixel_area
        return {
            "pixel_count": pixel_count,
            "area_sq_km": round(area_sq_m / 1e6, 4),
            "area_hectares": round(area_sq_m / 10000.0, 2),
            "pixel_size_m": round(float(x_res), 4),
        }

    # ------------------------------------------------------------------ #
    # Real geo-positioning: pixel -> EPSG:4326 lon/lat (handles UTM etc.)
    # ------------------------------------------------------------------ #
    def pixel_to_crs(self, row: int, col: int) -> Tuple[float, float]:
        """Pixel (row,col) -> coordinates in the raster's native CRS via affine."""
        if self.transform is None:
            raise RuntimeError("Raster not opened. Call .open(path) first.")
        return tuple(self.transform @ (col, row))

    def pixel_to_lonlat(self, row: int, col: int) -> Tuple[float, float]:
        """Pixel (row,col) -> (lon, lat) in EPSG:4326, reprojecting from self.crs."""
        if self.crs is None:
            raise RuntimeError("Raster not opened. Call .open(path) first.")
        x, y = self.pixel_to_crs(row, col)
        try:
            lons, lats = rio_transform(self.crs, WGS84, [x], [y])
            return float(lons[0]), float(lats[0])
        except Exception as e:
            raise RuntimeError(f"Reprojection to {WGS84} failed for point ({x},{y}): {e}") from e

    def pixel_to_polygon(self, px: int, py: int, w: int, h: int) -> Dict[str, Any]:
        """Pixel box (py,px,h,w) -> closed EPSG:4326 Polygon GeoJSON Feature."""
        corners = [(px, py), (px + w, py), (px + w, py + h), (px, py + h)]
        pts = [self.pixel_to_lonlat(cy, cx) for cx, cy in corners]
        ring = [list(p) for p in pts]
        ring.append(ring[0])
        return {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"bbox_pixels": [px, py, w, h]},
        }