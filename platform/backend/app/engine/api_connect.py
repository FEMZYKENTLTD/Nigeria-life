"""Official API connectors.

Calls a target site's or data provider's **official API** using the
researcher's own credentials. Credential hygiene:

* the database stores the environment variable **name** only
  (``env_var``), never a value;
* the value is read from the host environment at call time;
* anything that looks like the credential is never written into
  observations, evidence, logs or reports (checked before persisting).

New connectors start ``pending_approval`` and only become ``active`` after a
human approves the ``new_source`` decision — same gate as any third-party
source.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from ..db import session_scope
from ..github_int.client import sanitize
from ..models import ActivityLog, ApiConnector, Evidence, Observation, Project
from .ids import new_id
from .knowledge import upsert_knowledge
from .robots import USER_AGENT

log = logging.getLogger("rice.apiconn")

ENV_VAR_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
ROW_CAP = 500          # max rows persisted per sync (documented cap)
KB_CAP = 100           # max knowledge upserts per sync
BETWEEN_CALLS_S = 1.5  # politeness delay between endpoint calls


def validate_connector(name: str, base_url: str, auth_type: str, env_var: str,
                       key_header: str, endpoints: list) -> str | None:
    """Return an error string, or None when the definition is sound."""
    if not name or not name.strip():
        return "connector name is required"
    if not re.match(r"^https?://", base_url or ""):
        return "base_url must be an http(s) URL"
    if auth_type not in ("none", "bearer", "key"):
        return "auth_type must be none|bearer|key"
    if auth_type != "none" and not ENV_VAR_RE.match(env_var or ""):
        return "env_var must be an uppercase environment variable name (the credential value is never stored)"
    if auth_type == "none" and env_var:
        return "env_var must be empty when auth_type is none"
    if not endpoints:
        return "at least one endpoint {name, path} is required"
    for ep in endpoints:
        if not ep.get("name") or not str(ep.get("path", "")).startswith("/"):
            return "every endpoint needs a name and a path starting with /"
    return None


async def _credential_headers(c: ApiConnector) -> tuple[dict, str]:
    if c.auth_type == "none":
        return {}, ""
    value = os.environ.get(c.env_var, "")
    if not value:
        raise RuntimeError(
            f"credential env var {c.env_var} is not set in the host environment. "
            "Set it there — the platform never stores credential values."
        )
    if c.auth_type == "bearer":
        return {"Authorization": f"Bearer {value}"}, value
    return {c.key_header or "X-API-Key": value}, value


def _flatten(data) -> list:
    """Best-effort: turn a JSON payload into a list of row dicts (no deep
    magic — documented list containers first, then the payload itself)."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("results", "data", "rows", "items", "records"):
            v = data.get(key)
            if isinstance(v, list):
                return v
        return [data]
    return [data]


def _row_text(row, cap: int = 500) -> str:
    if isinstance(row, dict):
        parts = []
        for k, v in row.items():
            if v is None:
                continue
            parts.append(f"{k}: {str(v)[:200]}")
            if sum(len(p) for p in parts) > cap:
                break
        return " | ".join(parts)[:cap]
    return str(row)[:cap]


async def _mark_state(connector_id: str, status: str, error: str = "", last_sync: dict | None = None) -> None:
    async with session_scope() as s:
        c = (await s.execute(select(ApiConnector).where(ApiConnector.id == connector_id))).scalars().first()
        if c is None:
            return
        c.status = status
        c.error = error[:2000]
        if last_sync is not None:
            c.last_sync = last_sync
        if status == "active":
            c.last_sync_at = datetime.now(timezone.utc).isoformat()
        await s.commit()


async def sync_connector(connector_id: str) -> dict:
    """Call every configured endpoint (with politeness delay + the
    researcher's own credentials) and ingest rows as observations linked to
    one evidence item per endpoint. Honest failures: connector → error with
    the reason; nothing is invented."""
    async with session_scope() as s:
        c = (await s.execute(select(ApiConnector).where(ApiConnector.id == connector_id))).scalars().first()
    if c is None:
        return {"ok": False, "error": "connector not found"}
    if c.status != "active":
        return {"ok": False, "error": f"connector is {c.status} — approval required before use"}

    try:
        headers, secret = await _credential_headers(c)
    except RuntimeError as e:
        await _mark_state(c.id, "error", str(e))
        return {"ok": False, "error": str(e)}

    total_rows = 0
    total_obs = 0
    per_endpoint: list[dict] = []

    async with httpx.AsyncClient(
        timeout=30, follow_redirects=True,
        headers={"User-Agent": USER_AGENT, **headers},
    ) as client:
        for i, ep in enumerate(c.endpoints or []):
            if i:
                await asyncio.sleep(BETWEEN_CALLS_S)
            name = ep.get("name", f"ep{i}")
            url = c.base_url.rstrip("/") + str(ep.get("path", ""))
            try:
                r = await client.request(ep.get("method", "GET"), url)
            except Exception as e:
                msg = f"endpoint '{name}' failed: {e.__class__.__name__}: {e}"
                await _mark_state(c.id, "error", msg)
                return {"ok": False, "error": msg}
            if r.status_code >= 400:
                msg = f"endpoint '{name}' responded HTTP {r.status_code} (not bypassed; check scope/credentials with the provider)"
                await _mark_state(c.id, "error", msg)
                return {"ok": False, "error": msg}
            try:
                data = r.json()
            except Exception as e:
                msg = f"endpoint '{name}' returned non-JSON (HTTP {r.status_code})"
                await _mark_state(c.id, "error", msg)
                return {"ok": False, "error": msg}

            rows = _flatten(data)[:ROW_CAP]
            findings: list[str] = []
            for row in rows:
                text = sanitize(_row_text(row))
                # credential hygiene: if the secret leaked into the data,
                # refuse to persist it.
                if secret and secret in text:
                    msg = (f"endpoint '{name}' returned data containing the credential value — "
                           "import aborted to keep secrets out of research files")
                    await _mark_state(c.id, "error", msg)
                    return {"ok": False, "error": msg}
                findings.append(text)
                total_rows += 1

            ev = Evidence(
                id=new_id(), project_id=c.project_id, ref_code="",
                evidence_class="C", source_uri=url, source_name=c.name,
                capture_method="api_connector",
                description=f"Official API sync of '{name}': {len(findings)} record(s), "
                            f"HTTP {r.status_code}, {datetime.now(timezone.utc).isoformat()}",
                meta={"connector_id": c.id, "endpoint": name},
                captured_at=datetime.now(timezone.utc),
            )
            async with session_scope() as s:
                s.add(ev)
                await s.flush()
                evidence_id = ev.id
                for j, text in enumerate(findings[:ROW_CAP]):
                    s.add(Observation(
                        project_id=c.project_id, kind="fact",
                        observation=text, key=f"api:{name}", value="",
                        evidence_ids=[evidence_id], evidence_class="C",
                        confidence=0.75, status="open", created_by="import",
                    ))
                    total_obs += 1
                s.add(ActivityLog(project_id=c.project_id, actor="import",
                                  action="api_connector.sync", subject=c.name,
                                  detail=f"endpoint {name}: {len(findings)} rows"))
                await s.commit()
            for j, text in enumerate(findings[:KB_CAP]):
                await upsert_knowledge(c.project_id, "observation",
                                       f"{c.id}:{name}:{j}", f"API {name}", text)
            per_endpoint.append({"name": name, "rows": len(findings)})
            log.info("api connector %s endpoint %s: %d rows", c.id[:10], name, len(findings))

    await _mark_state(c.id, "active", "",
                      {"rows": total_rows, "observations": total_obs,
                       "endpoints": per_endpoint,
                       "at": datetime.now(timezone.utc).isoformat()})
    return {"ok": True, "rows": total_rows, "observations": total_obs,
            "endpoints": per_endpoint}
