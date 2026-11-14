"""Plain HTTP adapter: no JavaScript, no screenshots. Always available; the fallback when no browser engine is installed."""
from __future__ import annotations
import re
import time

import httpx

from .base import BrowserAdapter, Capture, CaptureRequest, FatalCaptureError, RecoverableError


class HttpAdapter(BrowserAdapter):
    name = "http"
    renders_js = False
    supports_screenshots = False

    def __init__(self, transport: httpx.BaseTransport | None = None):
        self._transport = transport

    def health(self) -> dict:
        return {"engine": self.name, "available": True, "renders_js": False, "screenshots": False,
                "detail": "Built-in HTTP fetcher. Sees server-rendered HTML only."}

    def capture(self, req: CaptureRequest) -> Capture:
        t0 = time.time()
        try:
            with httpx.Client(timeout=req.timeout_ms / 1000, follow_redirects=True, transport=self._transport,
                              headers={"User-Agent": req.user_agent or "NLIE"}) as c:
                r = c.get(req.url)
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as e:
            raise RecoverableError(f"{type(e).__name__}: {e}") from e
        except httpx.HTTPError as e:
            raise FatalCaptureError(f"{type(e).__name__}: {e}") from e
        if r.status_code >= 500 or r.status_code == 429:
            raise RecoverableError(f"HTTP {r.status_code} from server")
        ctype = r.headers.get("content-type", "")
        if "html" not in ctype and "text" not in ctype and "json" not in ctype:
            raise FatalCaptureError(f"Unsupported content type: {ctype or 'unknown'}")
        m = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.I | re.S)
        return Capture(url=req.url, final_url=str(r.url), status=r.status_code, html=r.text,
                       title=(m.group(1).strip() if m else ""), engine=self.name,
                       duration_ms=int((time.time() - t0) * 1000),
                       redirects=[str(h.url) for h in r.history], rendered=False)
