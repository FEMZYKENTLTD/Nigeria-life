"""Smart page understanding.

Turns raw HTML (captured by any browser engine, a page reader, or manually
imported) into a structured page record: title, purpose heuristic, content
category, regions, navigation, forms & controls, interactive components,
sections, links, empty/loading/error states and repeated components.

Pure Python (stdlib html.parser) — works with zero external services, which
keeps the platform functional when no AI provider is available. AI layers may
*enrich* the record later but are never required for it.
"""
from __future__ import annotations

import html as _html
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

MAX_BODY_TEXT = 20000

REGION_TAGS = {
    "header": "header", "nav": "navigation", "footer": "footer",
    "aside": "sidebar", "main": "main", "article": "article", "section": "section",
}
FORM_CONTROLS = {"input", "select", "textarea", "button"}
INTERACTIVE_TAGS = {"a", "button", "input", "select", "textarea", "summary", "dialog"}
SKIP_TEXT_TAGS = {"script", "style", "noscript", "template", "iframe"}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

ERROR_PATTERNS = re.compile(
    r"\b(error|not found|page not found|404|500|unavailable|something went wrong|couldn'?t load|offline)\b",
    re.IGNORECASE,
)
EMPTY_HINTS = re.compile(r"\b(no results?|nothing here|empty state|add (a )?something)\b", re.IGNORECASE)
LOADING_HINTS = re.compile(r"\b(loading|please wait|spinner|still loading|fetching)\b", re.IGNORECASE)


class _PageParser(HTMLParser):
    def __init__(self, base_url: str = "") -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title = ""
        self._in_title = False
        self.meta_description = ""
        self._in_meta = False
        self.regions: dict[str, list[str]] = {}
        self._region_stack: list[str] = []
        self.nav_links: list[dict] = []
        self.links: list[dict] = []
        self.forms: list[dict] = []
        self._form_stack: list[dict] = []
        self.controls: list[dict] = []
        self.interactive: list[dict] = []
        self.sections: list[dict] = []
        self.images: list[dict] = []
        self._section_depth = 0  # inside <section> nesting
        self.text_parts: list[str] = []
        self._skip_depth = 0
        self.class_counts: dict[tuple[str, str], int] = {}
        self.element_counts: dict[str, int] = {}
        self.buttons_text: list[str] = []
        self._current_heading: str | None = None
        self._button_text: list[str] = []
        self._in_button = False

    # -- helpers -------------------------------------------------------------
    def _emit_text(self, data: str) -> None:
        if self._skip_depth:
            return
        t = _html.unescape(data).strip()
        if not t:
            return
        self.text_parts.append(t)
        if self._in_button:
            self._button_text.append(t)
        if self._region_stack:
            lst = self.regions.setdefault(self._region_stack[-1], [])
            if t not in lst[-4:]:
                lst.append(t[:120])

    # -- HTMLParser events ----------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        self.element_counts[tag] = self.element_counts.get(tag, 0) + 1
        if tag in SKIP_TEXT_TAGS:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
            return
        if tag in REGION_TAGS and not self._form_stack:
            name = REGION_TAGS[tag]
            cls = a.get("class") or ""
            key = f"{name}:{cls.split()[0]}" if cls else name
            self._region_stack.append(key)
            self.regions.setdefault(key, [])
        if tag == "section":
            self._section_depth += 1
        if tag == "form":
            self._form_stack.append({"action": a.get("action", ""), "method": (a.get("method") or "get").lower(), "fields": []})
        if tag in FORM_CONTROLS:
            field = {
                "tag": tag,
                "type": a.get("type") or tag,
                "name": a.get("name", ""),
                "id": a.get("id", ""),
                "placeholder": a.get("placeholder", ""),
                "required": a.get("required") is not None or a.get("aria-required") == "true",
                "value": (a.get("value") or "")[:80],
            }
            if tag == "input" and field["type"] in ("hidden",):
                return
            self.controls.append(field)
            if self._form_stack:
                self._form_stack[-1]["fields"].append(field)
        if tag in INTERACTIVE_TAGS:
            label_bits = []
            if tag == "a":
                label_bits.append(a.get("aria-label", ""))
            elif tag in ("input", "button"):
                label_bits.append(a.get("aria-label", ""))
            self.interactive.append({
                "tag": tag,
                "href": a.get("href", "") if tag == "a" else "",
                "name": a.get("name", ""),
                "id": a.get("id", ""),
                "aria_label": a.get("aria-label", ""),
                "class": (a.get("class") or "")[:120],
            })
        if tag == "button":
            self._in_button = True
            self._button_text = []
        if tag == "a" and a.get("href"):
            href = a["href"]
            absolute = urljoin(self.base_url, href) if self.base_url else href
            parsed = urlparse(absolute)
            link = {"text": "", "href": href, "absolute": absolute,
                    "external": bool(parsed.scheme in ("http", "https")) and self.base_url and urlparse(self.base_url).netloc not in ("", parsed.netloc)}
            self.links.append(link)
            if self._region_stack and any(r.startswith("navigation") or r == "nav" for r in self._region_stack[-2:]):
                self.nav_links.append(link)
        if tag == "img":
            self.images.append({"alt": a.get("alt", ""), "src": (a.get("src") or "")[:300], "width": a.get("width", ""), "height": a.get("height", "")})
        if tag in HEADING_TAGS:
            self._current_heading = None  # will be set by text
        cls = a.get("class") or ""
        first_cls = cls.split()[0] if cls else ""
        key = (tag, first_cls)
        if first_cls:
            self.class_counts[key] = self.class_counts.get(key, 0) + 1
        # meta handled in complete tag

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "meta":
            if a.get("name") == "description":
                self.meta_description = (a.get("content") or "")[:500]
            return
        self.handle_starttag(tag, attrs)
        if tag not in ("a", "button", "img", "meta"):
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TEXT_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag == "title":
            self._in_title = False
            return
        if tag in REGION_TAGS:
            if self._region_stack:
                self._region_stack.pop()
        if tag == "section" and self._section_depth:
            self._section_depth -= 1
        if tag in HEADING_TAGS:
            if self._current_heading is None:
                pass
            self._current_heading = None
        if tag == "button" and self._in_button:
            text = " ".join(self._button_text).strip()
            if text:
                self.buttons_text.append(text[:120])
            self._in_button = False
        if tag in FORM_CONTROLS and tag in ("input", "select", "textarea"):
            pass
        if tag == "form" and self._form_stack:
            self.forms.append(self._form_stack.pop())

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
            return
        self._emit_text(data)


def _infer_category(p: _PageParser) -> tuple[str, str]:
    """Heuristic content category + one-line purpose. Deterministic; explained
    in the record so a reviewer can see why."""
    text = " ".join(p.text_parts).lower()
    signals: list[tuple[str, int]] = []
    if p.meta_description:
        signals.append(("description", 1))
    if any(k in text for k in ("terms of use", "terms and conditions", "privacy policy", "cookie policy", "legal")):
        signals.append(("legal", 3))
    if any(k in text for k in ("documentation", "developer", "sdk", "api reference", "quick start", "getting started")):
        signals.append(("docs", 3))
    if p.forms:
        signals.append(("form", 2 * min(len(p.forms), 2)))
    if any(k in text for k in ("sign up", "log in", "sign in", "register", "log in")):
        signals.append(("auth", 2))
    if p._section_depth or sum(1 for t in p.element_counts if t.startswith("h")) > 6:
        signals.append(("content", 2))
    if any(k in text for k in ("game", "play", "world", "simulation")) and not p.forms:
        signals.append(("app", 2))
    if ERROR_PATTERNS.search(" ".join(p.text_parts)):
        signals.append(("error", 2))
    if not text.strip() and not p.links:
        return "empty", "No visible content; the page appears empty or JS-only."
    if not signals:
        return "content", "General content page (no strong signal detected)."
    signals.sort(key=lambda x: -x[1])
    top = signals[0][0]
    purpose_bits = []
    if p.title:
        purpose_bits.append(f"page titled “{p.title.strip()[:80]}”")
    if p.meta_description:
        purpose_bits.append(f"meta description: {p.meta_description[:120]}")
    if top == "legal":
        purpose_bits.append("legal/policy text dominates")
    elif top == "docs":
        purpose_bits.append("developer documentation signals (SDK/API references)")
    elif top == "form":
        purpose_bits.append(f"{len(p.forms)} form(s) with user input")
    elif top == "auth":
        purpose_bits.append("authentication entry points (sign up / log in)")
    elif top == "app":
        purpose_bits.append("application/game surface signals")
    elif top == "error":
        purpose_bits.append("error-state signals present")
    else:
        purpose_bits.append("content signals (headings/sections)")
    cat_map = {"legal": "legal", "docs": "docs", "form": "form", "auth": "landing",
               "app": "app", "error": "error", "content": "content", "description": "content"}
    return cat_map.get(top, "content"), ("Serves as a " + top + " page: " if top else "Purpose: ") + " ".join(purpose_bits)


def _detect_states(p: _PageParser) -> dict:
    text = " ".join(p.text_parts)
    stripped = text.strip()
    visible_words = len(stripped.split())
    return {
        "empty": bool(visible_words < 15 and not p.links),
        "loading": bool(LOADING_HINTS.search(stripped[:4000])) and visible_words < 300,
        "error": bool(ERROR_PATTERNS.search(stripped[:4000])),
        "visible_word_count": visible_words,
    }


def _repeated_components(p: _PageParser, min_count: int = 3) -> list[dict]:
    out = []
    for (tag, cls), count in sorted(p.class_counts.items(), key=lambda kv: -kv[1]):
        if count >= min_count:
            out.append({"tag": tag, "class": cls, "count": count})
    return out[:25]


def analyze_html(html: str, url: str = "", base_url: str = "") -> dict:
    """Return a structured page record dict (matches PageRecord.structure)."""
    base_url = base_url or url
    p = _PageParser(base_url)
    try:
        p.feed(html or "")
        p.close()
    except Exception as e:  # malformed HTML must never kill research
        p._emit_text(f"[parse warning: {e.__class__.__name__}]")
    title = p.title.strip()
    category, purpose = _infer_category(p)
    internal, external = [], []
    for l in p.links:
        item = {"text": (l.get("text") or "")[:120] or l["href"][:120], "href": l["href"][:400], "absolute": l["absolute"][:500]}
        (external if l["external"] else internal).append(item)
    # dedupe keeping order
    def _dedupe(items: list[dict]) -> list[dict]:
        seen, out = set(), []
        for it in items:
            k = (it.get("href"), it.get("text"))
            if k not in seen:
                seen.add(k)
                out.append(it)
        return out[:300]

    body_text = " ".join(p.text_parts)
    body_text = re.sub(r"\s+", " ", body_text).strip()[:MAX_BODY_TEXT]
    headings = [t[:160] for t in p.text_parts if False]  # placeholder (kept for API shape)
    # collect real headings via a second lightweight pass
    sections = _collect_sections(html)
    regions = {k: v[:40] for k, v in p.regions.items()}
    # collapse duplicate region entries
    for k in regions:
        seen, dedup = set(), []
        for v in regions[k]:
            if v and v not in seen:
                seen.add(v)
                dedup.append(v)
        regions[k] = dedup
    return {
        "title": title,
        "meta_description": p.meta_description,
        "content_category": category,
        "purpose": purpose,
        "summary": _summarize(title, body_text, p),
        "regions": regions,
        "navigation": _dedupe(p.nav_links),
        "forms": p.forms[:20],
        "controls": p.controls[:100],
        "interactive": p.interactive[:200],
        "buttons": p.buttons_text[:100],
        "sections": sections,
        "links": {"internal": _dedupe(internal), "external": _dedupe(external)},
        "images": p.images[:100],
        "states": _detect_states(p),
        "repeated_components": _repeated_components(p),
        "element_counts": {k: v for k, v in sorted(p.element_counts.items(), key=lambda kv: -kv[1])[:30]},
        "body_text": body_text,
        "visible_word_count": p.states_word_count if hasattr(p, "states_word_count") else None,
    }


def _collect_sections(html: str) -> list[dict]:
    """Heading-based section outline (level + text)."""

    class _Headings(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.sections: list[dict] = []
            self._tag: str | None = None
            self._buf: list[str] = []

        def handle_starttag(self, tag, attrs):
            if tag in HEADING_TAGS:
                self._tag = tag
                self._buf = []

        def handle_data(self, data):
            if self._tag:
                self._buf.append(data)

        def handle_endtag(self, tag):
            if tag == self._tag:
                text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
                if text:
                    self.sections.append({"level": int(tag[1]), "text": text[:160]})
                self._tag = None

    h = _Headings()
    try:
        h.feed(html or "")
        h.close()
    except Exception:
        pass
    return h.sections[:200]


def _summarize(title: str, body_text: str, p: _PageParser) -> str:
    parts = []
    if title:
        parts.append(f"“{title[:100]}”.")
    if p.meta_description:
        parts.append(f"Self-describes as: {p.meta_description[:160]}")
    first = body_text[:400].strip()
    if first and first.lower() not in (title or "").lower():
        parts.append(f"Opens with: {first}")
    if p.forms:
        fields = p.forms[0]["fields"]
        parts.append(f"Primary form collects: {', '.join(f.get('name') or f.get('placeholder') or f.get('type', '?') for f in fields[:8])}.")
    if p.buttons_text:
        parts.append(f"Primary actions: {', '.join(p.buttons_text[:6])}.")
    return " ".join(parts)
