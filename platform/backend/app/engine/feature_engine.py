"""Feature intelligence engine.

Extracts feature candidates from structured page records (forms, controls,
buttons, nav, headings) and normalises them into the 15-field feature model
across the 20 required categories. Heuristic + deterministic; AI may later
enrich the same records.

Categorisation rules are documented per decision so output is explainable.
"""
from __future__ import annotations

import re

from .textsim import jaccard, normalize, token_set

# Order matters: specific revenue-surface terms (advertising, subscriptions,
# billing) are checked before generic economy terms (pay/price) so that e.g.
# "self-serve advertising" is monetisation while "Game Naira" stays economy.
CATEGORY_RULES: list[tuple[str, re.Pattern]] = [
    ("authentication", re.compile(r"(sign ?up|log ?in|log ?out|register|password|account recovery|2fa|oauth|age gate)", re.I)),
    ("user_profiles", re.compile(r"(profile|avatar|bio|preferences|account settings|my page|personal)", re.I)),
    ("character_systems", re.compile(r"(character|sim|avatar creation|creator|traits|needs|skills|mood)", re.I)),
    ("monetisation", re.compile(r"(advertis|billboard|subscription|billing|checkout|invoice|sponsor|pricing plan)", re.I)),
    ("economy", re.compile(r"(currency|balance|wallet|earn|spend|pay|price|fee|tax|loan|transaction|ledger|top-?up|purchase|buy)", re.I)),
    ("employment", re.compile(r"(job|career|shift|work|hiring|application|payroll|wage|resume|cv)", re.I)),
    ("business_management", re.compile(r"(business|store management|inventory|staff|pos|enterprise setup)", re.I)),
    ("marketplace", re.compile(r"(marketplace|listing|market|trade|auction|vendor|merchant|catalogue|catalog)", re.I)),
    ("virtual_assets", re.compile(r"(item|asset|skin|collectible|inventory item|digital good|token|gem)", re.I)),
    ("property", re.compile(r"(property|real estate|house|apartment|land|plot|rent|lease|estate)", re.I)),
    ("transportation", re.compile(r"(transport|travel|ride|route|fare|vehicle|fleet|logistics|delivery|dispatch)", re.I)),
    ("geography", re.compile(r"(map|location|region|city|state|district|geo|area|place|address|address book)", re.I)),
    ("social_interaction", re.compile(r"(friend|message|chat|group|community|social|follow|comment|share|dm|voice|forum|feed|social feed)", re.I)),
    ("entertainment", re.compile(r"(game|music|video|stream|watch|play|event|event ticket|theatre|club|entertainment|media)", re.I)),
    ("achievements", re.compile(r"(achievement|badge|award|trophy|certificate|milestone|leaderboard|rank|rankings|points)", re.I)),
    ("progression", re.compile(r"(level|progress|quest|mission|xp|experience|streak|progression|onboarding|tutorial)", re.I)),
    ("notifications", re.compile(r"(notification|alert|reminder|push|email|sms|inbox)", re.I)),
    ("settings", re.compile(r"(settings|preference|privacy|security|accessibility|language|theme|timezone|configuration|options)", re.I)),
    ("administration", re.compile(r"(admin|moderation|dashboard admin|review|approval|compliance|audit|governance|back office)", re.I)),
    ("monetisation", re.compile(r"(payment|store|shop|commerce|sell)", re.I)),
]


def categorize(text: str) -> tuple[str, str]:
    """Return (category, matched_rule) for explainability."""
    for cat, pattern in CATEGORY_RULES:
        m = pattern.search(text or "")
        if m:
            return cat, f"matched /{pattern.pattern[:60]}…/ on “{m.group(0)}”"
    return "other", "no rule matched"


def slugify(name: str) -> str:
    s = normalize(name)
    s = re.sub(r"[\s_]+", "-", s)
    return s[:200] or "unnamed"


def _field(value: str) -> str:
    return (value or "").strip()


def feature_from_page_record(page: dict) -> list[dict]:
    """Derive feature candidates from one structured page record.

    Each candidate is a dict with the 15 model fields (some possibly empty).
    Dedup happens at upsert time via name-slug + similarity.
    """
    st = page.get("structure") or {}
    title = page.get("title") or ""
    purpose = page.get("purpose") or ""
    url = page.get("url") or ""
    summary = page.get("summary") or ""
    candidates: list[dict] = []
    seen: set[frozenset[str]] = set()

    def push(name: str, description: str, access: str, inputs: str, outputs: str,
             behaviour: str, category_hint: str = "", evidence: list[str] | None = None) -> None:
        name = re.sub(r"\s+", " ", name).strip(" :|·")
        if not name or len(name) < 3:
            return
        key = token_set(name)
        for s in seen:
            if jaccard(name, " ".join(s)) > 0.85:
                return
        seen.add(key)
        cat, rule = categorize(f"{name} {description} {category_hint}")
        candidates.append({
            "name": name[:200],
            "category": cat,
            "category_rule": rule,
            "description": description[:1000],
            "purpose": (purpose[:400] if purpose else f"Part of the surface at {url}"),
            "user_type": "visitor" if page.get("content_category") in ("landing", "form", "legal") else "user",
            "access_location": access or url,
            "inputs": inputs,
            "outputs": outputs,
            "observed_behaviour": behaviour,
            "dependencies": [],
            "related_features": [],
            "user_journey": "",
            "limitations": "Auto-extracted candidate — field detail pending verification.",
            "opportunities": "",
            "implementation_implications": "",
            "evidence_ids": evidence or [],
            "confidence": 0.4,
            "status": "draft",
        })

    # 1) forms → features (strongest signal)
    for form in st.get("forms", [])[:10]:
        fields = form.get("fields", [])
        field_names = [_field(f.get("name") or f.get("placeholder") or f.get("type")) for f in fields if f.get("type") != "hidden"]
        field_names = [f for f in field_names if f][:12]
        action = form.get("action") or "page form"
        verb = "submits" if form.get("method") == "post" else "queries"
        push(
            f"Form: {action.split('/')[-1][:40] or 'page form'}" if action != "page form" else "Page form",
            f"Form at {url} {verb} {form.get('method','post')}: collects " + (", ".join(field_names) or "(no named fields)"),
            url,
            "; ".join(field_names),
            "server response (not observed automatically — record via interaction log)",
            f"Visible form with {len(fields)} control(s); required markers observed: {sum(1 for f in fields if f.get('required'))}",
            evidence=page.get("evidence_refs"),
        )
    # 2) primary buttons/CTAs
    for b in (st.get("buttons") or [])[:12]:
        if len(b) < 4:
            continue
        push(
            f"Action: {b[:60]}",
            f"Primary action labelled “{b}” on {url}.",
            url,
            "click",
            "navigation or submission (not operated automatically)",
            "Observed as a visible button/CTA; behaviour not exercised to stay within collection permissions.",
            evidence=page.get("evidence_refs"),
        )
    # 3) navigation clusters → sections as features
    nav = st.get("navigation") or []
    if nav:
        labels = [re.sub(r"\s+", " ", (n.get("text") or "")).strip() for n in nav if (n.get("text") or "").strip()]
        labels = [l for l in dict.fromkeys(labels) if 2 < len(l) < 40][:15]
        if labels:
            push(
                "Primary navigation",
                f"Site navigation exposes: {', '.join(labels)}.",
                url,
                "link selection",
                "page transition to listed sections",
                f"{len(labels)} distinct navigation targets observed.",
            )
    # 4) headings → content sections (only distinctive ones)
    sections = [s for s in st.get("sections", []) if s.get("level") in (1, 2)][:8]
    for s in sections:
        text = re.sub(r"\s+", " ", s.get("text", "")).strip()
        if 4 < len(text) < 60 and not re.search(r"^(home|skip|menu)$", text, re.I):
            push(
                f"Section: {text[:60]}",
                f"Content section “{text}” on {url} (heading level {s.get('level')}).",
                f"{url} → “{text[:40]}”",
                "reading",
                "content of the section",
                "Observed as a page section; content summarised in page record.",
            )
    if not candidates and page.get("status") == "documented":
        push(
            f"Page surface: {title[:50] or url}",
            f"Documented page {url} (category: {page.get('content_category') or 'unknown'}). No strong feature signals (forms/CTAs) detected.",
            url, "n/a", "n/a",
            page.get("summary") or "See page record.",
        )
    return candidates


def find_similar_existing(name: str, existing: list[dict]) -> dict | None:
    """Best existing feature by Jaccard similarity over name (+description).
    Used to merge auto-extracted candidates instead of creating duplicates."""
    best, best_sim = None, 0.0
    for f in existing:
        sim = jaccard(name, f.get("name", "") + " " + (f.get("description") or "")[:120])
        if sim > best_sim:
            best, best_sim = f, sim
    return best if best_sim >= 0.5 else None
