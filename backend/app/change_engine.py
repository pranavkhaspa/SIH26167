import numpy as np
import cv2
import rasterio
from typing import Dict, List, Any, Tuple, Optional
from rasterio.errors import CRSError
from rasterio.warp import transform as rio_transform
from rasterio.warp import reproject, Resampling
from app.raster_engine import RemoteSensingRasterEngine

class BiTemporalChangeEngine:
    """Bi-Temporal Difference & Vector GeoJSON Extraction Engine."""

    @staticmethod
    def _xy_to_wgs84(crs, xs, ys):
        """Vectorized reprojection of projected (x,y) to EPSG:4326 lon/lat."""
        if crs is None:
            return xs, ys
        try:
            lons, lats = rio_transform(crs, "EPSG:4326", xs, ys)
            return lons, lats
        except CRSError as e:
            raise RuntimeError(f"Invalid source CRS for reprojection: {crs}") from e

    @staticmethod
    def extract_vector_polygons(
        binary_mask: np.ndarray,
        transform: rasterio.Affine,
        min_area_pixels: int = 5,
        crs: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Convert binary raster mask into EPSG:4326 GeoJSON FeatureCollection.

        ``transform`` is the raster affine; ``crs`` (optional) is the raster's own CRS.
        When provided, contour vertices are reprojected from that CRS into EPSG:4326
        so the returned polygons are true WGS84 lon/lat. When omitted (legacy callers),
        affine-derived projected coords are returned as-is.
        """
        contours, _ = cv2.findContours(binary_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        features = []

        for contour in contours:
            if cv2.contourArea(contour) < min_area_pixels:
                continue

            # Unpack (c,r) pixel pairs from contour points, order preserved
            pixel_pts = np.array([p[0] for p in contour], dtype=np.float64)  # (x, y) = (col, row)
            rows = pixel_pts[:, 1]
            cols = pixel_pts[:, 0]

            # Affine -> native CRS projected coordinates (a,b,c,d,e,f params)
            a, b, c = transform.a, transform.b, transform.c
            d, e, f = transform.d, transform.e, transform.f
            xs = a * cols + b * rows + c
            ys = d * cols + e * rows + f

            if crs is not None:
                xs, ys = BiTemporalChangeEngine._xy_to_wgs84(crs, xs, ys)

            coordinates = [[float(lon), float(lat)] for lon, lat in zip(xs, ys)]
            if len(coordinates) >= 3:
                coordinates.append(coordinates[0])  # Close linear ring
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [coordinates]
                    },
                    "properties": {
                        "area_pixels": int(cv2.contourArea(contour))
                    }
                }
                features.append(feature)

        return {
            "type": "FeatureCollection",
            "features": features
        }

    @staticmethod
    def align_and_resample(raster1: np.ndarray, raster2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Ensure equal array shapes between T1 and T2 rasters via interpolation."""
        if raster1.shape == raster2.shape:
            return raster1, raster2

        h1, w1 = raster1.shape[:2]
        resampled_r2 = cv2.resize(raster2, (w1, h1), interpolation=cv2.INTER_LINEAR)
        return raster1, resampled_r2

    @staticmethod
    def align_to_reference_grid(
        target: np.ndarray,
        target_transform: rasterio.Affine,
        target_crs,
        ref_transform: rasterio.Affine,
        ref_crs,
        ref_height: int,
        ref_width: int,
    ) -> np.ndarray:
        """Warp ``target`` onto the reference raster's grid (transform+CRS aware).

        Fast-path returns as-is when grids already match. Otherwise reprojects bilinearly
        so real T1/T2 acquisitions with differing bounds, resolution, or CRS are aligned.
        """
        if (
            target_transform == ref_transform
            and target_crs == ref_crs
            and target.shape == (ref_height, ref_width)
        ):
            return target

        dst = np.empty((ref_height, ref_width), dtype=np.float32)
        reproject(
            source=target,
            destination=dst,
            src_transform=target_transform,
            src_crs=target_crs,
            dst_transform=ref_transform,
            dst_crs=ref_crs,
            resampling=Resampling.bilinear,
        )
        return dst

    @staticmethod
    def align_ndwi_pair(
        ndwi_t1: np.ndarray,
        engine1: "RemoteSensingRasterEngine",
        ndwi_t2: np.ndarray,
        engine2: "RemoteSensingRasterEngine",
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Return both NDWI arrays on T1's grid (real geospatial alignment of T2 onto T1)."""
        t1 = np.asarray(ndwi_t1, dtype=np.float32)
        t2 = BiTemporalChangeEngine.align_to_reference_grid(
            np.asarray(ndwi_t2, dtype=np.float32),
            engine2.transform,
            engine2.crs,
            engine1.transform,
            engine1.crs,
            engine1.height,
            engine1.width,
        )
        return t1, t2

    @staticmethod
    def compute_bitemporal_delta_ndwi(ndwi_t1: np.ndarray, ndwi_t2: np.ndarray) -> np.ndarray:
        """Compute Delta NDWI matrix (NDWI_T2 - NDWI_T1)."""
        r1, r2 = BiTemporalChangeEngine.align_and_resample(ndwi_t1, ndwi_t2)
        return r2 - r1

    @staticmethod
    def detect_inundation_change(water_mask_t1: np.ndarray, water_mask_t2: np.ndarray) -> np.ndarray:
        """Isolate newly inundated pixels (Water_T2 AND NOT Water_T1)."""
        w1, w2 = BiTemporalChangeEngine.align_and_resample(water_mask_t1, water_mask_t2)
        new_flooded = (w2 > 0) & (w1 == 0)
        return new_flooded.astype(np.uint8)

    @staticmethod
    def render_acquisition_overlay_png(engine, threshold=0.1) -> bytes:
        if engine.count < 3:
            raise ValueError("Engine must have at least 3 bands for RGB rendering")

        # --- RGB base ---
        bands = [engine.dataset.read(i).astype(np.float64) for i in [1, 2, 3]]
        canvas = np.zeros((*bands[0].shape, 3), dtype=np.uint8)
        for ch, band in enumerate(bands):
            lo, hi = np.percentile(band, [2, 98])
            if hi - lo < 1e-8:
                canvas[:, :, ch] = 0
            else:
                canvas[:, :, ch] = np.clip((band - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)

        # --- Water overlay ---
        ndwi = engine.dataset_ndwi(green_index=2, nir_index=3)
        mask = engine.water_mask(ndwi, threshold=threshold).astype(bool)
        canvas[mask] = [230, 120, 15]

        # --- Encode ---
        ok, buf = cv2.imencode(".png", canvas)
        if not ok:
            raise RuntimeError("cv2.imencode failed")
        return bytes(buf)
