"""Page understanding: turns captured HTML into a structured page record using deterministic rules.

Everything here is derived from the markup that was captured. Nothing is guessed about behaviour that was not observed:
controls are listed as present, not as "working".
"""
from __future__ import annotations
import hashlib
import re
from collections import Counter
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

PURPOSE_RULES = [  # (category, purpose sentence, keywords matched against url path + title + headings)
    ("authentication", "Sign-in or account creation", r"\b(log ?in|sign ?in|sign ?up|register|password|forgot)\b"),
    ("legal", "Legal or policy document", r"\b(terms|privacy|cookie|disclaimer|policy|guidelines|agreement|legal)\b"),
    ("support", "Help, support or reporting", r"\b(help|support|faq|contact|report)\b"),
    ("commerce", "Purchase, pricing or advertising", r"\b(pricing|price|checkout|cart|buy|advertis|billing|plans?)\b"),
    ("developer", "Developer documentation", r"\b(developers?|api|sdk|docs|documentation|webhook)\b"),
    ("error", "Error page", r"\b(404|not found|error|offline)\b"),
    ("profile", "Profile or settings", r"\b(profile|settings|account|dashboard)\b"),
    ("marketplace", "Listing or marketplace", r"\b(market|shop|store|listing|catalog)\b"),
]
STATE_RULES = {
    "error": r"\b(404|not found|something went wrong|error occurred|access denied|forbidden)\b",
    "empty": r"\b(no results|nothing here|no items|empty|nothing to show)\b",
    "loading": r"\b(loading|please wait|still loading)\b",
    "offline": r"\b(you'?re offline|no connection)\b",
    "auth_gate": r"\b(sign in first|log in to continue|please (log|sign) in)\b",
}


def _txt(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)) if el else ""


def normalise_url(base: str, href: str) -> str | None:
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
        return None
    u = urldefrag(urljoin(base, href))[0]
    p = urlparse(u)
    if p.scheme not in ("http", "https"):
        return None
    path = p.path or "/"
    return f"{p.scheme}://{p.netloc.lower()}{path}" + (f"?{p.query}" if p.query else "")


def analyse(html: str, url: str, rendered: bool = False) -> dict:
    soup = BeautifulSoup(html or "", "html.parser")
    for t in soup(["script", "style", "noscript", "template"]):
        t.decompose()
    title = _txt(soup.title) if soup.title else ""
    headings = [{"level": int(h.name[1]), "text": _txt(h)[:200]} for h in soup.find_all(re.compile(r"^h[1-6]$")) if _txt(h)]
    host = urlparse(url).netloc.lower()

    regions = []
    for tag, role in (("header", "banner"), ("nav", "navigation"), ("main", "main"), ("aside", "complementary"), ("footer", "contentinfo")):
        els = soup.find_all(tag) + [e for e in soup.find_all(attrs={"role": role}) if e.name != tag]
        if els:
            regions.append({"region": tag, "count": len(els), "sample": _txt(els[0])[:160]})
    dialogs = soup.find_all(attrs={"role": re.compile("dialog")}) + soup.find_all("dialog")
    if dialogs:
        regions.append({"region": "dialog", "count": len(dialogs), "sample": _txt(dialogs[0])[:160]})

    links, nav_links, seen = [], [], set()
    nav_anchor_ids = {id(a) for nav in soup.find_all(["nav", "header"]) for a in nav.find_all("a")}
    for a in soup.find_all("a", href=True):
        n = normalise_url(url, a["href"])
        if not n or n in seen:
            continue
        seen.add(n)
        item = {"url": n, "text": _txt(a)[:120], "internal": urlparse(n).netloc.lower() == host}
        links.append(item)
        if id(a) in nav_anchor_ids:
            nav_links.append(item)

    forms = []
    for f in soup.find_all("form"):
        fields = []
        for i in f.find_all(["input", "select", "textarea"]):
            itype = (i.get("type") or i.name).lower()
            if itype == "hidden":
                continue
            fields.append({"name": i.get("name") or i.get("id") or "", "type": itype, "required": i.has_attr("required"),
                           "label": (i.get("aria-label") or i.get("placeholder") or "")[:80],
                           "maxlength": i.get("maxlength") or ""})
        forms.append({"action": f.get("action") or "", "method": (f.get("method") or "get").lower(), "fields": fields,
                      "submit": [_txt(b)[:60] or b.get("value", "") for b in f.find_all(["button", "input"]) if (b.get("type") or "submit").lower() == "submit" and b.name in ("button", "input") and (b.name == "button" or b.get("type") == "submit")]})

    controls = []
    for b in soup.find_all(["button", "select", "textarea", "summary"]) + soup.find_all("input") + soup.find_all(attrs={"role": re.compile(r"^(button|tab|switch|checkbox|menuitem|combobox|slider)$")}):
        kind = b.get("role") or ((b.get("type") or "text") if b.name == "input" else b.name)
        if kind == "hidden":
            continue
        label = (_txt(b) or b.get("aria-label") or b.get("placeholder") or b.get("value") or b.get("name") or "")[:80]
        controls.append({"kind": kind, "label": label})
    seen_c, uniq_controls = set(), []
    for c in controls:
        k = (c["kind"], c["label"])
        if k not in seen_c:
            seen_c.add(k)
            uniq_controls.append(c)

    sections = [{"heading": h["text"], "level": h["level"]} for h in headings if h["level"] <= 3]
    body_text = _txt(soup.body or soup)

    # repeated components: sibling groups that share the same tag + class signature at least 3 times
    sigs = Counter()
    for el in soup.find_all(True):
        cls = el.get("class")
        if cls and el.name in ("li", "div", "article", "section", "tr", "a", "button"):
            sigs[(el.name, " ".join(sorted(cls))[:80])] += 1
    repeated = [{"tag": t, "class": c, "count": n} for (t, c), n in sigs.most_common(8) if n >= 3]

    probe = f"{urlparse(url).path} {title} {' '.join(h['text'] for h in headings[:5])}".lower()
    category, purpose, basis = "content", "General content page", "no purpose rule matched"
    for cat, sentence, pat in PURPOSE_RULES:
        m = re.search(pat, probe)
        if m:
            category, purpose, basis = cat, sentence, f"keyword '{m.group(0)}' in URL, title or headings"
            break
    if category == "content" and any(any(fl["type"] == "password" for fl in f["fields"]) for f in forms):
        category, purpose, basis = "authentication", "Sign-in or account creation", "page contains a password field"

    head = (title + " " + body_text[:1500]).lower()
    states = [name for name, pat in STATE_RULES.items() if re.search(pat, head)]
    if len(body_text) < 200 and not rendered:
        states.append("possibly_client_rendered")

    return {
        "url": url, "title": title, "purpose": purpose, "purpose_basis": basis, "category": category,
        "headings": headings[:60], "sections": sections[:60], "regions": regions,
        "navigation": nav_links[:60], "links": links[:300],
        "internal_links": [l["url"] for l in links if l["internal"]][:300],
        "forms": forms, "controls": uniq_controls[:150], "repeated_components": repeated,
        "states": states, "word_count": len(body_text.split()), "rendered_with_js": rendered,
        "text": body_text[:20000],
        "content_hash": hashlib.sha256(body_text.encode()).hexdigest(),
    }


def findings_from_record(rec: dict) -> list[dict]:
    """Atomic, evidence-backed observations about what is present on the page."""
    out = [{"kind": "page", "observation": f"Page '{rec['title'] or rec['url']}' classified as {rec['category']} ({rec['purpose_basis']})."}]
    for f in rec["forms"]:
        names = ", ".join(x["name"] or x["type"] for x in f["fields"]) or "no visible fields"
        out.append({"kind": "form", "observation": f"Form present (method {f['method']}, action '{f['action'] or 'same page'}') with fields: {names}."})
    if rec["navigation"]:
        out.append({"kind": "navigation", "observation": "Navigation links present: " + "; ".join(n["text"] or n["url"] for n in rec["navigation"][:15]) + "."})
    btns = [c["label"] for c in rec["controls"] if c["kind"] in ("button", "submit") and c["label"]]
    if btns:
        out.append({"kind": "controls", "observation": "Buttons present: " + "; ".join(btns[:20]) + "."})
    for st in rec["states"]:
        out.append({"kind": "state", "observation": f"Page text matches the '{st}' state pattern."})
    for r in rec["repeated_components"][:3]:
        out.append({"kind": "component", "observation": f"Repeated component: <{r['tag']} class='{r['class']}'> appears {r['count']} times."})
    return out
