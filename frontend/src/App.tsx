import { useState, useEffect, useRef } from 'react';
import MapComponent from './components/MapComponent';
import SplitSlider from './components/SplitSlider';

interface ApiMetrics {
  pixel_count: number;
  area_sq_km: number;
  area_hectares: number;
}

interface ApiResult {
  status: string;
  intent: string;
  narrative: string;
  metrics: ApiMetrics | null;
  geojson: { type: string; features: unknown[] } | null;
  data_source: string | null;
  filename?: string;
}

interface BitemporalDelta {
  min: number;
  max: number;
}

interface BitemporalResult {
  narrative: string;
  metrics: {
    t1_water: ApiMetrics;
    t2_water: ApiMetrics;
    change: ApiMetrics;
    delta_ndwi: BitemporalDelta;
  };
}

const fmtArea = (n?: number) => (n ?? 0).toFixed(4);
const fmtPixels = (n?: number) => (n ?? 0).toLocaleString('en-US');

const cleanNarrative = (s?: string | null) =>
  (s ?? '')
    .replace(/\*\*+|\*/g, '')
    .replace(/\s+/g, ' ')
    .trim();

const GUIDE_STEPS = [
  {
    title: 'Welcome to SatQuery AI',
    body: 'ISRO Smart India Hackathon console. Every result you see here is computed on real 16-bit Sentinel-2 / Sentinel-1 GeoTIFF rasters — pixel counts, km² areas, and the polygons on the map are real, not mock data.',
  },
  {
    title: '1 · Inquire in plain language',
    body: 'Type a query like "detect water" or "process C-Band SAR" in the left panel and hit Run, or click one of the three preset prompts (Flood, SAR, Bi-Temporal). A demo query already ran for you.',
  },
  {
    title: '2 · The interactive map',
    body: 'Detected regions are drawn as real EPSG:4326 polygons over basemaps. Switch Voyager / Dark / Satellite at the bottom-left, zoom, or hit the fullscreen icon. The Active Layer chips update per intent.',
  },
  {
    title: '3 · Read the metrics',
    body: 'The Inspection Report shows Intent, a ground-truth narrative, pixel counts, area in km², and hectares. A hosted vision-language model explains what the raster shows.',
  },
  {
    title: '4 · Bi-Temporal Swipe tab',
    body: 'Open the Bi-Temporal tab to swipe-compare Pre (T1) vs Post (T2) flood imagery and see the newly inundated area the change engine detected.',
  },
];

const presetBtnStyle: React.CSSProperties = {
  textAlign: 'left',
  fontSize: '12px',
  padding: '8px 12px',
  borderRadius: '6px',
  border: '1px solid #1f2937',
  background: '#1f2937',
  cursor: 'pointer',
};

export default function App() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [activeTab, setActiveTab] = useState<'vqa' | 'bitemporal'>('vqa');
  const [activeLayer, setActiveLayer] = useState<'ndwi' | 'ndvi' | 'sar' | 'change'>('ndwi');
  const [result, setResult] = useState<ApiResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [bitemporal, setBitemporal] = useState<BitemporalResult | null>(null);
  const [rasterError, setRasterError] = useState<string | null>(null);
  const demoRan = useRef(false);
  const bitemporalRan = useRef(false);
  const [showGuide, setShowGuide] = useState<boolean>(() => {
    try {
      return localStorage.getItem('satquery_guide_seen') !== '1';
    } catch {
      return true;
    }
  });
  const [guideStep, setGuideStep] = useState(0);

  const closeGuide = () => {
    try {
      localStorage.setItem('satquery_guide_seen', '1');
    } catch {
      /* ignore */
    }
    setShowGuide(false);
  };

  useEffect(() => {
    if (bitemporalRan.current) return;
    bitemporalRan.current = true;
    fetch('/api/v1/demo/change-detect', {
      method: 'POST',
    })
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || res.statusText);
        setBitemporal(data);
        setRasterError(null);
      })
      .catch((err) => {
        setRasterError(err instanceof Error ? err.message : 'Backend unreachable');
      });
  }, []);

  useEffect(() => {
    if (demoRan.current) return;
    demoRan.current = true;
    fetch('/api/v1/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: 'detect water' }),
    })
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || res.statusText);
        setResult(data);
        setActiveLayer('ndwi');
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Backend unreachable');
      });
  }, []);

  const runQuery = async (text: string) => {
    if (!text) return;
    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/v1/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || res.statusText);
      setResult(data);
      if (data.intent === 'CROSS_MODAL_SAR_FUSION') setActiveLayer('sar');
      else if (data.intent === 'BITEMPORAL_CHANGE_DETECTION') setActiveLayer('change');
      else setActiveLayer('ndwi');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Query failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    runQuery(query);
  };

  const runPreset = (text: string) => {
    setQuery(text);
    runQuery(text);
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch('/api/v1/ingest', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || res.statusText);
      setResult(data);
      setActiveLayer('ndwi');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  return (
    <div className="app-shell" style={{ fontFamily: 'Inter, system-ui, -apple-system, sans-serif', background: '#0b0f19', color: '#f8fafc', minHeight: '100vh', padding: '24px' }}>
      {/* Top Navbar */}
      <header className="app-header" style={{
        maxWidth: '1300px',
        margin: '0 auto 24px auto',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: '#111827',
        padding: '16px 24px',
        borderRadius: '12px',
        border: '1px solid #1f2937',
        boxShadow: '0 4px 20px rgba(0,0,0,0.4)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ background: '#2563eb', width: '40px', height: '40px', borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '20px' }}>
            🛰️
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '20px', fontWeight: 700, letterSpacing: '-0.02em', color: '#ffffff' }}>
              SatQuery AI <span style={{ fontSize: '12px', background: '#1e3a8a', color: '#60a5fa', padding: '2px 8px', borderRadius: '12px', marginLeft: '8px' }}>SIH26167</span>
            </h1>
            <p style={{ margin: '2px 0 0 0', fontSize: '12px', color: '#94a3b8' }}>ISRO Multi-Modal Remote Sensing & SAR Vision-Language Console</p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button
            onClick={() => setShowGuide(true)}
            aria-label="Show how to use guide"
            title="How to use"
            style={{
              padding: '8px 14px',
              borderRadius: '8px',
              border: '1px solid #1f2937',
              background: '#030712',
              color: '#94a3b8',
              cursor: 'pointer',
              fontWeight: 700,
              fontSize: '13px',
            }}
          >
            ?
          </button>
          <div style={{ display: 'flex', gap: '8px', background: '#030712', padding: '4px', borderRadius: '8px', border: '1px solid #1f2937' }}>
          <button
            onClick={() => setActiveTab('vqa')}
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              border: 'none',
              background: activeTab === 'vqa' ? '#2563eb' : 'transparent',
              color: activeTab === 'vqa' ? '#ffffff' : '#94a3b8',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '13px',
              transition: 'all 0.2s'
            }}
          >
            VQA & SAR Analysis
          </button>
          <button
            onClick={() => setActiveTab('bitemporal')}
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              border: 'none',
              background: activeTab === 'bitemporal' ? '#2563eb' : 'transparent',
              color: activeTab === 'bitemporal' ? '#ffffff' : '#94a3b8',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '13px',
              transition: 'all 0.2s'
            }}
          >
            Bi-Temporal Swipe
          </button>
        </div>
        </div>
      </header>

      {/* Main Workspace */}
      <div style={{ maxWidth: '1300px', margin: '0 auto' }}>
        {activeTab === 'bitemporal' ? (
          <div style={{ background: '#111827', padding: '24px', borderRadius: '12px', border: '1px solid #1f2937' }}>
            <h2 style={{ marginTop: 0, fontSize: '18px', color: '#ffffff' }}>Bi-Temporal Change Swipe Engine</h2>
            <p style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '20px' }}>
              Compare Pre-Event ($T_1$) baseline multi-spectral image against Post-Event ($T_2$) flood image to isolate newly inundated pixels.
            </p>
            {rasterError && (
              <div style={{ background: '#7f1d1d', border: '1px solid #dc2626', padding: '8px 12px', borderRadius: '8px', fontSize: '12px', color: '#fca5a5', marginBottom: '16px' }}>
                <strong>Warning:</strong> {rasterError} — showing placeholder imagery.
              </div>
            )}
            {bitemporal && (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                  <div style={{ background: '#030712', padding: '14px 10px', borderRadius: '8px', border: '1px solid #1f2937', textAlign: 'center' }}>
                    <div style={{ fontSize: '11px', color: '#64748b' }}>T1 Water (km²)</div>
                    <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#60a5fa' }}>{fmtArea(bitemporal.metrics.t1_water.area_sq_km)}</div>
                  </div>
                  <div style={{ background: '#030712', padding: '14px 10px', borderRadius: '8px', border: '1px solid #1f2937', textAlign: 'center' }}>
                    <div style={{ fontSize: '11px', color: '#64748b' }}>T2 Water (km²)</div>
                    <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#60a5fa' }}>{fmtArea(bitemporal.metrics.t2_water.area_sq_km)}</div>
                  </div>
                  <div style={{ background: '#030712', padding: '14px 10px', borderRadius: '8px', border: '1px solid #1f2937', textAlign: 'center' }}>
                    <div style={{ fontSize: '11px', color: '#64748b' }}>Δ Newly Inundated (km²)</div>
                    <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#dc2626' }}>{fmtArea(bitemporal.metrics.change.area_sq_km)}</div>
                  </div>
                </div>
                <p style={{ fontSize: '13px', color: '#cbd5e1', lineHeight: 1.5, margin: '0 0 16px 0' }}>{cleanNarrative(bitemporal.narrative)}</p>
              </>
            )}
            <SplitSlider
              preImageUrl={rasterError ? undefined : '/api/v1/demo/change-raster/pre'}
              postImageUrl={rasterError ? undefined : '/api/v1/demo/change-raster/post'}
              preLabel="T1 (Pre-Event)"
              postLabel="T2 (Post-Event)"
            />
          </div>
        ) : (
          <div className="app-layout">
            {/* Left Control Drawer */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Error Banner */}
              {error && (
                <div style={{
                  background: '#7f1d1d',
                  border: '1px solid #dc2626',
                  padding: '10px 12px',
                  borderRadius: '8px',
                  fontSize: '13px',
                  color: '#fca5a5',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: '12px',
                }}>
                  <span><strong>Error:</strong> {error}</span>
                  <button
                    onClick={() => setError(null)}
                    aria-label="Dismiss error"
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: '#fca5a5',
                      cursor: 'pointer',
                      fontSize: '14px',
                      lineHeight: 1,
                      padding: '2px 6px',
                      borderRadius: '4px',
                    }}
                  >
                    ✕
                  </button>
                </div>
              )}

              {/* Query Card */}
              <div style={{ background: '#111827', padding: '20px', borderRadius: '12px', border: '1px solid #1f2937' }}>
                <h2 style={{ marginTop: 0, fontSize: '16px', fontWeight: 600, color: '#f8fafc', marginBottom: '14px' }}>
                  Natural Language Query
                </h2>
                <form onSubmit={handleSearch}>
                  <textarea
                    rows={4}
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="e.g. Detect surface water change after flood or process C-Band SAR radar data..."
                    style={{
                      width: '100%',
                      boxSizing: 'border-box',
                      padding: '12px',
                      borderRadius: '8px',
                      border: '1px solid #374151',
                      background: '#030712',
                      color: '#f8fafc',
                      fontSize: '13px',
                      resize: 'vertical',
                      outline: 'none',
                      marginBottom: '12px'
                    }}
                  />

                  <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '8px', fontWeight: 600 }}>
                    Quick Preset Prompts:
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '16px' }}>
                    <button
                      type="button"
                      onClick={() => runPreset("Detect flood inundation expansion across Brahmaputra basin")}
                      disabled={loading}
                      style={{ ...presetBtnStyle, color: '#93c5fd', opacity: loading ? 0.5 : 1, cursor: loading ? 'not-allowed' : 'pointer' }}
                    >
                      🌊 Flood & NDWI Water Detection
                    </button>
                    <button
                      type="button"
                      onClick={() => runPreset("Process Sentinel-1 C-Band SAR radar for cloud-penetrating water mask")}
                      disabled={loading}
                      style={{ ...presetBtnStyle, color: '#c084fc', opacity: loading ? 0.5 : 1, cursor: loading ? 'not-allowed' : 'pointer' }}
                    >
                      📡 Sentinel-1 All-Weather SAR Radar
                    </button>
                    <button
                      type="button"
                      onClick={() => runPreset("Calculate bi-temporal change difference matrix between T1 and T2")}
                      disabled={loading}
                      style={{ ...presetBtnStyle, color: '#fca5a5', opacity: loading ? 0.5 : 1, cursor: loading ? 'not-allowed' : 'pointer' }}
                    >
                      🔄 Bi-Temporal Change Matrix
                    </button>
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    style={{
                      width: '100%',
                      background: '#2563eb',
                      color: '#ffffff',
                      border: 'none',
                      padding: '12px',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      fontWeight: 600,
                      fontSize: '14px',
                      boxShadow: '0 4px 12px rgba(37, 99, 235, 0.3)'
                    }}
                  >
                    {loading ? 'Executing Agent & Raster Math…' : 'Run SatQuery AI Inference'}
                  </button>
                </form>

                {/* GeoTIFF Upload */}
                <div style={{ marginTop: '14px', borderTop: '1px solid #1f2937', paddingTop: '14px' }}>
                  <label style={{ fontSize: '12px', color: '#94a3b8', fontWeight: 600, display: 'block', marginBottom: '8px' }}>
                    Upload GeoTIFF
                  </label>
                  <label
                    style={{
                      display: 'block',
                      textAlign: 'center',
                      padding: '10px',
                      borderRadius: '8px',
                      border: '1px dashed #374151',
                      background: '#030712',
                      color: uploading ? '#64748b' : '#93c5fd',
                      cursor: uploading ? 'not-allowed' : 'pointer',
                      fontSize: '13px',
                      fontWeight: 500,
                    }}
                  >
                    {uploading ? 'Uploading & Processing...' : 'Browse .tif / .tiff / .gtif'}
                    <input
                      type="file"
                      accept=".tif,.tiff,.gtif"
                      onChange={handleUpload}
                      disabled={uploading}
                      style={{ display: 'none' }}
                    />
                  </label>
                </div>
              </div>

              {/* Operational Metrics Panel */}
              <div style={{ background: '#111827', padding: '20px', borderRadius: '12px', border: '1px solid #1f2937' }}>
                {result ? (
                  <>
                    <h3 style={{ marginTop: 0, fontSize: '15px', color: '#f8fafc', marginBottom: '12px' }}>
                      Operational Inspection Report
                      {result.filename && <span style={{ fontWeight: 400, fontSize: '11px', color: '#64748b', marginLeft: '8px' }}>({result.filename})</span>}
                    </h3>
                    <div style={{ background: '#1e3a8a', border: '1px solid #3b82f6', padding: '8px 12px', borderRadius: '6px', fontSize: '12px', color: '#93c5fd', marginBottom: '12px' }}>
                      <strong>Intent:</strong> {result.intent}
                    </div>
                    <p style={{ fontSize: '13px', color: '#cbd5e1', lineHeight: 1.5, margin: '0 0 16px 0' }}>{cleanNarrative(result.narrative)}</p>

                    {result.metrics && (
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
                        <div style={{ background: '#030712', padding: '10px 6px', borderRadius: '8px', border: '1px solid #1f2937', textAlign: 'center' }}>
                          <div style={{ fontSize: '11px', color: '#64748b' }}>Pixels</div>
                          <div style={{ fontSize: '15px', fontWeight: 'bold', color: '#f8fafc' }}>{fmtPixels(result.metrics.pixel_count)}</div>
                        </div>
                        <div style={{ background: '#030712', padding: '10px 6px', borderRadius: '8px', border: '1px solid #1f2937', textAlign: 'center' }}>
                          <div style={{ fontSize: '11px', color: '#64748b' }}>Area (km²)</div>
                          <div style={{ fontSize: '15px', fontWeight: 'bold', color: '#60a5fa' }}>{fmtArea(result.metrics.area_sq_km)}</div>
                        </div>
                        <div style={{ background: '#030712', padding: '10px 6px', borderRadius: '8px', border: '1px solid #1f2937', textAlign: 'center' }}>
                          <div style={{ fontSize: '11px', color: '#64748b' }}>Hectares</div>
                          <div style={{ fontSize: '15px', fontWeight: 'bold', color: '#f8fafc' }}>{result.metrics.area_hectares}</div>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div style={{ textAlign: 'center', padding: '24px 8px', color: '#64748b' }}>
                    <div style={{ fontSize: '28px', marginBottom: '8px' }}>🛰️</div>
                    <div style={{ fontSize: '13px', fontWeight: 600, color: '#94a3b8', marginBottom: '4px' }}>No analysis yet</div>
                    <div style={{ fontSize: '12px' }}>Run a query, use a preset, or upload a GeoTIFF to see real raster metrics here.</div>
                  </div>
                )}
              </div>
            </div>

            {/* Right Map Canvas & Layer Controls */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ background: '#111827', padding: '12px 16px', borderRadius: '12px', border: '1px solid #1f2937', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '13px', fontWeight: 600, color: '#cbd5e1' }}>Multi-Spectral Layer Selector:</span>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button
                    onClick={() => setActiveLayer('ndwi')}
                    style={{ padding: '6px 12px', borderRadius: '6px', border: 'none', background: activeLayer === 'ndwi' ? '#2563eb' : '#1f2937', color: '#ffffff', cursor: 'pointer', fontSize: '12px' }}
                  >
                    NDWI Water
                  </button>
                  <button
                    onClick={() => setActiveLayer('ndvi')}
                    style={{ padding: '6px 12px', borderRadius: '6px', border: 'none', background: activeLayer === 'ndvi' ? '#16a34a' : '#1f2937', color: '#ffffff', cursor: 'pointer', fontSize: '12px' }}
                  >
                    NDVI Vegetation
                  </button>
                  <button
                    onClick={() => setActiveLayer('sar')}
                    style={{ padding: '6px 12px', borderRadius: '6px', border: 'none', background: activeLayer === 'sar' ? '#9333ea' : '#1f2937', color: '#ffffff', cursor: 'pointer', fontSize: '12px' }}
                  >
                    Sentinel-1 SAR
                  </button>
                  <button
                    onClick={() => setActiveLayer('change')}
                    style={{ padding: '6px 12px', borderRadius: '6px', border: 'none', background: activeLayer === 'change' ? '#dc2626' : '#1f2937', color: '#ffffff', cursor: 'pointer', fontSize: '12px' }}
                  >
                    Inundation Change
                  </button>
                </div>
              </div>

              <MapComponent geojson={result?.geojson ?? null} activeLayer={activeLayer} />
            </div>
          </div>
        )}
      </div>

      {/* First-Visit Guide Overlay */}
      {showGuide && (
        <div
          role="dialog"
          aria-modal="true"
          data-testid="guide-overlay"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 1000,
            background: 'rgba(2, 6, 23, 0.86)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '24px',
          }}
        >
          <div
            style={{
              maxWidth: '560px',
              width: '100%',
              background: '#111827',
              border: '1px solid #334155',
              borderRadius: '16px',
              padding: '28px',
              boxShadow: '0 25px 60px rgba(0, 0, 0, 0.6)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
              <div style={{ fontSize: '28px' }}>🛰️</div>
              <button
                onClick={closeGuide}
                aria-label="Close guide"
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#94a3b8',
                  cursor: 'pointer',
                  fontSize: '18px',
                  lineHeight: 1,
                  padding: '4px 8px',
                }}
              >
                ✕
              </button>
            </div>
            <h2 style={{ margin: '0 0 8px 0', fontSize: '19px', color: '#f8fafc' }}>
              {GUIDE_STEPS[guideStep].title}
            </h2>
            <p style={{ margin: '0 0 20px 0', fontSize: '14px', color: '#cbd5e1', lineHeight: 1.6 }}>
              {GUIDE_STEPS[guideStep].body}
            </p>

            <div style={{ display: 'flex', gap: '6px', marginBottom: '20px' }}>
              {GUIDE_STEPS.map((_, i) => (
                <button
                  key={i}
                  onClick={() => setGuideStep(i)}
                  aria-label={`Go to step ${i + 1}`}
                  style={{
                    width: '28px',
                    height: '6px',
                    border: 'none',
                    borderRadius: '3px',
                    cursor: 'pointer',
                    background: i === guideStep ? '#2563eb' : '#334155',
                    padding: 0,
                  }}
                />
              ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <button
                onClick={closeGuide}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#94a3b8',
                  cursor: 'pointer',
                  fontSize: '13px',
                  padding: '8px 12px',
                }}
              >
                Skip tour
              </button>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={() => setGuideStep((s) => Math.max(0, s - 1))}
                  disabled={guideStep === 0}
                  style={{
                    padding: '8px 14px',
                    borderRadius: '8px',
                    border: '1px solid #334155',
                    background: 'transparent',
                    color: '#e2e8f0',
                    cursor: guideStep === 0 ? 'not-allowed' : 'pointer',
                    fontSize: '13px',
                    opacity: guideStep === 0 ? 0.4 : 1,
                  }}
                >
                  Back
                </button>
                {guideStep === GUIDE_STEPS.length - 1 ? (
                  <button
                    onClick={closeGuide}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '8px',
                      border: 'none',
                      background: '#2563eb',
                      color: '#ffffff',
                      cursor: 'pointer',
                      fontWeight: 600,
                      fontSize: '13px',
                    }}
                  >
                    Start exploring
                  </button>
                ) : (
                  <button
                    onClick={() => setGuideStep((s) => Math.min(GUIDE_STEPS.length - 1, s + 1))}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '8px',
                      border: 'none',
                      background: '#2563eb',
                      color: '#ffffff',
                      cursor: 'pointer',
                      fontWeight: 600,
                      fontSize: '13px',
                    }}
                  >
                    Next
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
