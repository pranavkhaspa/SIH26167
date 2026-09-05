import { useEffect, useRef, useState, type CSSProperties } from 'react';
import {
  Map as MapLibreMap,
  LngLatBounds,
  NavigationControl,
  ScaleControl,
  type GeoJSONSource,
} from 'maplibre-gl';
import { setWorkerUrl } from 'maplibre-gl';
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import 'maplibre-gl/dist/maplibre-gl.css';

setWorkerUrl(maplibreWorkerUrl);

export type BasemapId = 'voyager' | 'dark' | 'satellite';

interface MapComponentProps {
  geojson: any;
  activeLayer: 'ndwi' | 'ndvi' | 'sar' | 'change';
}

const PALETTE: Record<MapComponentProps['activeLayer'], { fill: string; line: string }> = {
  ndwi: { fill: '#3b82f6', line: '#60a5fa' },
  ndvi: { fill: '#22c55e', line: '#4ade80' },
  sar: { fill: '#a855f7', line: '#c084fc' },
  change: { fill: '#ef4444', line: '#f87171' },
};

const CARTO_KEY = 'cb1_2xx6_1_513fdfc95d1125751297f712';

const BASEMAPS: Record<BasemapId, { label: string; tiles: string[]; attribution: string }> = {
  voyager: {
    label: 'Voyager',
    tiles: [`https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=${CARTO_KEY}`],
    attribution: '© OpenStreetMap contributors © CARTO',
  },
  dark: {
    label: 'Dark',
    tiles: [`https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png?key=${CARTO_KEY}`],
    attribution: '© OpenStreetMap contributors © CARTO',
  },
  satellite: {
    label: 'Satellite',
    tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
    attribution: '© Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community',
  },
};

const INDIA_BOUNDS: [[number, number], [number, number]] = [
  [68.0, 6.0],
  [97.5, 37.0],
];

const SOURCE_ID = 'carto-raster';
const OVERLAY_SOURCE_ID = 'overlay-source';
const FILL_ID = 'overlay-fill';
const LINE_ID = 'overlay-line';

function isEmptyGeojson(geojson: any): boolean {
  return !geojson || !geojson.features || geojson.features.length === 0;
}

export default function MapComponent({ geojson, activeLayer }: MapComponentProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const lastDataRef = useRef<string>('');
  const [basemap, setBasemap] = useState<BasemapId>('voyager');
  const [loaded, setLoaded] = useState(false);
  const [tileError, setTileError] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    const onFullscreenChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement));
      requestAnimationFrame(() => mapRef.current?.resize());
    };
    document.addEventListener('fullscreenchange', onFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', onFullscreenChange);
  }, []);

  const toggleFullscreen = () => {
    const el = wrapRef.current;
    if (!el) return;
    if (document.fullscreenElement) {
      void document.exitFullscreen();
    } else {
      void el.requestFullscreen();
    }
  };

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new MapLibreMap({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          [SOURCE_ID]: {
            type: 'raster',
            tiles: BASEMAPS.voyager.tiles,
            tileSize: 256,
            attribution: BASEMAPS.voyager.attribution,
          },
        },
        layers: [
          {
            id: SOURCE_ID,
            type: 'raster',
            source: SOURCE_ID,
            paint: { 'raster-opacity': 1 },
          },
        ],
      },
      center: [81.0, 22.0],
      zoom: 4,
    });

    map.once('load', () => setLoaded(true));
    map.on('error', () => setTileError(true));
    map.on('load', () => setTileError(false));
    map.addControl(new NavigationControl({ showCompass: false }), 'bottom-right');
    map.addControl(new ScaleControl({ maxWidth: 110, unit: 'metric' }), 'bottom-left');
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) return;
    const spec = BASEMAPS[basemap];
    const src = map.getSource(SOURCE_ID) as GeoJSONSource | undefined;
    if (src) {
      (src as unknown as { setTiles: (tiles: string[]) => void }).setTiles(spec.tiles);
    } else {
      map.addSource(SOURCE_ID, { type: 'raster', tiles: spec.tiles, tileSize: 256, attribution: spec.attribution });
    }
    setTileError(false);
  }, [basemap, loaded]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) return;

    const empty = isEmptyGeojson(geojson);
    const dataKey = empty ? '' : JSON.stringify(geojson);
    const dataChanged = dataKey !== lastDataRef.current;
    lastDataRef.current = dataKey;

    if (empty) {
      if (map.getLayer(FILL_ID)) map.removeLayer(FILL_ID);
      if (map.getLayer(LINE_ID)) map.removeLayer(LINE_ID);
      if (map.getSource(OVERLAY_SOURCE_ID)) map.removeSource(OVERLAY_SOURCE_ID);
      map.fitBounds(new LngLatBounds(INDIA_BOUNDS[0], INDIA_BOUNDS[1]), { padding: 20, duration: 0 });
      return;
    }

    const { fill, line } = PALETTE[activeLayer];

    if (map.getSource(OVERLAY_SOURCE_ID)) {
      (map.getSource(OVERLAY_SOURCE_ID) as GeoJSONSource).setData(geojson);
      map.setPaintProperty(FILL_ID, 'fill-color', fill);
      map.setPaintProperty(LINE_ID, 'line-color', line);
    } else {
      map.addSource(OVERLAY_SOURCE_ID, {
        type: 'geojson',
        data: geojson,
      });
      map.addLayer({
        id: FILL_ID,
        type: 'fill',
        source: OVERLAY_SOURCE_ID,
        paint: { 'fill-color': fill, 'fill-opacity': 0.35 },
      });
      map.addLayer({
        id: LINE_ID,
        type: 'line',
        source: OVERLAY_SOURCE_ID,
        paint: { 'line-color': line, 'line-width': 2 },
      });
    }

    map.setPaintProperty(FILL_ID, 'fill-color', fill);
    map.setPaintProperty(LINE_ID, 'line-color', line);

    if (dataChanged) {
      const bounds = new LngLatBounds();
      geojson.features.forEach((feature: any) => {
        const geom = feature.geometry;
        if (!geom || !geom.coordinates) return;
        if (geom.type === 'Polygon') {
          geom.coordinates[0].forEach((coord: number[]) => bounds.extend(coord as [number, number]));
        } else if (geom.type === 'MultiPolygon') {
          geom.coordinates.forEach((poly: number[][][]) =>
            poly[0].forEach((coord: number[]) => bounds.extend(coord as [number, number])),
          );
        }
      });
      if (!bounds.isEmpty()) {
        map.fitBounds(bounds, { padding: 40, duration: 600, maxZoom: 16 });
      }
    }
  }, [geojson, activeLayer, loaded]);

  const resetView = () => {
    mapRef.current?.fitBounds(new LngLatBounds(INDIA_BOUNDS[0], INDIA_BOUNDS[1]), { padding: 20, duration: 400 });
  };

  const legend = {
    ndwi: 'Water Body (> 0.1)',
    ndvi: 'Vegetation Index',
    sar: 'SAR Backscatter (≤ -18dB)',
    change: 'Newly Inundated Region',
  }[activeLayer];

  const chipStyle: CSSProperties = {
    position: 'absolute',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    background: 'rgba(15, 23, 42, 0.85)',
    backdropFilter: 'blur(8px)',
    padding: '6px 12px',
    borderRadius: '8px',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    fontSize: '11px',
    color: '#e2e8f0',
    pointerEvents: 'none',
  };

  const controlStyle: CSSProperties = {
    position: 'absolute',
    bottom: '20px',
    left: '12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    zIndex: 5,
  };

  return (
    <div
      ref={wrapRef}
      className="satquery-map"
      style={{
        width: '100%',
        height: '480px',
        background: 'linear-gradient(160deg, #0d1424, #0a0f1c)',
        borderRadius: '12px',
        position: 'relative',
        overflow: 'hidden',
        border: '1px solid #1e293b',
        boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)',
      }}
    >
      <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />

      {!loaded && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '12px',
            background: 'rgba(13, 20, 36, 0.7)',
            zIndex: 10,
          }}
        >
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '50%',
              border: '3px solid rgba(148, 163, 184, 0.25)',
              borderTopColor: '#3b82f6',
              animation: 'spinner 0.8s linear infinite',
            }}
          />
          <span style={{ fontSize: '12px', color: '#94a3b8' }}>Loading map tiles…</span>
        </div>
      )}
      <style>{`@keyframes spinner { to { transform: rotate(360deg); } }
.satquery-map:fullscreen {
  width: 100vw;
  height: 100vh;
  border-radius: 0;
  border: none;
}`}</style>

      {tileError && (
        <div
          style={{
            position: 'absolute',
            top: '16px',
            left: '50%',
            transform: 'translateX(-50%)',
            background: '#7f1d1d',
            border: '1px solid #dc2626',
            padding: '6px 12px',
            borderRadius: '8px',
            fontSize: '11px',
            color: '#fca5a5',
            pointerEvents: 'none',
            zIndex: 9,
          }}
        >
          ⚠ Basemap tiles unavailable — check network
        </div>
      )}

      <div style={{ ...chipStyle, top: '16px', left: '16px' }}>
        <span>🛰️ <strong>Sensor:</strong> Sentinel-2 / Sentinel-1 C-SAR</span>
      </div>

      <div style={{ ...chipStyle, top: '16px', right: '16px' }}>
        <span>📍 <strong>Active Layer:</strong> {activeLayer.toUpperCase()}</span>
      </div>

      <div
        style={{
          position: 'absolute',
          bottom: '16px',
          right: '16px',
          background: 'rgba(15, 23, 42, 0.85)',
          backdropFilter: 'blur(8px)',
          padding: '12px',
          borderRadius: '8px',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          fontSize: '11px',
          color: '#e2e8f0',
          minWidth: '160px',
          pointerEvents: 'none',
          zIndex: 6,
        }}
      >
        <div style={{ fontWeight: 'bold', marginBottom: '8px', borderBottom: '1px solid #334155', paddingBottom: '4px' }}>
          Layer Legend ({activeLayer.toUpperCase()})
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <span style={{ width: '12px', height: '12px', borderRadius: '2px', background: PALETTE[activeLayer].fill }} />
          <span>{legend}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ width: '12px', height: '12px', borderRadius: '2px', border: `1.5px solid ${PALETTE[activeLayer].line}`, background: 'transparent' }} />
          <span>Vector Polygon Ring</span>
        </div>
      </div>

      <div style={controlStyle}>
        <div
          style={{
            display: 'flex',
            gap: '4px',
            background: 'rgba(15, 23, 42, 0.9)',
            border: '1px solid rgba(255, 255, 255, 0.12)',
            borderRadius: '8px',
            padding: '4px',
            backdropFilter: 'blur(8px)',
            zIndex: 5,
          }}
        >
          {(Object.keys(BASEMAPS) as BasemapId[]).map((id) => (
            <button
              key={id}
              onClick={() => setBasemap(id)}
              aria-label={`${BASEMAPS[id].label} basemap`}
              title={BASEMAPS[id].label}
              style={{
                padding: '5px 10px',
                borderRadius: '6px',
                border: 'none',
                background: basemap === id ? '#2563eb' : 'transparent',
                color: basemap === id ? '#ffffff' : '#94a3b8',
                cursor: 'pointer',
                fontSize: '11px',
                fontWeight: 600,
                transition: 'all 0.15s',
              }}
            >
              {BASEMAPS[id].label}
            </button>
          ))}
        </div>
        <button
          onClick={toggleFullscreen}
          aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
          title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          style={{
            background: 'rgba(15, 23, 42, 0.9)',
            border: '1px solid rgba(255, 255, 255, 0.12)',
            borderRadius: '8px',
            color: '#e2e8f0',
            cursor: 'pointer',
            fontSize: '11px',
            fontWeight: 600,
            padding: '6px 10px',
            backdropFilter: 'blur(8px)',
            textAlign: 'left',
          }}
        >
          {isFullscreen ? '🗗 Exit' : '⛶ Fullscreen'}
        </button>
        <button
          onClick={resetView}
          aria-label="Reset view to India"
          style={{
            background: 'rgba(15, 23, 42, 0.9)',
            border: '1px solid rgba(255, 255, 255, 0.12)',
            borderRadius: '8px',
            color: '#e2e8f0',
            cursor: 'pointer',
            fontSize: '11px',
            fontWeight: 600,
            padding: '6px 10px',
            backdropFilter: 'blur(8px)',
            textAlign: 'left',
          }}
        >
          ⌂ India
        </button>
      </div>
    </div>
  );
}