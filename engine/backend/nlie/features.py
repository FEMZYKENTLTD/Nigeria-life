"""Feature intelligence: categorise and document features with the 15 required fields."""
from __future__ import annotations
import re

CATEGORIES = ["Authentication", "User profiles", "Character systems", "Economy", "Employment", "Business management",
              "Marketplace", "Virtual assets", "Property", "Transportation", "Geography", "Social interaction",
              "Entertainment", "Achievements", "Progression", "Notifications", "Settings", "Administration",
              "Monetisation", "Other"]

FIELDS = ["description", "purpose", "user_type", "access_location", "inputs", "outputs", "observed_behaviour",
          "dependencies", "related_features", "user_journey", "evidence", "limitations", "opportunities",
          "implementation_implications"]  # + name = 15

RULES = [  # first match wins; ordered from specific to general
    ("Authentication", r"\b(sign[- ]?up|log[- ]?in|sign[- ]?in|password|session|age gate|recovery|one device|account merge|stolen-account)\b"),
    ("Notifications", r"\b(notification|push|alert)s?\b"),
    ("Settings", r"\b(settings?|preferences|theme|account deletion|delete account)\b"),
    ("Achievements", r"\b(achievement|badge|trophy|streak)s?\b"),
    ("Monetisation", r"\b(top-?up|real[- ]money|advertis\w*|billboard|sea plots?|sponsor\w*|revenue|payout|purchase with real|developer platform|partner stores?)\b"),
    ("Transportation", r"\b(transport|travel|flight|bus|drive|car|vehicle|danfo|keke|okada|cab|airport|boat|jet|helipad)s?\b"),
    ("Property", r"\b(rent\w*|home|house|land|plot|furnish\w*|estate)s?\b"),
    ("Business management", r"\b(business\w*|haulage|start-?up|enterprise|kiosk)\b"),
    ("Employment", r"\b(job|career|shift|work|gig|salary|pay|degree premium)s?\b"),
    ("Marketplace", r"\b(market\w*|trading|listing|hustle board)\b"),
    ("Virtual assets", r"\b(item|asset|inventory|furniture|sticker)s?\b"),
    ("Economy", r"\b(naira|currency|tax|loan|ledger|transfer|invest\w*|insurance|bet\w*|casino|money|economy|wallet)\b"),
    ("Character systems", r"\b(sim|character|avatar|look|personality|trait|needs?|mood\w*|skills?|sickness|birth lottery|dream)\b"),
    ("Progression", r"\b(level|progress\w*|promotion|xp|experience|new life|game clock)\b"),
    ("Geography", r"\b(map|city|cities|venue|location|geograph\w*|coming soon)\b"),
    ("Social interaction", r"\b(chat|friend|message|dm|voice|relationship|gist|group|follow\w*|report|block|knock|presence|club music)s?\b"),
    ("Entertainment", r"\b(game|gem hunt|match|football|event|activit\w*|leaderboard)s?\b"),
    ("Administration", r"\b(moderation|strike|admin|support|governor|election|polic\w*|court|crime|police|commissioner|teen space|anti-abuse|ai helper)\b"),
    ("User profiles", r"\b(profile|username|bio)\b"),
]


def categorise(name: str, description: str = "") -> tuple[str, str]:
    """Returns (category, basis). Name is matched first, then description."""
    for text, where in ((name, "name"), (description, "description")):
        for cat, pat in RULES:
            m = re.search(pat, text.lower())
            if m:
                return cat, f"keyword '{m.group(0)}' in {where}"
    return "Other", "no category rule matched"


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:190] or "feature"


def field_completeness(fields: dict) -> tuple[int, list[str]]:
    missing = [f for f in FIELDS if not str(fields.get(f) or "").strip()]
    return len(FIELDS) - len(missing), missing


def features_from_page(rec: dict, evidence_ref: str) -> list[dict]:
    """Candidate features that the page markup directly supports. Fields that were not observed are left blank
    on purpose so the analytics can report them as missing rather than hide them."""
    out = []
    for f in rec.get("forms", []):
        types = {x["type"] for x in f["fields"]}
        names = [x["name"] or x["type"] for x in f["fields"]]
        if "password" in types:
            name = "Sign-up form" if len([t for t in f["fields"] if t["type"] == "password"]) > 1 or re.search(r"sign ?up|register", rec["title"].lower() + f["action"].lower()) else "Log-in form"
        elif "search" in types or any("search" in n.lower() or n.lower() == "q" for n in names):
            name = "Search"
        elif "file" in types:
            name = f"File upload form on {rec['title'] or rec['url']}"
        else:
            name = f"Form on {rec['title'] or rec['url']}"
        cat, _ = categorise(name, rec["purpose"])
        out.append({"name": name, "category": cat, "fields": {
            "description": f"A form with fields: {', '.join(names) or 'none visible'}.",
            "access_location": rec["url"], "inputs": ", ".join(names),
            "observed_behaviour": f"Markup only: method {f['method']}, action '{f['action'] or 'same page'}'. The form was not submitted.",
            "evidence": evidence_ref}})
    if rec.get("navigation"):
        out.append({"name": "Site navigation", "category": "Other", "fields": {
            "description": "Navigation links: " + "; ".join(n["text"] or n["url"] for n in rec["navigation"][:15]),
            "access_location": rec["url"], "observed_behaviour": "Links present in header/nav markup. Not clicked.",
            "evidence": evidence_ref}})
    return out
