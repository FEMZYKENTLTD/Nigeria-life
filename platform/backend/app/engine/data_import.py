"""Licensed / purchased / otherwise legally obtained dataset import.

The researcher uploads a file they lawfully hold (CSV / JSON / XML) with
mandatory provenance (where it came from) and license (what they may do
with it). That provenance is recorded on the Evidence row so every finding
can be traced to a defensible source — the same integrity rule as any other
evidence.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import xml.etree.ElementTree as ET

from sqlalchemy import select

from ..db import session_scope
from ..models import ActivityLog, DataAsset, Evidence, Observation
from .ids import new_id
from .knowledge import upsert_knowledge

log = logging.getLogger("rice.data")

SUPPORTED = ("csv", "json", "xml")
MAX_ROWS = 5000        # documented hard cap per import
KB_CAP = 200           # knowledge upserts per import
MAX_FILE_BYTES = 25 * 1024 * 1024


def detect_format(filename: str) -> str | None:
    ext = (filename or "").rsplit(".", 1)[-1].lower()
    return ext if ext in SUPPORTED else None


def parse_rows(filename: str, content: bytes) -> tuple[list[dict], str]:
    """Return (rows, error)."""
    fmt = detect_format(filename)
    if fmt is None:
        return [], f"unsupported format '.{filename.rsplit('.', 1)[-1] if '.' in filename else '?'}' (supported: {', '.join(SUPPORTED)})"
    text = content.decode("utf-8-sig", errors="replace")
    try:
        if fmt == "csv":
            reader = csv.DictReader(io.StringIO(text))
            rows = [{k: (v if v is not None else "") for k, v in row.items() if k}
                    for row in reader]
        elif fmt == "json":
            data = json.loads(text)
            if isinstance(data, dict):
                for key in ("rows", "results", "data", "items"):
                    if isinstance(data.get(key), list):
                        data = data[key]
                        break
                else:
                    data = [data]
            rows = [d if isinstance(d, dict) else {"value": d} for d in data]
        else:  # xml
            root = ET.fromstring(text)
            rows = []
            for el in root:
                rows.append(_xml_to_dict(el))
            if not rows:  # single-element document
                rows = [_xml_to_dict(root)]
        return rows[:MAX_ROWS], ""
    except Exception as e:
        return [], f"{fmt} parse failed: {e.__class__.__name__}: {e}"


def _xml_to_dict(el: ET.Element) -> dict:
    out: dict = {}
    for child in el:
        out[child.tag] = child.text or ""
    if not out and el.text:
        out["_text"] = el.text
    out.setdefault(el.tag, el.text or "")
    return out


def _row_text(row: dict) -> str:
    parts = []
    for k, v in row.items():
        if v in (None, ""):
            continue
        parts.append(f"{k}: {str(v)[:200]}")
        if sum(len(p) for p in parts) > 500:
            break
    return " | ".join(parts)[:500]


async def import_dataset(project_id: str, name: str, filename: str, content: bytes,
                         provenance: str, license_text: str,
                         evidence_class: str = "S", confidence: float = 0.6) -> dict:
    """Parse, persist evidence + observations, register the asset.
    Returns {ok, rows, observations, evidence_id, asset_id, error}."""
    if not provenance or not provenance.strip():
        return {"ok": False, "error": "provenance is required (where was this data obtained from?)"}
    if evidence_class not in ("C", "I", "S", "H", "U"):
        return {"ok": False, "error": "evidence_class must be one of C/I/S/H/U"}
    if not (0.0 <= confidence <= 1.0):
        return {"ok": False, "error": "confidence must be between 0 and 1"}

    rows, err = parse_rows(filename, content)
    if err:
        asset_id = new_id()
        async with session_scope() as s:
            s.add(DataAsset(id=asset_id, project_id=project_id, name=name or filename,
                            filename=filename, format=detect_format(filename) or "",
                            provenance=provenance, license=license_text,
                            rows=0, status="error", error=err))
            await s.commit()
        return {"ok": False, "asset_id": asset_id, "error": err}

    evidence_id = new_id()
    async with session_scope() as s:
        ev = Evidence(
            id=evidence_id, project_id=project_id, ref_code="",
            evidence_class=evidence_class, source_uri=provenance,
            source_name=name or filename, capture_method="data_import",
            description=f"{len(rows)} row(s) from {filename}. License: {license_text or 'not stated'}. "
                        f"Provenance: {provenance}",
            meta={"format": detect_format(filename), "filename": filename},
        )
        s.add(ev)
        await s.flush()
        n = 0
        for i, row in enumerate(rows):
            text = _row_text(row)
            if not text:
                continue
            s.add(Observation(
                project_id=project_id, kind="fact", observation=text,
                key=f"dataset:{(name or filename)}#{i}", value="",
                evidence_ids=[evidence_id], evidence_class=evidence_class,
                confidence=confidence, status="open", created_by="import",
            ))
            n += 1
        asset = DataAsset(project_id=project_id, name=name or filename,
                          filename=filename, format=detect_format(filename) or "",
                          provenance=provenance, license=license_text,
                          rows=len(rows), evidence_id=evidence_id, status="imported")
        s.add(asset)
        await s.flush()
        asset_id = asset.id
        s.add(ActivityLog(project_id=project_id, actor="import",
                          action="data_asset.import", subject=name or filename,
                          detail=f"{len(rows)} rows, class {evidence_class}, {n} findings"))
        await s.commit()

    for i, row in enumerate(rows[:KB_CAP]):
        text = _row_text(row)
        if text:
            await upsert_knowledge(project_id, "observation",
                                   f"{asset_id}:{i}", f"Dataset {(name or filename)[:80]}", text)
    log.info("data asset %s: %d rows → %d findings", asset_id[:10], len(rows), n)
    return {"ok": True, "rows": len(rows), "observations": n,
            "evidence_id": evidence_id, "asset_id": asset_id, "error": ""}
