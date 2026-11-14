"""Playwright adapters for Chromium, Firefox and WebKit.

No stealth, no anti-detection, no CAPTCHA handling: the browser identifies itself normally and a blocked page is
reported as blocked.
"""
from __future__ import annotations
import time
from pathlib import Path

from .base import BrowserAdapter, Capture, CaptureRequest, FatalCaptureError, RecoverableError


_exe_cache: dict[str, tuple[float, str | None]] = {}


class PlaywrightAdapter(BrowserAdapter):
    renders_js = True
    supports_screenshots = True

    def __init__(self, engine: str):
        self.name = engine  # chromium | firefox | webkit

    def _executable(self) -> str | None:
        """Looked up once a minute: starting the Playwright driver takes about half a second."""
        hit = _exe_cache.get(self.name)
        if hit and time.time() - hit[0] < 60:
            return hit[1]
        path = None
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                path = getattr(p, self.name).executable_path
            path = path if path and Path(path).exists() else None
        except Exception:
            path = None
        _exe_cache[self.name] = (time.time(), path)
        return path

    def health(self) -> dict:
        exe = self._executable()
        return {"engine": self.name, "available": bool(exe), "renders_js": True, "screenshots": True,
                "detail": exe or f"Not installed. Run: playwright install {self.name}"}

    def capture(self, req: CaptureRequest) -> Capture:
        try:
            from playwright.sync_api import Error as PWError, TimeoutError as PWTimeout, sync_playwright
        except ImportError as e:
            raise FatalCaptureError("Playwright is not installed (pip install playwright).") from e
        t0 = time.time()
        console_errors: list[str] = []
        failed: list[str] = []
        shots: list[dict] = []
        try:
            with sync_playwright() as p:
                btype = getattr(p, self.name)
                ctx_args = dict(viewport={"width": req.viewport[0], "height": req.viewport[1]})
                if req.mobile and self.name != "firefox":  # Firefox does not support the isMobile option
                    ctx_args.update(is_mobile=True, has_touch=True)
                browser = None
                if req.profile_dir:
                    ctx = btype.launch_persistent_context(str(req.profile_dir), headless=req.headless, **ctx_args)
                else:
                    browser = btype.launch(headless=req.headless)
                    ctx = browser.new_context(**ctx_args)
                page = ctx.new_page()
                page.on("console", lambda m: console_errors.append(m.text[:500]) if m.type == "error" else None)
                page.on("pageerror", lambda e: console_errors.append(str(e)[:500]))
                page.on("requestfailed", lambda r: failed.append(r.url[:300]))
                resp = page.goto(req.url, timeout=req.timeout_ms, wait_until="domcontentloaded")
                try:
                    page.wait_for_load_state("networkidle", timeout=min(req.timeout_ms, 10000))
                except PWTimeout:
                    pass  # long-polling pages never go idle; the DOM is still usable
                status = resp.status if resp else None
                html, title, final = page.content(), page.title(), page.url
                if req.screenshot_dir:
                    req.screenshot_dir.mkdir(parents=True, exist_ok=True)
                    stamp = f"{int(time.time() * 1000)}-{self.name}-{req.viewport[0]}x{req.viewport[1]}"
                    vp = req.screenshot_dir / f"{stamp}-viewport.png"
                    page.screenshot(path=str(vp))
                    shots.append({"path": str(vp), "full_page": False, "width": req.viewport[0], "height": req.viewport[1]})
                    if req.full_page:
                        fp = req.screenshot_dir / f"{stamp}-full.png"
                        page.screenshot(path=str(fp), full_page=True)
                        shots.append({"path": str(fp), "full_page": True, "width": req.viewport[0], "height": 0})
                ctx.close()
                if browser:
                    browser.close()
        except PWTimeout as e:
            raise RecoverableError(f"Timed out after {req.timeout_ms} ms: {e}") from e
        except PWError as e:
            msg = str(e)
            if "Executable doesn't exist" in msg or "playwright install" in msg:
                raise FatalCaptureError(f"{self.name} is not installed. Run: playwright install {self.name}") from e
            if any(k in msg for k in ("net::ERR_", "NS_ERROR_", "Connection", "crashed", "closed")):
                raise RecoverableError(msg[:400]) from e
            raise FatalCaptureError(msg[:400]) from e
        if status is not None and (status >= 500 or status == 429):
            raise RecoverableError(f"HTTP {status} from server")
        return Capture(url=req.url, final_url=final, status=status, html=html, title=title, engine=self.name,
                       duration_ms=int((time.time() - t0) * 1000), console_errors=console_errors[:50],
                       failed_requests=failed[:50], screenshots=shots, rendered=True)
