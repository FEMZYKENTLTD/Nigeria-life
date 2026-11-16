"""Browser engine fold-in: inspect_page (honest error dict, never raises),
wait_until option, screenshot sizes in capture results, declared UA from
config."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from conftest import start  # noqa: E402


def test_inspect_page_returns_honest_dict():
    async def t():
        from app.engine.browser.engines import make_adapter, _default_ua
        from app.engine.browser.base import CaptureOptions, CaptureResult
        from app.config import get_settings

        # declared UA comes from settings
        assert _default_ua() == get_settings().browser_ua

        # wait_until is a first-class option with a safe default
        o = CaptureOptions(url="https://x.example.com")
        assert o.wait_until == "domcontentloaded"
        o.wait_until = "networkidle"
        assert o.wait_until == "networkidle"

        # screenshot sizes container exists
        r = CaptureResult(ok=True)
        r.screenshot_sizes["/tmp/a.png"] = 123
        assert r.screenshot_sizes["/tmp/a.png"] == 123

        # inspect_page: never raises, always the honest 5-key dict —
        # with or without browser binaries installed in the environment
        for engine in ("chromium", "firefox", "webkit"):
            adapter = make_adapter(engine)
            assert adapter is not None
            out = await adapter.inspect_page("https://unreachable-host-xyz.invalid/")
            assert set(out.keys()) == {"url", "status", "title", "screenshot_size", "error"}
            assert out["url"] == "https://unreachable-host-xyz.invalid/"
            assert isinstance(out["screenshot_size"], int)
            # in this sandbox the target cannot be reached: the failure is
            # reported in the dict, not raised
            assert out["error"]  # honest: something went wrong and it is said
        return
    start(t)


def test_browsers_inspect_endpoint_shape():
    async def t():
        import httpx

        from app.main import create_app

        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/api/browsers/inspect",
                             json={"url": "https://unreachable-host-xyz.invalid/",
                                   "engine": "chromium"})
            # 500 = engine cannot run (no binaries); 200 = probed, honest
            # error in the dict. Both are acceptable honest outcomes.
            assert r.status_code in (200, 500), r.text
            if r.status_code == 200:
                body = r.json()
                assert set(body.keys()) >= {"url", "status", "title",
                                            "screenshot_size", "error"}
            # unknown engine → engine error dict, still 200 (honest)
            r = await c.post("/api/browsers/inspect",
                             json={"url": "https://example.invalid/",
                                   "engine": "edge"})
            assert r.status_code == 200
            assert "unknown engine" in r.json()["error"]
            # bad wait_until falls back, not rejected
            r = await c.post("/api/browsers/inspect",
                             json={"url": "https://example.invalid/",
                                   "wait_until": "bogus"})
            assert r.status_code in (200, 500)
    start(t)
