import base64
import os

import pytest

from app.sample_data import make_optical
from app.vlm_adapter import RemoteSensingVLMAdapter

_FAKE_KEY = "sk-test-not-real"


def _fixture_tif(tmp_path):
    return make_optical(tmp_path / "scene.tif", size=128)


def test_render_raster_preview_png_data_url(tmp_path):
    tif = _fixture_tif(tmp_path)
    url = RemoteSensingVLMAdapter(api_key=_FAKE_KEY).render_raster_preview(str(tif))
    assert url.startswith("data:image/png;base64,")
    raw = base64.b64decode(url.split(",", 1)[1])
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"


def test_sanitize_narrative_strips_markdown_and_fixes_floats():
    dirty = (
        "**Scene Assessment:** Water covers 0.37.56 hectares.\n"
        "### Pipeline Metrics:\n"
        "- Pixel Count: 3,756 pixels\n"
        "- Area: 0.3756 sq km\n"
        "*Inquiry Response:* Mask recovered **37.56 hectares**."
    )
    clean = RemoteSensingVLMAdapter._sanitize_narrative(dirty)
    assert "**" not in clean
    assert "###" not in clean
    assert clean.startswith("Scene Assessment: Water covers 0.3756 hectares.")
    assert "0.37.56" not in clean
    assert "0.3756" in clean


def test_generate_narrative_no_key(tmp_path, monkeypatch):
    tif = _fixture_tif(tmp_path)
    monkeypatch.delenv("OPEN_ROUTER", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    adapter = RemoteSensingVLMAdapter(api_key=None)
    with pytest.raises(RuntimeError, match="VLM unavailable"):
        adapter.generate_vlm_narrative("detect water", {"area_sq_km": 1.0}, str(tif))


def test_generate_narrative_messages_grounded(tmp_path):
    tif = _fixture_tif(tmp_path)
    adapter = RemoteSensingVLMAdapter(
        api_key=_FAKE_KEY, model="google/gemini-3.5-flash-lite"
    )
    messages = adapter._build_messages("detect water", {"area_sq_km": 1.234, "pixel_count": 123}, str(tif))
    assert messages[0]["role"] == "system"
    user_content = messages[1]["content"]
    assert user_content[0]["type"] == "image_url"
    assert user_content[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert "1.234" in user_content[1]["text"]
    assert "detect water" in user_content[1]["text"]


def test_generate_narrative_fallback_chain(tmp_path, monkeypatch):
    tif = _fixture_tif(tmp_path)
    adapter = RemoteSensingVLMAdapter(
        api_key=_FAKE_KEY, model="google/gemini-3.5-flash-lite"
    )
    calls = []

    class _FakeResp:
        def __init__(self, payload=None, exc=None, used=False):
            self._p, self._e = payload, exc

        def raise_for_status(self):
            if self._e:
                raise self._e

        def json(self):
            return self._p

    def fake_post(url, headers, json, timeout):
        model = json["model"]
        calls.append(model)
        if model == "google/gemini-3.5-flash-lite":
            return _FakeResp(payload={
                "choices": [{"message": {"content": "   First model narrative.  "}}]
            })
        raise AssertionError("primary must succeed")

    monkeypatch.setattr("app.vlm_adapter.httpx.post", fake_post)
    out = adapter.generate_vlm_narrative("detect water", {"area_sq_km": 1.0}, str(tif))
    assert out == "First model narrative."


def test_generate_narrative_falls_to_second_model(tmp_path, monkeypatch):
    tif = _fixture_tif(tmp_path)
    adapter = RemoteSensingVLMAdapter(
        api_key=_FAKE_KEY, model="google/gemini-3.5-flash-lite"
    )
    calls = []

    def fake_post(url, headers, json, timeout):
        model = json["model"]
        calls.append(model)
        if model == "google/gemini-3.5-flash-lite":
            return _FakeResp2({"choices": [{"message": {}}]})
        return _FakeResp2({"choices": [{"message": {"content": "Fallback narrative."}}]})

    monkeypatch.setattr("app.vlm_adapter.httpx.post", fake_post)
    out = adapter.generate_vlm_narrative("detect water", {"area_sq_km": 1.0}, str(tif))
    assert out == "Fallback narrative."
    assert calls[0] == "google/gemini-3.5-flash-lite"
    assert calls[1] == "google/gemini-3.7-flash"


def test_generate_narrative_all_fail_raises(tmp_path, monkeypatch):
    tif = _fixture_tif(tmp_path)
    adapter = RemoteSensingVLMAdapter(
        api_key=_FAKE_KEY, model="google/gemini-3.5-flash-lite"
    )

    def fake_post(url, headers, json, timeout):
        raise RuntimeError("network down")

    monkeypatch.setattr("app.vlm_adapter.httpx.post", fake_post)
    with pytest.raises(RuntimeError, match="VLM inference failed"):
        adapter.generate_vlm_narrative("detect water", {"area_sq_km": 1.0}, str(tif))


@pytest.mark.skipif(
    not (os.environ.get("OPEN_ROUTER") or os.environ.get("OPENROUTER_API_KEY")),
    reason="OPEN_ROUTER key not set in environment",
)
@pytest.mark.skipif(os.environ.get("SATQUERY_RUN_LIVE") != "1", reason="set SATQUERY_RUN_LIVE=1 for live VLM smoke")
def test_live_vlm_narrative(tmp_path):
    tif = _fixture_tif(tmp_path)
    adapter = RemoteSensingVLMAdapter()
    narrative = adapter.generate_vlm_narrative(
        "Is there a water body in this scene?",
        {"area_sq_km": 0.34, "pixel_count": 3394},
        str(tif),
    )
    assert narrative  # non-empty real VLM narrative
    print(f"\n[VLM-LIVE] {narrative[:200]}")


class _FakeResp2:
    def __init__(self, payload=None, exc=None):
        self._p, self._e = payload, exc

    def raise_for_status(self):
        if self._e:
            raise self._e

    def json(self):
        return self._p