"""Browser adapter contract, AI adapter, and (when installed) real browser engines."""
import json

import httpx
import pytest

from nlie import ai
from nlie.browser import CaptureRequest
from nlie.browser.registry import available_engines, best_engine, get_adapter


def test_registry_reports_every_engine_honestly(env):
    engines = {e["engine"]: e for e in available_engines()}
    assert set(engines) == {"http", "chromium", "firefox", "webkit"}
    assert engines["http"]["available"] and not engines["http"]["renders_js"]
    assert best_engine("no-such-engine") in engines
    assert best_engine() == next((n for n in ("chromium", "firefox", "webkit") if engines[n]["available"]), "http")


@pytest.mark.parametrize("engine", ["chromium", "firefox", "webkit"])
def test_real_browser_engine(engine, tmp_path):
    """Runs only where the engine binary is installed (playwright install <engine>)."""
    ad = get_adapter(engine)
    if not ad.health()["available"]:
        pytest.skip(f"{engine} binary not installed in this environment: {ad.health()['detail']}")
    page = tmp_path / "p.html"
    page.write_text("<html><title>T</title><body><h1 id=h>a</h1><script>document.getElementById('h').textContent='rendered';console.error('boom')</script></body></html>")
    cap = ad.capture(CaptureRequest(url=page.as_uri(), screenshot_dir=tmp_path / "shots", profile_dir=tmp_path / "profile"))
    assert cap.rendered and "rendered" in cap.html and any("boom" in e for e in cap.console_errors)
    assert cap.screenshots and (tmp_path / "profile").exists()


def test_ai_works_without_a_provider(env):
    p = ai.get_provider()
    assert p.name == "heuristic" and ai.status()["model_configured"] is False
    with pytest.raises(ai.AIUnavailable):
        p.complete_json("anything")


def test_openai_compatible_provider_routes_models_and_calls_tools():
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        assert request.headers["authorization"] == "Bearer k"
        if body.get("tools") and not any(m["role"] == "tool" for m in body["messages"]):
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "count_pages", "arguments": "{\"status\": \"analysed\"}"}}]}}]})
        if body.get("response_format"):
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "{\"category\": \"Economy\"}"}}]})
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "There are 3."}}]})

    p = ai.OpenAICompatibleProvider("http://local.test/v1", "k", {"simple": "small", "complex": "big"}, transport=httpx.MockTransport(handler))
    assert p.complete_json("classify", complexity="simple") == {"category": "Economy"} and seen[-1]["model"] == "small"
    p.complete("think hard", complexity="complex")
    assert seen[-1]["model"] == "big"
    calls = []
    out = p.run_tools("how many?", {"count_pages": lambda status: calls.append(status) or 3},
                      [{"type": "function", "function": {"name": "count_pages", "parameters": {"type": "object", "properties": {"status": {"type": "string"}}}}}])
    assert calls == ["analysed"] and out == "There are 3."
