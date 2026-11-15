"""Playwright-backed adapters for Chromium, Firefox and WebKit.

One implementation parameterised by engine; each registers under its own
name so the manager, dashboard and scheduler stay engine-agnostic.

Permission policy (directive §5/§16):
* screenshots are only taken when the caller passes screenshots_allowed
* never submit forms, never click authenticated controls, never store
  credentials/cookies/tokens in results — only public observable state
* no stealth, no anti-detection: plain, honest browser with an
  identifiable user-agent suffix
"""
from __future__ import annotations

import hashlib
import logging
import os
import time

from .base import BrowserEngineAdapter, CaptureOptions, CaptureResult

log = logging.getLogger("rice.browser")

SUPPORTED_ENGINES = ("chromium", "firefox", "webkit")

# Fallback only; the declared identity is RICE_BROWSER_UA in settings.
UA_SUFFIX = "NigeriaLifeResearchBot/1.0 (+research-platform; authorised-research-only)"

WAIT_UNTIL_CHOICES = ("domcontentloaded", "load", "networkidle")


def _default_ua() -> str:
    """The declared, identifiable user agent — configurable per deployment
    via RICE_BROWSER_UA, always honest (never impersonates a real browser)."""
    try:
        from ...config import get_settings

        return get_settings().browser_ua or UA_SUFFIX
    except Exception:
        return UA_SUFFIX


def _norm_wait_until(wait_until: str) -> str:
    return wait_until if wait_until in WAIT_UNTIL_CHOICES else "domcontentloaded"


class PlaywrightAdapter(BrowserEngineAdapter):
    def __init__(self, engine: str) -> None:
        self.engine = engine

    async def health(self) -> dict:
        out = {"engine": self.engine, "installed": False, "version": "", "binary_path": "", "error": ""}
        pw = None
        try:
            from playwright.async_api import async_playwright

            pw = await async_playwright().start()
            launcher = getattr(pw, self.engine)
            browser = await launcher.launch(headless=True)
            try:
                out["version"] = str(getattr(browser, "version", lambda: "")()) or "unknown"
            except Exception:
                out["version"] = "unknown"
            await browser.close()
            out["installed"] = True
        except Exception as e:
            msg = str(e)
            first = msg.splitlines()[0][:300]
            out["error"] = first
            if "Executable doesn't exist" in msg or "browserType.launch" in msg:
                out["error"] = (f"Browser binaries for {self.engine} are not installed in this "
                                "environment. Run `playwright install " + self.engine + "` on the "
                                "host, then re-check health. Sessions will degrade to manual "
                                "evidence import until then.")
            return out
        finally:
            try:
                if pw is not None:
                    await pw.stop()
            except Exception:
                pass
        return out

    async def capture(self, options: CaptureOptions, user_data_dir: str = "",
                      headless: bool = True,
                      extra_viewports: list[dict] | None = None,
                      screenshot_dir: str = "",
                      screenshots_allowed: bool = True) -> CaptureResult:
        t0 = time.monotonic()
        result = CaptureResult(ok=False)
        pw = None
        context = None
        browser = None
        try:
            from playwright.async_api import async_playwright

            pw = await async_playwright().start()
            launcher = getattr(pw, self.engine)
            ua = options.user_agent or _default_ua()
            wait_until = _norm_wait_until(options.wait_until)
            common = {
                "headless": headless,
                "viewport": {"width": int(options.viewport.get("width", 1440)),
                             "height": int(options.viewport.get("height", 900))},
                "device_scale_factor": float(options.viewport.get("dpr", 1)),
                "user_agent": ua,
            }
            if user_data_dir:
                os.makedirs(user_data_dir, exist_ok=True)
                context = await launcher.launch_persistent_context(user_data_dir, **common)
            else:
                browser = await launcher.launch(headless=headless)
                context = await browser.new_context(**common)
            page = await context.new_page()

            navigations: list[str] = []
            console_errors: list[str] = []

            def _on_nav(frame):
                try:
                    if frame == page.main_frame and frame.url and frame.url != "about:blank":
                        if not navigations or navigations[-1] != frame.url:
                            navigations.append(frame.url)
                except Exception:
                    pass

            def _on_console(msg):
                if msg.type in ("error", "warning"):
                    console_errors.append(f"{msg.type}: {msg.text[:300]}")

            page.on("framenavigated", _on_nav)
            page.on("console", _on_console)

            response = await page.goto(options.url, timeout=options.timeout_ms,
                                       wait_until=wait_until)
            await page.wait_for_timeout(options.wait_ms)
            result.final_url = page.url
            result.status_code = response.status if response is not None else None
            result.html = await page.content()
            result.navigations = navigations[:50]
            result.console_errors = console_errors[:50]
            result.ok = True

            if screenshots_allowed and screenshot_dir:
                os.makedirs(screenshot_dir, exist_ok=True)
                safe = hashlib.sha1(options.url.encode()).hexdigest()[:12]
                vp_path = os.path.join(screenshot_dir, f"viewport-{safe}.png")
                fp_path = os.path.join(screenshot_dir, f"fullpage-{safe}.png")
                try:
                    await page.screenshot(path=vp_path, full_page=False)
                    result.screenshot_paths.append(vp_path)
                    result.screenshot_sizes[vp_path] = os.path.getsize(vp_path)
                except Exception as e:
                    result.console_errors.append(f"screenshot(viewport) failed: {str(e)[:160]}")
                if options.full_page_screenshot:
                    try:
                        await page.screenshot(path=fp_path, full_page=True)
                        result.screenshot_paths.append(fp_path)
                        result.screenshot_sizes[fp_path] = os.path.getsize(fp_path)
                    except Exception as e:
                        result.console_errors.append(f"screenshot(fullpage) failed: {str(e)[:160]}")
                for ev in (extra_viewports or [])[:6]:
                    name = str(ev.get("name") or "vp").replace(" ", "-")
                    try:
                        await page.set_viewport_size({"width": int(ev.get("width", 375)),
                                                      "height": int(ev.get("height", 812))})
                        await page.goto(options.url, timeout=options.timeout_ms,
                                        wait_until=wait_until)
                        await page.wait_for_timeout(min(options.wait_ms, 1500))
                        p = os.path.join(screenshot_dir, f"responsive-{name}-{safe}.png")
                        await page.screenshot(path=p, full_page=False)
                        result.screenshot_paths.append(p)
                        result.screenshot_sizes[p] = os.path.getsize(p)
                    except Exception as e:
                        result.console_errors.append(f"screenshot({name}) failed: {str(e)[:160]}")
            return result
        except Exception as e:
            msg = str(e)
            first = msg.splitlines()[0][:300]
            result.error = first
            low = msg.lower()
            if "executable doesn't exist" in low or "browsertype.launch" in low:
                result.error = f"Browser binaries for {self.engine} not installed. Run `playwright install {self.engine}`."
                result.recoverable = False
            elif any(k in low for k in ("timeout", "net::err", "dns", "tls", "resolve", "unreachable", "refused", "certificate", "name or service")):
                # network-level failure: record, do not hammer the target
                result.recoverable = False
            else:
                result.recoverable = True
            return result
        finally:
            try:
                if context is not None:
                    await context.close()
            except Exception:
                pass
            try:
                if browser is not None:
                    await browser.close()
            except Exception:
                pass
            try:
                if pw is not None:
                    await pw.stop()
            except Exception:
                pass
            result.duration_ms = int((time.monotonic() - t0) * 1000)

    async def inspect_page(self, url: str, screenshot_path: str = "",
                           timeout_ms: int = 30000,
                           wait_until: str = "domcontentloaded") -> dict:
        """Quick standalone probe of one public page. Never raises: always
        returns {"url", "status", "title", "screenshot_size", "error"} with
        the honest outcome (a failed target lands in "error", not an
        exception)."""
        out: dict = {"url": url, "status": None, "title": "",
                     "screenshot_size": 0, "error": ""}
        pw = None
        context = None
        browser = None
        try:
            from playwright.async_api import async_playwright

            pw = await async_playwright().start()
            launcher = getattr(pw, self.engine)
            browser = await launcher.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent=_default_ua(),
            )
            page = await context.new_page()
            response = await page.goto(url, timeout=timeout_ms,
                                       wait_until=_norm_wait_until(wait_until))
            out["status"] = response.status if response is not None else None
            out["title"] = (await page.title() or "")[:500]
            if screenshot_path:
                d = os.path.dirname(screenshot_path)
                if d:
                    os.makedirs(d, exist_ok=True)
                await page.screenshot(path=screenshot_path, full_page=False)
                out["screenshot_size"] = os.path.getsize(screenshot_path)
            await page.close()
        except Exception as e:
            out["error"] = str(e).splitlines()[0][:300]
        finally:
            for closer in (context, browser):
                try:
                    if closer is not None:
                        await closer.close()
                except Exception:
                    pass
            try:
                if pw is not None:
                    await pw.stop()
            except Exception:
                pass
        return out


ENGINE_REGISTRY: dict[str, type[BrowserEngineAdapter]] = {
    "chromium": PlaywrightAdapter,
    "firefox": PlaywrightAdapter,
    "webkit": PlaywrightAdapter,
}


def make_adapter(engine: str) -> BrowserEngineAdapter | None:
    if engine not in ENGINE_REGISTRY:
        return None
    return ENGINE_REGISTRY[engine](engine)


def supported_engines() -> list[str]:
    return list(SUPPORTED_ENGINES)
