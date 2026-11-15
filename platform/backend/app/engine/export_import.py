"""Database backups + project export/import.

Backups: WAL checkpoint + a consistent copy of the SQLite database into
``data/backups/`` (retention-bounded). Postgres deployments keep the
documented ``pg_dump`` path; the API reports that honestly.

Export/import: a versioned JSON bundle of one project (pages, features,
evidence, observations, questions, sources, scopes, reports) that can be
moved between installations. Import validates the bundle, generates fresh
ids, and remaps every cross-reference — the imported project is fully
isolated from the source.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import time

from sqlalchemy import select, text

from ..config import get_settings
from ..db import session_scope
from ..engine.feature_engine import slugify
from ..engine.ids import new_id
from ..engine.knowledge import upsert_knowledge
from ..models import (ActivityLog, CollectionScope, DataAsset, Evidence, Feature,
                      Observation, PageRecord, Project, Report, Source,
                      UnresolvedQuestion)

log = logging.getLogger("rice.backup")

EXPORT_VERSION = 1
MAX_BACKUPS = 20


# ---------------------------------------------------------------- backups

async def create_backup() -> dict:
    s = get_settings()
    if not s.db_url.startswith("sqlite"):
        return {"ok": False,
                "error": ("central Postgres is in use — take the backup with pg_dump "
                          "(documented runbook path); the API will not copy a live "
                          "postgres socket into a file")}
    # WAL checkpoint makes the main DB file self-consistent before copying
    from ..db import get_engine

    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
        await conn.commit()
    db_path = os.path.abspath(s.db_url.split("///", 1)[-1])
    backups_dir = os.path.join(s.data_dir, "backups")
    os.makedirs(backups_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(backups_dir, f"rice-{stamp}.db")
    shutil.copy2(db_path, dest)
    # retention
    files = sorted(f for f in os.listdir(backups_dir) if f.endswith(".db"))
    for old in files[:-MAX_BACKUPS]:
        try:
            os.remove(os.path.join(backups_dir, old))
        except OSError:
            pass
    log.info("backup written: %s (%d KB)", dest, os.path.getsize(dest) // 1024)
    return {"ok": True, "path": os.path.relpath(dest, s.data_dir),
            "bytes": os.path.getsize(dest), "kept": min(len(files), MAX_BACKUPS)}


def list_backups() -> list[dict]:
    s = get_settings()
    backups_dir = os.path.join(s.data_dir, "backups")
    if not os.path.isdir(backups_dir):
        return []
    out = []
    for f in sorted(os.listdir(backups_dir), reverse=True):
        if not f.endswith(".db"):
            continue
        p = os.path.join(backups_dir, f)
        out.append({"name": f, "path": os.path.relpath(p, s.data_dir),
                    "bytes": os.path.getsize(p),
                    "modified": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(p)))})
    return out


# ---------------------------------------------------------------- export / import

async def dump_project(project_id: str) -> dict:
    """Collect the project's rows into a versioned bundle."""
    async with session_scope() as s:
        p = (await s.execute(select(Project).where(Project.id == project_id))).scalars().first()
        if p is None:
            raise ValueError("project not found")
        sources = (await s.execute(select(Source).where(Source.project_id == project_id))).scalars().all()
        pages = (await s.execute(select(PageRecord).where(PageRecord.project_id == project_id))).scalars().all()
        features = (await s.execute(select(Feature).where(Feature.project_id == project_id))).scalars().all()
        evidence = (await s.execute(select(Evidence).where(Evidence.project_id == project_id))).scalars().all()
        observations = (await s.execute(select(Observation).where(Observation.project_id == project_id))).scalars().all()
        questions = (await s.execute(select(UnresolvedQuestion).where(UnresolvedQuestion.project_id == project_id))).scalars().all()
        scopes = (await s.execute(select(CollectionScope).where(CollectionScope.project_id == project_id))).scalars().all()
        assets = (await s.execute(select(DataAsset).where(DataAsset.project_id == project_id))).scalars().all()
        reports = (await s.execute(select(Report).where(Report.project_id == project_id))).scalars().all()

        def rows(m, cols):
            return [{c: getattr(r, c) for c in cols} for r in m]

        # portable evidence references: normalise raw ids to positional
        # indices so the importing installation can remap onto fresh ids
        ev_id_list = [e.id for e in evidence]

        def pos(ids):
            return [ev_id_list.index(r) if r in ev_id_list else r for r in (ids or [])]

        pages_raw = rows(pages, ["url", "canonical_url", "title", "status", "content_category",
                                 "purpose", "summary", "structure", "body_text",
                                 "capture_method", "error", "evidence_ids"])
        feats_raw = rows(features, ["name", "category", "description", "purpose",
                                    "access_location", "limitations", "opportunities",
                                    "dependencies", "related_features", "confidence",
                                    "status", "evidence_ids"])
        obs_raw = rows(observations, ["kind", "observation", "key", "value",
                                      "evidence_ids", "evidence_class",
                                      "confidence", "status"])
        for r in pages_raw:
            r["evidence_ids"] = pos(r["evidence_ids"])
        for r in feats_raw:
            r["evidence_ids"] = pos(r["evidence_ids"])
        for r in obs_raw:
            r["evidence_ids"] = pos(r["evidence_ids"])

        return {
            "version": EXPORT_VERSION,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "project": _p(p),
            "sources": rows(sources, ["name", "url", "domain", "status", "notes"]),
            "pages": pages_raw,
            "features": feats_raw,
            "evidence": rows(evidence, ["ref_code", "evidence_class", "source_uri",
                                        "source_name", "capture_method", "description",
                                        "meta"]),
            "observations": obs_raw,
            "questions": rows(questions, ["question", "context", "status"]),
            "scopes": rows(scopes, ["domain", "allowed_methods", "min_delay_s",
                                    "max_pages", "robots_mode", "note"]),
            "data_assets": rows(assets, ["name", "filename", "format", "provenance",
                                         "license", "rows", "status", "error"]),
            "reports": rows(reports, ["type", "title", "format", "content"]),
        }


def _p(m: Project) -> dict:
    return {"name": m.name, "slug": m.slug, "description": m.description,
            "industry": m.industry, "target_base_url": m.target_base_url,
            "permissions": m.permissions or {}}


def _validate_bundle(bundle: dict) -> str | None:
    if not isinstance(bundle, dict):
        return "bundle is not a JSON object"
    if bundle.get("version") != EXPORT_VERSION:
        return f"unsupported bundle version {bundle.get('version')!r} (expected {EXPORT_VERSION})"
    p = bundle.get("project")
    if not isinstance(p, dict) or not p.get("name"):
        return "bundle.project.name is missing"
    for key in ("pages", "features", "evidence", "observations"):
        if not isinstance(bundle.get(key), list):
            return f"bundle.{key} must be a list"
    return None


async def import_project(bundle: dict, name_override: str = "") -> dict:
    """Create a new project from an exported bundle with fresh ids and
    remapped cross-references. Returns the new project id + counts."""
    err = _validate_bundle(bundle)
    if err:
        return {"ok": False, "error": err}
    src = bundle["project"]
    name = name_override or src["name"]
    pid = new_id()
    import hashlib

    slug = slugify_safe(name) + "-" + hashlib.sha1(f"{pid}{time.time()}".encode()).hexdigest()[:6]
    async with session_scope() as s:
        p = Project(id=pid, name=name, slug=slug, description=src.get("description", ""),
                    industry=src.get("industry", ""),
                    target_base_url=src.get("target_base_url", ""),
                    permissions=src.get("permissions") or {})
        s.add(p)
        await s.flush()

        # evidence first: bundle refs are positional indices in export order
        ev_ids: list[str] = []
        for e in bundle["evidence"]:
            eid = new_id()
            ev_ids.append(eid)
            s.add(Evidence(id=eid, project_id=pid, ref_code=e.get("ref_code", ""),
                           evidence_class=e.get("evidence_class", "I"),
                           source_uri=e.get("source_uri", ""),
                           source_name=e.get("source_name", ""),
                           capture_method=e.get("capture_method", "import"),
                           description=e.get("description", ""), meta=e.get("meta") or {}))
        await s.flush()

        def remap(ids) -> list:
            """Evidence refs in a bundle are positional (int index) or raw
            strings from the source install. Integers map onto the fresh ids;
            unknown strings are kept verbatim — no silent drop."""
            out = []
            for ref in ids or []:
                if isinstance(ref, int) and 0 <= ref < len(ev_ids):
                    out.append(ev_ids[ref])
                else:
                    out.append(ref)
            return out

        pg_ids: list[str] = []
        for pg in bundle["pages"]:
            gid = new_id()
            pg_ids.append(gid)
            s.add(PageRecord(id=gid, project_id=pid, url=pg.get("url", "")[:700],
                             canonical_url=(pg.get("canonical_url") or pg.get("url") or "")[:700],
                             title=pg.get("title", "")[:500], status=pg.get("status", "documented"),
                             content_category=pg.get("content_category", ""),
                             purpose=pg.get("purpose", ""), summary=pg.get("summary", ""),
                             structure=pg.get("structure") or {}, body_text=pg.get("body_text", ""),
                             capture_method=pg.get("capture_method", "imported_package"),
                             error=pg.get("error", ""), evidence_ids=remap(pg.get("evidence_ids") or [])))
        await s.flush()

        for f in bundle["features"]:
            fname = f.get("name", "unnamed")[:300]
            s.add(Feature(id=new_id(), project_id=pid, name=fname,
                          slug=slugify(fname),
                          category=f.get("category", "other"),
                          description=f.get("description", ""), purpose=f.get("purpose", ""),
                          access_location=f.get("access_location", ""),
                          limitations=f.get("limitations", ""),
                          opportunities=f.get("opportunities", ""),
                          dependencies=list(f.get("dependencies") or []),
                          related_features=list(f.get("related_features") or []),
                          confidence=f.get("confidence", 0.5), status=f.get("status", "documented"),
                          evidence_ids=remap(f.get("evidence_ids") or [])))
        for o in bundle["observations"]:
            s.add(Observation(project_id=pid, kind=o.get("kind", "note"),
                              observation=o.get("observation", ""),
                              key=o.get("key", ""), value=o.get("value", ""),
                              evidence_ids=remap(o.get("evidence_ids") or []),
                              evidence_class=o.get("evidence_class", "I"),
                              confidence=o.get("confidence", 0.5),
                              status=o.get("status", "open"), created_by="import"))
        for q in bundle["questions"]:
            s.add(UnresolvedQuestion(project_id=pid, question=q.get("question", ""),
                                     context=q.get("context", ""), status=q.get("status", "open")))
        for srcrow in bundle.get("sources", []):
            s.add(Source(project_id=pid, name=srcrow.get("name", ""),
                         url=srcrow.get("url", ""), domain=srcrow.get("domain", ""),
                         status=srcrow.get("status", "pending_approval"),
                         notes=srcrow.get("notes", "")))
        for sc in bundle.get("scopes", []):
            # robots exceptions never travel: they require local re-approval
            s.add(CollectionScope(project_id=pid, domain=sc.get("domain", "*"),
                                  allowed_methods=list(sc.get("allowed_methods") or []),
                                  min_delay_s=sc.get("min_delay_s", 2.0),
                                  max_pages=sc.get("max_pages", 40),
                                  robots_mode="respect", note=sc.get("note", "") + " (imported)"))
        for a in bundle.get("data_assets", []):
            s.add(DataAsset(project_id=pid, name=a.get("name", ""), filename=a.get("filename", ""),
                            format=a.get("format", ""), provenance=a.get("provenance", ""),
                            license=a.get("license", ""), rows=a.get("rows", 0),
                            status=a.get("status", "imported"), error=a.get("error", "")))
        for r in bundle.get("reports", []):
            s.add(Report(project_id=pid, type=r.get("type", ""), title=r.get("title", ""),
                         format=r.get("format", "md"), content=r.get("content", ""),
                         meta={"imported_from_bundle": True}))
        s.add(ActivityLog(project_id=pid, actor="import", action="project.imported",
                          subject=name,
                          detail=f"{len(bundle['pages'])} pages, {len(bundle['features'])} features, "
                                 f"{len(bundle['evidence'])} evidence"))
        await s.commit()

    # rebuild knowledge entries for the imported project
    for f in bundle["features"]:
        await upsert_knowledge(pid, "feature", f"import:{f.get('name', '')[:40]}",
                               f"Feature: {f.get('name', '')}", f.get("description", "")[:4000])
    for pg in bundle["pages"]:
        await upsert_knowledge(pid, "page", f"import:{pg.get('url', '')[:60]}",
                               f"Page: {pg.get('title', '')}",
                               f"{pg.get('url', '')} {pg.get('body_text', '')[:4000]}")
    return {"ok": True, "project_id": pid,
            "counts": {"pages": len(bundle["pages"]), "features": len(bundle["features"]),
                       "evidence": len(bundle["evidence"]),
                       "observations": len(bundle["observations"])}}


def slugify_safe(name: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", (name or "project").lower()).strip("-")[:48] or "project"
