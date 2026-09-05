import { useState } from 'react';

interface SplitSliderProps {
  preImageUrl?: string;
  postImageUrl?: string;
  preLabel?: string;
  postLabel?: string;
}

export default function SplitSlider({
  preImageUrl,
  postImageUrl,
  preLabel = "T1 (Pre-Event)",
  postLabel = "T2 (Post-Event)",
}: SplitSliderProps) {
  const [sliderPos, setSliderPos] = useState(50);
  const hasImages = Boolean(preImageUrl && postImageUrl);

  const badgeStyle: React.CSSProperties = {
    position: 'absolute',
    top: '12px',
    padding: '6px 10px',
    borderRadius: '6px',
    background: 'rgba(3, 7, 18, 0.75)',
    color: '#ffffff',
    fontSize: '12px',
    fontWeight: 600,
    zIndex: 5,
    pointerEvents: 'none',
  };

  return (
    <div style={{ position: 'relative', width: '100%', height: '240px', borderRadius: '8px', overflow: 'hidden', border: '1px solid #cbd5e1' }}>
      {hasImages ? (
        <>
          {/* T2 (Post-Event) Background Layer */}
          <img
            src={postImageUrl}
            alt={postLabel}
            draggable={false}
            style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', objectFit: 'cover' }}
          />
          {/* T1 (Pre-Event) Foreground Layer with clip-path */}
          <img
            src={preImageUrl}
            alt={preLabel}
            draggable={false}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              clipPath: `polygon(0 0, ${sliderPos}% 0, ${sliderPos}% 100%, 0 100%)`,
            }}
          />
          <div style={{ ...badgeStyle, right: '12px' }}>{postLabel}</div>
          <div style={{ ...badgeStyle, left: '12px' }}>{preLabel}</div>
        </>
      ) : (
        <>
          {/* T2 (Post-Event) Background Layer */}
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'linear-gradient(135deg, #1e3a8a, #0284c7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            padding: '20px',
            color: '#ffffff',
            fontWeight: 'bold'
          }}>
            {postLabel} (Inundation/Flood)
          </div>

          {/* T1 (Pre-Event) Foreground Layer with clip-path */}
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'linear-gradient(135deg, #065f46, #059669)',
            clipPath: `polygon(0 0, ${sliderPos}% 0, ${sliderPos}% 100%, 0 100%)`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-start',
            padding: '20px',
            color: '#ffffff',
            fontWeight: 'bold'
          }}>
            {preLabel} (Baseline)
          </div>
        </>
      )}

      {/* Divider Bar */}
      <div style={{
        position: 'absolute',
        top: 0,
        bottom: 0,
        left: `${sliderPos}%`,
        width: '4px',
        background: '#ffffff',
        boxShadow: '0 0 8px rgba(0,0,0,0.5)',
        cursor: 'ew-resize'
      }} />

      {/* Input Slider */}
      <input
        type="range"
        min="0"
        max="100"
        value={sliderPos}
        onChange={(e) => setSliderPos(Number(e.target.value))}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          opacity: 0,
          cursor: 'ew-resize'
        }}
      />
    </div>
  );
}
