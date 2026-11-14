"""Research task planner.

Decomposes a research objective into a typed, prioritised subtask graph:
discover → fetch → understand → document → analyse → report.

The heuristic planner below is deterministic and works fully offline; when an
AI provider is configured, the LLM planner produces the same output schema
(extra context, extra pages) and is used instead. Both outputs are persisted
on the task (``plan``) and drive the agent loop — the loop itself is
provider-agnostic.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from .ids import new_id

SUBTASK_TYPES = ("discover", "fetch", "understand", "document", "analyse", "report")


def _urls_in_text(text: str) -> list[str]:
    found = re.findall(r"https?://[^\s\)\]\"',;]+", text or "")
    out, seen = [], set()
    for u in found:
        u = u.rstrip(".,")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[:50]


def heuristic_plan(project: dict, task: dict, sources: list[dict],
                   report_types: list[str] | None = None) -> dict:
    """Build the standard investigation plan for an objective.

    Report types produced at the end default to the core trio; callers can
    extend (the Reports UI can generate any type on demand).
    """
    base_url = (project.get("target_base_url") or "").strip().rstrip("/")
    known_urls: list[str] = []
    for s in sources:
        if s.get("status") == "authorised" and s.get("url"):
            known_urls.append(s["url"].strip())
    mentioned = _urls_in_text(task.get("objective", ""))
    for u in mentioned:
        if u not in known_urls:
            known_urls.append(u)
    if base_url and base_url not in known_urls:
        known_urls.insert(0, base_url)

    subtasks: list[dict] = []
    idx = 0

    def add(type_: str, description: str, priority: int = 3, requires_approval: bool = False, **extra) -> None:
        nonlocal idx
        subtasks.append({
            "id": new_id(),
            "idx": idx,
            "type": type_,
            "description": description,
            "status": "queued",
            "priority": priority,
            "requires_approval": requires_approval,
            "checkpoint": {},
            "output": {},
            "attempts": 0,
            "max_attempts": 3 if type_ in ("fetch",) else 1,
            "last_error": "",
        })
        idx += 1

    add("discover", "Compile the page queue from authorised sources and objective-mentioned URLs.", priority=1)
    for i, u in enumerate(known_urls[:25]):
        add("fetch", f"Capture page {i + 1}/{len(known_urls[:25])}: {u[:200]}", priority=2, **{"_url": u})
    add("understand", "Analyse all captured pages into structured records (regions, controls, forms, states, links).", priority=2)
    add("document", "Extract and upsert feature documentation from structured page records and existing findings.", priority=2)
    add("analyse", "Run deterministic analytics (coverage, completeness, duplicates, contradictions, gaps).", priority=2)
    reports = report_types or ["feature_inventory", "evidence_register", "completion_report"]
    for rt in reports:
        add("report", f"Generate report: {rt.replace('_', ' ')}.", priority=3)

    return {
        "planner": "heuristic-v1",
        "objective": task.get("objective", ""),
        "url_queue": known_urls[:50],
        "notes": (
            "Standard six-phase plan. 'fetch' subtasks honour per-project collection permissions; "
            "if a source is unreachable or does not permit automated capture, the step fails with a "
            "recorded reason and the task switches to manual evidence import (never silently skipped)."
        ),
        "subtasks": subtasks,
    }


def llm_plan(project: dict, task: dict, sources: list[dict], ai_client,
             report_types: list[str] | None = None) -> dict:
    """LLM-assisted plan. Output must match the heuristic schema; the agent
    loop validates it and falls back to the heuristic plan on any problem.
    """
    base = heuristic_plan(project, task, sources, report_types)
    prompt = (
        "You are the planning module of a website research platform. Decompose the research objective "
        "below into investigation subtasks of these exact types: discover, fetch, understand, document, "
        "analyse, report. Respond with STRICT JSON only, matching: "
        '{"notes": str, "subtasks": [{"type": one of the six types, "description": str, "priority": 1-3, '
        '"url": optional str}]}. Do not invent URLs beyond those provided. Keep it under 30 subtasks.\n\n'
        f"Project: {project.get('name')} — {project.get('description', '')}\n"
        f"Objective: {task.get('objective', '')}\n"
        f"Known authorised sources: {json.dumps([s.get('url') for s in sources if s.get('status') == 'authorised'])}\n"
        f"Project instructions: {project.get('instructions', '')[:800]}"
    )
    try:
        raw = ai_client.complete(prompt, system="You output strict JSON only. No commentary.")
        data = json.loads(_extract_json(raw))
        subtasks_raw = data.get("subtasks") or []
        subtasks = []
        idx = 0
        for st in subtasks_raw[:30]:
            t = str(st.get("type", "")).lower()
            if t not in SUBTASK_TYPES:
                continue
            url = str(st.get("url", "")).strip()
            desc = str(st.get("description", "")) or f"{t} step"
            if t == "fetch" and url and url not in base["url_queue"]:
                base["url_queue"].append(url)
            subtasks.append({
                "id": new_id(), "idx": idx, "type": t, "description": desc[:500],
                "status": "queued", "priority": int(st.get("priority", 3) or 3),
                "requires_approval": False, "checkpoint": {}, "output": {},
                "attempts": 0, "max_attempts": 3 if t == "fetch" else 1, "last_error": "",
                "_url": url if t == "fetch" else None,
            })
            idx += 1
        if not subtasks:
            return base
        base["planner"] = "llm-v1"
        base["notes"] = str(data.get("notes", base["notes"]))[:1000]
        base["subtasks"] = subtasks
        return base
    except Exception:
        # LLM plan must never break research: fall back deterministically.
        base["planner"] = "heuristic-v1 (llm fallback)"
        return base


def _extract_json(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        return raw[start:end + 1]
    return raw
