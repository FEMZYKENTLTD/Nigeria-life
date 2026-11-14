"""Report generation: Markdown, JSON, CSV, HTML, PDF and Mermaid from one intermediate structure.
Every report states when it was generated, the investigation date range, and cites evidence IDs."""
from __future__ import annotations
import csv
import html as htmlmod
import io
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from . import analytics
from .config import get_settings
from .db import Evidence, Feature, Finding, Page, Project, Question, Report, Source, log, now
from .features import CATEGORIES, FIELDS
from .planner import assess

KINDS = {"executive": "Executive report", "feature_inventory": "Feature inventory", "technical": "Technical documentation (page records)",
         "competitive": "Competitive and gap analysis", "product_requirements": "Product requirements input", "roadmap": "Development roadmap input",
         "evidence_register": "Evidence register", "site_map": "Site map diagram", "completeness": "Completeness report"}
FORMATS = ["md", "json", "csv", "html", "pdf", "mmd"]


def _dates(s, pid):
    ev = s.query(Evidence).filter_by(project_id=pid).order_by(Evidence.captured_at).all()
    if not ev:
        return "no evidence recorded"
    a, b = ev[0].captured_at.date().isoformat(), ev[-1].captured_at.date().isoformat()
    return a if a == b else f"{a} to {b}"


def _refs(f):
    return ", ".join(f.evidence_refs or []) or "none cited"


def site_mermaid(pages) -> str:
    ids = {p.url: f"P{p.id}" for p in pages}
    lines = ["flowchart LR"]
    for p in pages:
        label = (urlparse(p.url).path or "/").replace('"', "'")[:50]
        lines.append(f'  {ids[p.url]}["{label} · {p.status}"]')
    seen = set()
    for p in pages:
        for l in (p.record or {}).get("internal_links", []):
            if l in ids and l != p.url and (p.url, l) not in seen:
                seen.add((p.url, l))
                lines.append(f"  {ids[p.url]} --> {ids[l]}")
        if p.discovered_from in ids and (p.discovered_from, p.url) not in seen:
            seen.add((p.discovered_from, p.url))
            lines.append(f"  {ids[p.discovered_from]} --> {ids[p.url]}")
    return "\n".join(lines)


def build(s, project: Project, kind: str) -> dict:
    if kind not in KINDS:
        raise ValueError(f"Unknown report kind '{kind}'")
    pid = project.id
    feats = s.query(Feature).filter_by(project_id=pid).order_by(Feature.category, Feature.name).all()
    pages = s.query(Page).filter_by(project_id=pid).order_by(Page.url).all()
    evid = s.query(Evidence).filter_by(project_id=pid).order_by(Evidence.ref).all()
    a = analytics.compute(s, project)
    sec = []

    def table(heading, header, rows, intro=""):
        sec.append({"heading": heading, "text": intro, "header": header, "rows": [[str(c) for c in r] for r in rows]})

    def text(heading, body):
        sec.append({"heading": heading, "text": body, "header": [], "rows": []})

    metric_rows = [[m["name"], "n/a" if m["value"] is None else f"{m['value']}{m['unit']}", m["formula"], json.dumps(m["inputs"])] for m in a["metrics"]]
    if kind == "executive":
        text("Objective", project.objective or "No objective recorded.")
        c = a["counts"]
        text("What the knowledge base holds", f"{c['features']} features, {c['findings']} findings, {c['evidence']} evidence items, "
             f"{sum(c['pages'].values())} pages ({json.dumps(c['pages'])}), {c['questions_open']} open questions.")
        table("Measures and how they were calculated", ["Measure", "Value", "Formula", "Inputs"], metric_rows)
        table("Features by category", ["Category", "Features"], [[x["category"], x["count"]] for x in a["features_by_category"]])
        table("Evidence by class", ["Class", "Items"], [[x["class"], x["count"]] for x in a["evidence_by_class"]])
        table("Recorded source conflicts", ["Conflict", "Status"], [[x["text"], x["status"]] for x in a["contradictions"]], a["contradiction_note"])
        table("Gaps", ["Gap", "Basis"], [[g["gap"], g["basis"]] for g in a["gaps"]])
    elif kind == "feature_inventory":
        table("Features", ["Name", "Category", "Confidence", "Status", *FIELDS, "Evidence IDs"],
              [[f.name, f.category, f.confidence, f.status, *[(f.fields or {}).get(k, "") for k in FIELDS], _refs(f)] for f in feats],
              "Empty cells mean the field has not been observed or written. They are left empty on purpose.")
    elif kind == "technical":
        table("Pages", ["URL", "Status", "HTTP", "Engine", "Category", "Purpose", "Forms", "Controls", "States", "Evidence"],
              [[p.url, p.status, p.http_status or "", p.engine, p.category, p.purpose, len((p.record or {}).get("forms", [])), len((p.record or {}).get("controls", [])),
                ", ".join((p.record or {}).get("states", [])), next((e.ref for e in evid if e.id == p.evidence_id), ", ".join((p.record or {}).get("evidence", [])))] for p in pages],
              "Rows with status 'imported' come from earlier research documents and were not captured by the engine.")
        finds = s.query(Finding).filter_by(project_id=pid).order_by(Finding.id).all()
        eref = {e.id: e.ref for e in evid}
        purl = {p.id: p.url for p in pages}
        table("Findings", ["ID", "Page", "Kind", "Observation", "Confidence", "Status", "Evidence", "Recorded"],
              [[f.uid, purl.get(f.page_id, ""), f.kind, f.observation, f.confidence, f.status, eref.get(f.evidence_id, ""), f.created_at.isoformat()[:19]] for f in finds])
    elif kind == "competitive":
        table("Gaps in the research", ["Gap", "Basis"], [[g["gap"], g["basis"]] for g in a["gaps"]])
        table("Opportunities written in the research", ["Feature", "Opportunity", "Evidence"], [[o["feature"], o["text"], ", ".join(o["evidence"])] for o in a["opportunities"]], a["opportunity_note"])
        table("Documented limitations of the subject", ["Feature", "Limitation", "Confidence", "Evidence"],
              [[f.name, f.fields["limitations"], f.confidence, _refs(f)] for f in feats if (f.fields or {}).get("limitations")])
        table("Possible duplicate features", ["A", "B", "Similarity", "Basis"], [[d["a"], d["b"], d["similarity"], d["basis"]] for d in a["duplicates"]])
    elif kind == "product_requirements":
        text("How to read this", "This is input for a requirements document, generated from the knowledge base. It lists what the research shows about each area. "
             "It does not decide what the product should do; that is a human decision.")
        for c in CATEGORIES:
            fs = [f for f in feats if f.category == c]
            if fs:
                table(c, ["Feature", "Description", "Dependencies", "Limitations / unknowns", "Implementation implications", "Confidence", "Evidence"],
                      [[f.name, (f.fields or {}).get("description", ""), (f.fields or {}).get("dependencies", ""), (f.fields or {}).get("limitations", ""),
                        (f.fields or {}).get("implementation_implications", ""), f.confidence, _refs(f)] for f in fs])
    elif kind == "roadmap":
        text("How to read this", "Ordering input only. Features are ranked by how many other documented features name them as a dependency. Priorities and dates are for people to set.")
        table("Most depended-on features", ["Feature", "Features that depend on it"], [[d["feature"], d["dependants"]] for d in a["dependencies"]["most_depended_on"]], a["dependencies"]["note"])
        table("Open questions to resolve first", ["Question", "Origin"], [[q.text, q.origin] for q in s.query(Question).filter_by(project_id=pid, status="open")])
        table("Missing documentation by field", ["Field", "Features missing it", "Of"], [[m["field"], m["missing"], m["of"]] for m in a["missing_fields"]])
    elif kind == "evidence_register":
        table("Evidence", ["ID", "Kind", "Class", "Source URL", "Locator", "Summary", "Captured (UTC)", "Captured by", "SHA-256", "File"],
              [[e.ref, e.kind, e.classification, e.source_url, e.locator, e.summary, e.captured_at.isoformat()[:19], e.captured_by, e.sha256, Path(e.file_path).name if e.file_path else ""] for e in evid])
    elif kind == "site_map":
        sec.append({"heading": "Navigation graph", "text": a["journeys"]["note"], "header": [], "rows": [], "mermaid": site_mermaid(pages)})
        table("Pages", ["URL", "Status", "Discovered from"], [[p.url, p.status, p.discovered_from] for p in pages])
    elif kind == "completeness":
        asm = assess(s, project)
        text("Verdict", asm["summary"])
        table("Criteria", ["Criterion", "Met", "Detail"], [[c["criterion"], "yes" if c["met"] else "no", c["detail"]] for c in asm["criteria"]])
        table("Measures and how they were calculated", ["Measure", "Value", "Formula", "Inputs"], metric_rows)
        from .db import Task
        table("Tasks that did not finish", ["Task", "Status", "Reason"], [[t.title, t.status, (t.error or "").splitlines()[0] if t.error else ""] for t in s.query(Task).filter(Task.project_id == pid, Task.status.in_(("failed", "blocked", "cancelled")))])
        table("Sources", ["Source", "URL", "Mode", "Approved"], [[x.name, x.base_url, x.automation, "yes" if x.approved else "no"] for x in s.query(Source).filter_by(project_id=pid)])
    return {"kind": kind, "title": f"{KINDS[kind]} — {project.name}", "project": project.name, "generated_at": now().isoformat()[:19] + "Z",
            "investigation_dates": _dates(s, pid), "evidence_ids_cited": sorted({r for f in feats for r in (f.evidence_refs or [])} | ({e.ref for e in evid} if kind in ("evidence_register", "technical") else set())),
            "generator": "Nigeria Life Intelligence Engine (rule-based; no language model wrote this text)", "sections": sec}


def _cell(c: str) -> str:
    return c.replace("|", "\\|").replace("\n", " ")


def to_md(d) -> str:
    out = [f"# {d['title']}", "", f"- Generated: {d['generated_at']}", f"- Investigation dates: {d['investigation_dates']}", f"- Generator: {d['generator']}",
           f"- Evidence IDs cited: {', '.join(d['evidence_ids_cited']) or 'none'}", ""]
    for sct in d["sections"]:
        out += [f"## {sct['heading']}", ""]
        if sct["text"]:
            out += [sct["text"], ""]
        if sct.get("mermaid"):
            out += ["```mermaid", sct["mermaid"], "```", ""]
        if sct["header"]:
            if sct["rows"]:
                out += ["| " + " | ".join(sct["header"]) + " |", "| " + " | ".join("---" for _ in sct["header"]) + " |"]
                out += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in sct["rows"]]
            else:
                out.append("_None recorded._")
            out.append("")
    return "\n".join(out)


def to_csv(d) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["# " + d["title"], "generated " + d["generated_at"], "investigation dates " + d["investigation_dates"]])
    for sct in d["sections"]:
        if sct["header"]:
            w.writerow([])
            w.writerow(["## " + sct["heading"]])
            w.writerow(sct["header"])
            w.writerows(sct["rows"])
    return buf.getvalue()


def to_html(d) -> str:
    e = htmlmod.escape
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{e(d['title'])}</title><style>"
             "body{background:#0b0b0c;color:#e8e4d9;font:15px/1.55 Georgia,serif;max-width:1100px;margin:40px auto;padding:0 24px}"
             "h1,h2{color:#c9a961;font-weight:normal}table{border-collapse:collapse;width:100%;font:13px/1.4 system-ui,sans-serif;margin:12px 0 28px}"
             "th,td{border:1px solid #2a2a2e;padding:6px 8px;text-align:left;vertical-align:top}th{background:#17171a;color:#c9a961}"
             ".meta{color:#9a968b;font:13px system-ui,sans-serif}pre{background:#17171a;padding:12px;overflow:auto}</style></head><body>",
             f"<h1>{e(d['title'])}</h1><p class='meta'>Generated {e(d['generated_at'])} · Investigation dates: {e(d['investigation_dates'])}<br>{e(d['generator'])}<br>"
             f"Evidence IDs cited: {e(', '.join(d['evidence_ids_cited']) or 'none')}</p>"]
    for sct in d["sections"]:
        parts.append(f"<h2>{e(sct['heading'])}</h2>")
        if sct["text"]:
            parts.append(f"<p>{e(sct['text'])}</p>")
        if sct.get("mermaid"):
            parts.append(f"<pre class='mermaid'>{e(sct['mermaid'])}</pre>")
        if sct["header"]:
            if sct["rows"]:
                parts.append("<table><thead><tr>" + "".join(f"<th>{e(h)}</th>" for h in sct["header"]) + "</tr></thead><tbody>")
                parts += ["<tr>" + "".join(f"<td>{e(c)}</td>" for c in r) + "</tr>" for r in sct["rows"]]
                parts.append("</tbody></table>")
            else:
                parts.append("<p><em>None recorded.</em></p>")
    return "".join(parts) + "</body></html>"


def to_mmd(d) -> str:
    for sct in d["sections"]:
        if sct.get("mermaid"):
            return sct["mermaid"]
    raise ValueError("This report kind has no diagram. Use kind 'site_map' for Mermaid output.")


def to_pdf(d, path: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    st = getSampleStyleSheet()
    cell = ParagraphStyle("cell", parent=st["BodyText"], fontSize=6.5, leading=8)
    esc = lambda x: htmlmod.escape(re.sub(r"[^\x09\x0a\x20-\x7e\u00a0-\u00ff]", "?", x[:600]))  # noqa: E731 - built-in PDF fonts are Latin-1 only
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), leftMargin=28, rightMargin=28, topMargin=28, bottomMargin=28, title=d["title"])
    flow = [Paragraph(esc(d["title"]), st["Title"]),
            Paragraph(esc(f"Generated {d['generated_at']} | Investigation dates: {d['investigation_dates']} | {d['generator']}"), st["Italic"]),
            Paragraph(esc("Evidence IDs cited: " + (", ".join(d["evidence_ids_cited"]) or "none")), cell), Spacer(1, 10)]
    for sct in d["sections"]:
        flow.append(Paragraph(esc(sct["heading"]), st["Heading2"]))
        if sct["text"]:
            flow.append(Paragraph(esc(sct["text"]), st["BodyText"]))
        if sct.get("mermaid"):
            flow.append(Paragraph(esc(sct["mermaid"]).replace("\n", "<br/>"), cell))
        if sct["header"] and sct["rows"]:
            data = [[Paragraph(f"<b>{esc(h)}</b>", cell) for h in sct["header"]]] + [[Paragraph(esc(c), cell) for c in r] for r in sct["rows"]]
            t = Table(data, repeatRows=1, colWidths=[(landscape(A4)[0] - 56) / len(sct["header"])] * len(sct["header"]))
            t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9dfc4")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            flow.append(t)
        elif sct["header"]:
            flow.append(Paragraph("None recorded.", st["Italic"]))
        flow.append(Spacer(1, 8))
    doc.build(flow)


def generate(s, project: Project, kind: str, formats: list[str]) -> list[dict]:
    d = build(s, project, kind)
    stamp = now().strftime("%Y%m%dT%H%M%S")
    folder = get_settings().data_dir / "reports" / str(project.id)
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for fmt in formats:
        if fmt not in FORMATS:
            raise ValueError(f"Unknown format '{fmt}'")
        path = folder / f"{kind}-{stamp}.{fmt}"
        if fmt == "pdf":
            to_pdf(d, path)
        else:
            path.write_text({"md": to_md, "csv": to_csv, "html": to_html, "mmd": to_mmd, "json": lambda x: json.dumps(x, indent=2)}[fmt](d), encoding="utf-8")
        r = Report(project_id=project.id, kind=kind, format=fmt, title=d["title"], path=str(path))
        s.add(r)
        s.flush()
        out.append(r.as_dict())
    log(s, "report_generated", project.id, kind=kind, formats=formats)
    return out
