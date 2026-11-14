"""Imports the research already committed to the project repository, so earlier work is reused rather than repeated.

Only what the documents state is imported. Class tags (C/S/I/H/U) are carried over unchanged.
"""
from __future__ import annotations
import re
from pathlib import Path

from .db import Evidence, Page, log
from .features import categorise
from .knowledge import add_evidence, add_question, upsert_feature, weakest

CLASS_MAP = {"C": "confirmed", "S": "secondary", "I": "inference", "H": "hypothesis", "U": "unknown"}
RESEARCH_DIR = "docs/research"


def split_row(line: str) -> list[str]:
    return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def md_tables(text: str) -> list[dict]:
    """Every pipe table with the nearest preceding heading."""
    out, heading, lines, i = [], "", text.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("#"):
            heading = ln.lstrip("#").strip()
        if ln.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:\-|]+\|\s*$", lines[i + 1]):
            header, rows, i = split_row(ln), [], i + 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = split_row(lines[i])
                if len(cells) == len(header):
                    rows.append(dict(zip(header, cells)))
                i += 1
            out.append({"heading": heading, "header": header, "rows": rows})
            continue
        i += 1
    return out


def classes_in(text: str) -> list[str]:
    return [CLASS_MAP[c] for c in re.findall(r"(?<![A-Za-z])([CSIHU])(?=\s*(?:\(|,|/|$|\s))", text) if c in CLASS_MAP]


def strip_md(s: str) -> str:
    return re.sub(r"[`*]|<br>", "", re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)).strip()


def import_research(s, project, repo_path: str) -> dict:
    root = Path(repo_path) / RESEARCH_DIR
    stats = {"read": [], "evidence": 0, "pages": 0, "features_created": 0, "features_updated": 0, "questions": 0, "missing_files": []}
    if not root.is_dir():
        raise FileNotFoundError(f"No research directory at {root}")

    def read(name: str) -> str:
        p = root / name
        if not p.exists():
            stats["missing_files"].append(name)
            return ""
        stats["read"].append(name)
        return p.read_text(encoding="utf-8")

    # The index and the investigation log are read first, before anything else is planned.
    readme, inv = read("README.md"), read("00-investigation-log.md")
    target = ""
    m = re.search(r"Target:\s*(https?://[^\s/]+)", inv + readme)
    if m:
        target = m.group(1)

    for t in md_tables(read("12-evidence-register.md")):
        if "ID" not in t["header"]:
            continue
        for r in t["rows"]:
            ref = r["ID"].strip()
            if not re.match(r"^E\d+$", ref):
                continue
            existed = s.query(Evidence).filter_by(project_id=project.id, ref=ref).first() is not None
            add_evidence(s, project.id, ref=ref, kind="import", source_url=strip_md(r.get("Source URL", ""))[:800],
                         locator=strip_md(r.get("Page / component", ""))[:400], summary=strip_md(r.get("Key observations", "")),
                         classification=CLASS_MAP.get(r.get("Class", "").strip(), "unknown"),
                         captured_by=f"imported:{RESEARCH_DIR}/12-evidence-register.md")
            stats["evidence"] += 0 if existed else 1

    for t in md_tables(inv):
        if t["header"][:2] == ["Route", "Result"]:
            for r in t["rows"]:
                for route in re.findall(r"`([^`]+)`", r["Route"]):
                    if not route.startswith("/") and "." not in route:
                        continue
                    url = (target + route) if route.startswith("/") else f"https://{route}"
                    if s.query(Page).filter_by(project_id=project.id, url=url).first():
                        continue
                    s.add(Page(project_id=project.id, url=url, status="imported", purpose=strip_md(r["Result"])[:1000],
                               record={"origin": f"{RESEARCH_DIR}/00-investigation-log.md", "evidence": re.findall(r"E\d+", r.get("Evidence", ""))}))
                    stats["pages"] += 1
        if t["header"][:1] == ["Topic"]:
            for r in t["rows"]:
                cells = list(r.values())
                stats["questions"] += add_question(s, project.id, f"Conflict — {strip_md(cells[0])}: {strip_md(cells[1])} vs {strip_md(cells[2])}", "conflict:00-investigation-log.md")

    section = re.search(r"## 7\. Open items.*?\n(.*?)(?=\n## |\Z)", inv, re.S)
    for item in re.findall(r"^\d+\.\s+(.*)$", section.group(1) if section else "", re.M):
        stats["questions"] += add_question(s, project.id, strip_md(item), "open-item:00-investigation-log.md")
    road = read("11-feature-roadmap.md")
    sec = re.search(r"### About Lagos Life\s*\n(.*?)(?=\n### |\n## |\Z)", road, re.S)
    for item in re.findall(r"^\d+\.\s+(.*)$", sec.group(1) if sec else "", re.M):
        stats["questions"] += add_question(s, project.id, strip_md(item), "unresolved:11-feature-roadmap.md")

    for t in md_tables(read("02-feature-inventory.md")):
        if t["header"][:1] != ["Feature"]:
            continue
        for r in t["rows"]:
            name = strip_md(r["Feature"])
            desc = strip_md(r.get("What it does and its rules", ""))
            ev = r.get("Evidence", "")
            if not name or desc in ("—", ""):
                desc = ""
            cat, basis = categorise(name, t["heading"] + " " + desc)
            fields = {"description": desc, "access_location": strip_md(r.get("Access", "")).replace("—", ""),
                      "dependencies": strip_md(r.get("Depends on / related", "")).replace("—", ""),
                      "limitations": strip_md(r.get("Limits and unknowns", "")).replace("—", ""),
                      "evidence": strip_md(ev)}
            _, action = upsert_feature(s, project.id, name, cat, fields, evidence_refs=re.findall(r"E\d+", ev),
                                       confidence=weakest(classes_in(ev)), origin=f"imported:{RESEARCH_DIR}/02-feature-inventory.md")
            stats["features_created"] += action == "created"
            stats["features_updated"] += action == "updated"
    for name in ("01-executive-intelligence-report.md", "03-page-by-page-audit.md", "04-user-journeys.md", "05-ui-ux-reference.md",
                 "06-technical-architecture.md", "07-data-entity-model.md", "08-business-model-analysis.md", "09-gap-analysis.md",
                 "10-nigeria-wide-blueprint.md"):
        if not (root / name).exists():
            stats["missing_files"].append(name)
    log(s, "research_imported", project.id, **stats)
    return stats
