import os
import re
import base64
from typing import Any, Dict, List, Optional

import numpy as np
import cv2
import rasterio
import httpx

from dotenv import load_dotenv

load_dotenv()

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemini-3.5-flash-lite"
FALLBACK_MODELS = ["google/gemini-3.7-flash", "meta/llama-3.2-90b-vision-instruct"]

_SYSTEM_PROMPT = (
    "You are SatQuery AI, a remote-sensing analyst supporting ISRO. Analyze the satellite imagery "
    "and the pipeline metrics supplied. Answer ONLY using what is visible in the image and the "
    "quantitative metrics provided. Never invent numbers, locations, dates, or features that are "
    "not present in these inputs. Be concise, technical, and factual. "
    "Respond in plain text only - do NOT use Markdown, bold asterisks, bullet lists, or headings."
)


class RemoteSensingVLMAdapter:
    """Remote Sensing Vision-Language Adapter backed by a real hosted VLM (OpenRouter)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPEN_ROUTER") or os.environ.get("OPENROUTER_API_KEY")
        self.model = model or os.environ.get("SATQUERY_VLM_MODEL") or DEFAULT_MODEL
        self.base_url = base_url or os.environ.get("OPENROUTER_BASE_URL") or DEFAULT_BASE_URL

    def render_raster_preview(self, raster_path: str, max_edge: int = 512) -> str:
        """Render the first 3 bands of a GeoTIFF to a PNG data URL (percentile-stretched)."""
        with rasterio.open(raster_path) as src:
            bands = src.read()
        if bands.ndim == 2:
            bands = bands[np.newaxis, ...]
        n_bands = bands.shape[0]
        if n_bands >= 3:
            rgb = bands[:3]
        elif n_bands == 2:
            rgb = np.stack([bands[0], bands[0], bands[1]])
        else:
            rgb = np.repeat(bands, 3, axis=0)

        h, w = rgb.shape[1], rgb.shape[2]
        scale = min(1.0, max_edge / max(h, w))
        out_h, out_w = max(1, round(h * scale)), max(1, round(w * scale))

        canvas = np.empty((out_h, out_w, 3), dtype=np.uint8)
        for i in range(3):
            band = rgb[i].astype(np.float32)
            lo, hi = np.percentile(band, (2.0, 98.0))
            scaled = np.clip((band - lo) / max(float(hi - lo), 1e-6), 0.0, 1.0)
            ch = (scaled * 255.0).astype(np.uint8)
            if (out_h, out_w) != (h, w):
                ch = cv2.resize(ch, (out_w, out_h), interpolation=cv2.INTER_AREA)
            canvas[..., i] = ch

        ok, buf = cv2.imencode(".png", canvas)
        if not ok:
            raise RuntimeError("VLM preview PNG encoding failed")
        return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii")

    def _build_messages(self, query: str, metrics: Dict[str, Any], raster_path: str) -> List[Dict[str, Any]]:
        image_url = self.render_raster_preview(raster_path)
        metrics_block = "\n".join(f"- {k}: {v}" for k, v in (metrics or {}).items())
        user_text = (
            f"User inquiry: {query}\n\n"
            f"Pipeline metrics computed from THIS raster:\n{metrics_block}\n\n"
            "Assess the scene: describe what the imagery and metrics indicate about the area, "
            "and answer the inquiry directly. Do not fabricate values."
        )
        return [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": user_text},
                ],
            },
        ]

    def _chat_completion(self, messages: List[Dict[str, Any]], max_tokens: int, timeout: float) -> str:
        if not self.api_key:
            raise RuntimeError("VLM unavailable: set OPEN_ROUTER (or OPENROUTER_API_KEY) to enable VLM narration")
        models = [self.model] + [m for m in FALLBACK_MODELS if m != self.model]
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        last_error: Optional[Exception] = None
        for model in models:
            try:
                resp = httpx.post(
                    url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": 0.0,
                    },
                    timeout=timeout,
                )
                resp.raise_for_status()
                payload = resp.json()
                content = payload["choices"][0]["message"].get("content")
                if content and content.strip():
                    return content.strip()
                last_error = RuntimeError(f"model {model} returned empty content")
            except Exception as e:  # fall through to next model
                last_error = e
        raise RuntimeError(f"VLM inference failed on all {len(models)} models: {last_error}")

    def generate_vlm_narrative(
        self,
        query: str,
        metrics: Dict[str, Any],
        raster_path: str,
        max_tokens: int = 300,
        timeout: float = 30.0,
    ) -> str:
        """Produce a grounded narrative from the real raster + metrics via a hosted VLM."""
        messages = self._build_messages(query, metrics, raster_path)
        raw = self._chat_completion(messages, max_tokens=max_tokens, timeout=timeout)
        return self._sanitize_narrative(raw)

    @staticmethod
    def _sanitize_narrative(text: str) -> str:
        """Strip Markdown residue and malformed decimal chaining from VLM output."""
        text = re.sub(r"\*\*+|\*|__+", "", text)
        text = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.M)
        text = re.sub(r"^\s*[-+•]\s+", "", text, flags=re.M)
        text = re.sub(
            r"(?<=\d)\.(\d+)\.(?=\d)",
            lambda m: f".{m.group(1)}",
            text,
        )
        return re.sub(r"\s+", " ", text).strip()