import { useState } from "react";
import { api, Connector, DataAsset, ScopeRow } from "../api";
import { Card, ErrorNote, Spinner, StatusPill, timeAgo, useFetch } from "../components/ui";

const METHODS = ["http", "browser", "manual", "api"] as const;

export default function Access({ pid }: { pid: string }) {
  if (!pid) return <div className="text-sm text-muted">Select or create a project first.</div>;
  return (
    <div className="space-y-6">
      <p className="text-xs leading-relaxed text-faint">
        Sanctioned collection only. The agent <span className="text-white">never bypasses</span> a
        restriction set here: a robots-disallowed URL, a disabled method or a missing credential
        parks the task on a human decision (AI Agent Centre) instead of working around it.
      </p>
      <ScopeSection pid={pid} />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ConnectorsSection pid={pid} />
        <AssetsSection pid={pid} />
      </div>
      <ManualQueueSection pid={pid} />
    </div>
  );
}

// ---------------------------------------------------------------- scope

function ScopeSection({ pid }: { pid: string }) {
  const { data, error, loading, reload } = useFetch(() => api.scope(pid), [pid]);
  const [form, setForm] = useState({ domain: "*", min_delay_s: 2, max_pages: 40, note: "" });
  const [methods, setMethods] = useState<string[]>(["http", "manual"]);
  const [robotsMode, setRobotsMode] = useState("respect");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  if (error) return <ErrorNote error={error} />;
  if (loading || !data) return <Card><Spinner /></Card>;

  async function save() {
    setBusy(true); setMsg("");
    try {
      const r = await api.upsertScope(pid, {
        domain: form.domain || "*",
        allowed_methods: methods,
        min_delay_s: Number(form.min_delay_s) || 0,
        max_pages: Number(form.max_pages) || 40,
        note: form.note,
        robots_mode: robotsMode,
      });
      setMsg(r.robots_exception_pending
        ? "Scope saved. A robots exception now requires approval — see AI Agent Centre."
        : "Scope saved.");
      reload();
    } catch (e: any) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title={`Collection scopes & politeness — ${data.length} row(s)`}>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-line text-[11px] uppercase tracking-wider text-faint">
              <th className="py-2 pr-4">Domain</th>
              <th className="py-2 pr-4">Methods</th>
              <th className="py-2 pr-4">Delay</th>
              <th className="py-2 pr-4">Page cap</th>
              <th className="py-2 pr-4">robots.txt</th>
              <th className="py-2">Note</th>
            </tr>
          </thead>
          <tbody>
            {data.map((s: ScopeRow) => (
              <tr key={s.id} className="border-b border-line/60">
                <td className="py-2 pr-4 font-mono text-white">{s.domain}</td>
                <td className="py-2 pr-4">
                  <div className="flex flex-wrap gap-1">
                    {s.allowed_methods.length
                      ? s.allowed_methods.map((m) => (
                        <span key={m} className="badge border border-line bg-ink text-muted">{m}</span>))
                      : <span className="text-warn">manual only (empty)</span>}
                  </div>
                </td>
                <td className="py-2 pr-4 font-mono text-muted">{s.min_delay_s}s</td>
                <td className="py-2 pr-4 font-mono text-muted">{s.max_pages}</td>
                <td className="py-2 pr-4">
                  {s.robots_mode === "approved_exception"
                    ? <StatusPill status="approved" />
                    : <span className="text-good">respect</span>}
                </td>
                <td className="py-2 text-muted">{s.note}</td>
              </tr>
            ))}
            {data.length === 0 && (
              <tr><td colSpan={6} className="py-3 text-muted">
                No scope rows — the project's default permissions apply. Add a row below to declare
                per-domain collection rules.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-6">
        <div>
          <label className="card-title">Domain ("*" = default)</label>
          <input className="input" value={form.domain}
            onChange={(e) => setForm({ ...form, domain: e.target.value })} />
        </div>
        <div>
          <label className="card-title">Methods</label>
          <div className="flex flex-wrap gap-2 pt-1">
            {METHODS.map((m) => (
              <label key={m} className="flex items-center gap-1 text-xs text-muted">
                <input type="checkbox" checked={methods.includes(m)}
                  onChange={() => setMethods(methods.includes(m)
                    ? methods.filter((x) => x !== m)
                    : [...methods, m])} />
                {m}
              </label>
            ))}
          </div>
        </div>
        <div>
          <label className="card-title">Min delay (s)</label>
          <input className="input" type="number" min={0} max={300}
            value={form.min_delay_s}
            onChange={(e) => setForm({ ...form, min_delay_s: Number(e.target.value) })} />
        </div>
        <div>
          <label className="card-title">Page cap</label>
          <input className="input" type="number" min={1} max={500}
            value={form.max_pages}
            onChange={(e) => setForm({ ...form, max_pages: Number(e.target.value) })} />
        </div>
        <div>
          <label className="card-title">robots.txt</label>
          <select className="input" value={robotsMode}
            onChange={(e) => setRobotsMode(e.target.value)}>
            <option value="respect">respect (default)</option>
            <option value="approved_exception">request exception…</option>
          </select>
        </div>
        <div className="flex items-end">
          <button className="btn btn-gold w-full" disabled={busy} onClick={save}>Save scope</button>
        </div>
      </div>
      {robotsMode === "approved_exception" && (
        <p className="mt-2 text-[11px] text-warn">
          Requesting an exception submits a permission-change decision. The exception only takes
          effect after a human approves it in the AI Agent Centre.
        </p>
      )}
      {msg && <p className="mt-2 text-xs text-muted">{msg}</p>}
    </Card>
  );
}

// ---------------------------------------------------------------- connectors

function ConnectorsSection({ pid }: { pid: string }) {
  const { data, error, loading, reload } = useFetch(() => api.connectors(pid), [pid]);
  const [form, setForm] = useState({
    name: "", base_url: "", auth_type: "none", env_var: "", key_header: "X-API-Key",
  });
  const [eps, setEps] = useState("items /v1/items");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [syncing, setSyncing] = useState("");

  if (error) return <Card><ErrorNote error={error} /></Card>;
  if (loading || !data) return <Card><Spinner /></Card>;

  async function register() {
    setBusy(true); setMsg("");
    try {
      const endpoints = eps.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
        const [name, ...rest] = l.split(/\s+/);
        return { name, path: rest.join(" ") || "/", method: "GET" };
      });
      const r = await api.createConnector(pid, { ...form, endpoints });
      setMsg(`Registered "${r.connector.name}" — pending approval (AI Agent Centre).`);
      setForm({ name: "", base_url: "", auth_type: "none", env_var: "", key_header: "X-API-Key" });
      reload();
    } catch (e: any) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function sync(c: Connector) {
    setSyncing(c.id); setMsg("");
    try {
      const r = await api.syncConnector(pid, c.id);
      setMsg(`Synced ${r.rows} row(s) → ${r.observations} finding(s).`);
      reload();
    } catch (e: any) {
      setMsg(String(e.message || e));
      reload();
    } finally {
      setSyncing("");
    }
  }

  return (
    <Card title={`Official API connectors — ${data.length}`}>
      <div className="space-y-2">
        {data.map((c) => (
          <div key={c.id} className="rounded-lg border border-line bg-charcoal/40 p-3">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <span className="text-sm text-white">{c.name}</span>
                <span className="ml-2 font-mono text-[11px] text-faint">{c.base_url}</span>
              </div>
              <div className="flex items-center gap-2">
                <StatusPill status={c.status} />
                <button className="btn" disabled={c.status !== "active" || syncing === c.id}
                  onClick={() => sync(c)}>
                  {syncing === c.id ? "Syncing…" : "Sync"}
                </button>
              </div>
            </div>
            <div className="mt-1 text-[11px] text-muted">
              auth: {c.auth_type}{c.auth_type !== "none" ? ` (env: ${c.env_var})` : ""} ·
              endpoints: {c.endpoints.map((e) => `${e.name}${e.path}`).join(", ")}
              {c.last_sync?.rows !== undefined && (
                <span className="text-good"> · last sync {c.last_sync.rows} row(s) {c.last_sync_at && `(${timeAgo(c.last_sync_at)})`}</span>
              )}
            </div>
            {c.error && <div className="mt-1 text-[11px] text-bad">{c.error}</div>}
          </div>
        ))}
        {data.length === 0 && (
          <div className="text-sm text-muted">
            No connectors. Register the target's official API below — it starts pending approval
            and uses <span className="text-white">your own credentials from the host environment</span>
            (env var name only; values are never stored or logged).
          </div>
        )}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-5">
        <input className="input" placeholder="Connector name"
          value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <input className="input" placeholder="https://api.example.com"
          value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} />
        <select className="input" value={form.auth_type}
          onChange={(e) => setForm({ ...form, auth_type: e.target.value })}>
          <option value="none">auth: none</option>
          <option value="bearer">auth: bearer</option>
          <option value="key">auth: api key</option>
        </select>
        {form.auth_type !== "none" && (
          <input className="input" placeholder="ENV_VAR_NAME"
            value={form.env_var} onChange={(e) => setForm({ ...form, env_var: e.target.value })} />
        )}
        <div className="flex items-end">
          <button className="btn btn-gold w-full" disabled={busy} onClick={register}>Register</button>
        </div>
      </div>
      <div className="mt-2">
        <label className="card-title">Endpoints (one per line: name path)</label>
        <textarea className="input" rows={2} value={eps} onChange={(e) => setEps(e.target.value)} />
      </div>
      {msg && <p className="mt-2 text-xs text-muted">{msg}</p>}
    </Card>
  );
}

// ---------------------------------------------------------------- data assets

function AssetsSection({ pid }: { pid: string }) {
  const { data, error, loading, reload } = useFetch(() => api.dataAssets(pid), [pid]);
  const [file, setFile] = useState<File | null>(null);
  const [meta, setMeta] = useState({ name: "", provenance: "", license: "", evidence_class: "S" });
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  if (error) return <Card><ErrorNote error={error} /></Card>;
  if (loading || !data) return <Card><Spinner /></Card>;

  async function doImport() {
    if (!file) { setMsg("Choose a file first (CSV / JSON / XML)."); return; }
    setBusy(true); setMsg("");
    try {
      const r = await api.importDataAsset(pid, file, meta);
      setMsg(`Imported ${r.rows} row(s) → ${r.observations} finding(s).`);
      setFile(null);
      setMeta({ name: "", provenance: "", license: "", evidence_class: "S" });
      reload();
    } catch (e: any) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title={`Licensed data assets — ${data.length}`}>
      <div className="space-y-2">
        {data.map((a: DataAsset) => (
          <div key={a.id} className="rounded-lg border border-line bg-charcoal/40 p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm text-white">{a.name || a.filename}</span>
              <div className="flex items-center gap-2">
                <span className="badge border border-line bg-ink font-mono text-muted">{a.format}</span>
                <StatusPill status={a.status} />
              </div>
            </div>
            <div className="mt-1 text-[11px] text-muted">
              {a.rows} row(s) · provenance: {a.provenance || "—"} · license: {a.license || "not stated"}
            </div>
            {a.error && <div className="mt-1 text-[11px] text-bad">{a.error}</div>}
          </div>
        ))}
        {data.length === 0 && (
          <div className="text-sm text-muted">
            No datasets imported. Upload data you lawfully hold (CSV / JSON / XML) with provenance
            and license — every row becomes a finding citing that evidence.
          </div>
        )}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <input className="input" placeholder="Dataset name"
          value={meta.name} onChange={(e) => setMeta({ ...meta, name: e.target.value })} />
        <input className="input" placeholder="Provenance (required — where from?)"
          value={meta.provenance} onChange={(e) => setMeta({ ...meta, provenance: e.target.value })} />
        <input className="input" placeholder="License (e.g. CC-BY 4.0)"
          value={meta.license} onChange={(e) => setMeta({ ...meta, license: e.target.value })} />
        <select className="input" value={meta.evidence_class}
          onChange={(e) => setMeta({ ...meta, evidence_class: e.target.value })}>
          <option value="C">class C — confirmed</option>
          <option value="S">class S — secondary</option>
          <option value="I">class I — inferred</option>
        </select>
      </div>
      <div className="mt-3 flex items-center gap-3">
        <input type="file" accept=".csv,.json,.xml"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          className="text-xs text-muted file:mr-2 file:rounded-lg file:border-0 file:bg-gold-dim/20 file:px-3 file:py-1.5 file:text-gold-soft" />
        <button className="btn btn-gold" disabled={busy} onClick={doImport}>
          {busy ? "Importing…" : "Import dataset"}
        </button>
      </div>
      {msg && <p className="mt-2 text-xs text-muted">{msg}</p>}
    </Card>
  );
}

// ---------------------------------------------------------------- manual queue

function ManualQueueSection({ pid }: { pid: string }) {
  const { data, error, loading, reload } = useFetch(() => api.manualQueue(pid), [pid]);
  const [cap, setCap] = useState({ url: "", title: "", notes: "", html: "" });
  const [shot, setShot] = useState<File | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [robotsUrl, setRobotsUrl] = useState("");
  const [robots, setRobots] = useState<{ status: string; detail: string } | null>(null);

  if (error) return <Card><ErrorNote error={error} /></Card>;
  if (loading || !data) return <Card><Spinner /></Card>;

  async function capture() {
    if (!cap.url) { setMsg("URL is required."); return; }
    setBusy(true); setMsg("");
    let b64 = "";
    if (shot) b64 = await new Promise<string>((res, rej) => {
      const fr = new FileReader();
      fr.onload = () => res(String(fr.result || ""));
      fr.onerror = () => rej(new Error("could not read file"));
      fr.readAsDataURL(shot);
    });
    try {
      await api.manualCapture(pid, { ...cap, screenshot_b64: b64 });
      setMsg(`Captured ${cap.url} as manual evidence.`);
      setCap({ url: "", title: "", notes: "", html: "" });
      setShot(null);
      reload();
    } catch (e: any) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function checkRobots() {
    if (!robotsUrl) return;
    try {
      setRobots(await api.robotsCheck(pid, robotsUrl));
    } catch (e: any) {
      setRobots({ status: "error", detail: String(e.message || e) });
    }
  }

  return (
    <Card title="Manual evidence — the sanctioned path for restricted sources">
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <div>
          <div className="card-title mb-2">
            Waiting on human capture — {data.pending_decisions.length} decision(s),
            {" "}{data.blocked_fetches.length} blocked fetch(es)
          </div>
          <div className="max-h-64 space-y-2 overflow-y-auto pr-1">
            {data.pending_decisions.map((d) => (
              <div key={d.id} className="rounded-lg border border-gold-dim/40 bg-gold-dim/5 p-3 text-xs">
                <div className="text-[10px] uppercase tracking-wider text-gold-soft">
                  manual evidence · {timeAgo(d.created_at)}
                </div>
                <div className="mt-1 line-clamp-3 text-white">{d.question}</div>
              </div>
            ))}
            {data.blocked_fetches.map((b) => (
              <div key={b.id} className="rounded-lg border border-line bg-charcoal/40 p-3 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate text-white">{b.description}</span>
                  <StatusPill status={b.status} />
                </div>
                {b.last_error && <div className="mt-1 line-clamp-2 text-faint">{b.last_error}</div>}
              </div>
            ))}
            {data.pending_decisions.length === 0 && data.blocked_fetches.length === 0 && (
              <div className="text-sm text-muted">
                Nothing is waiting on manual capture right now.
              </div>
            )}
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-faint">
            Approve/reject decisions in the AI Agent Centre. Submit the captured page below —
            it lands as confirmed manual evidence (class C) linked to the project.
          </p>
        </div>

        <div>
          <div className="card-title mb-2">Submit a manual capture</div>
          <div className="space-y-2">
            <input className="input" placeholder="Page URL (https://…)"
              value={cap.url} onChange={(e) => setCap({ ...cap, url: e.target.value })} />
            <input className="input" placeholder="Title"
              value={cap.title} onChange={(e) => setCap({ ...cap, title: e.target.value })} />
            <textarea className="input" rows={2} placeholder="Notes — what does this page show?"
              value={cap.notes} onChange={(e) => setCap({ ...cap, notes: e.target.value })} />
            <textarea className="input font-mono text-[11px]" rows={3}
              placeholder="Optional: page HTML (analysed by the page understanding engine)"
              value={cap.html} onChange={(e) => setCap({ ...cap, html: e.target.value })} />
            <div className="flex items-center gap-3">
              <input type="file" accept="image/png,image/jpeg"
                onChange={(e) => setShot(e.target.files?.[0] || null)}
                className="text-xs text-muted file:mr-2 file:rounded-lg file:border-0 file:bg-gold-dim/20 file:px-3 file:py-1.5 file:text-gold-soft" />
              <button className="btn btn-gold" disabled={busy} onClick={capture}>
                {busy ? "Saving…" : "Submit capture"}
              </button>
            </div>
          </div>

          <div className="mt-4 border-t border-line pt-4">
            <div className="card-title mb-2">robots.txt check (what the agent will do)</div>
            <div className="flex gap-2">
              <input className="input" placeholder="https://example.com/some-page"
                value={robotsUrl} onChange={(e) => setRobotsUrl(e.target.value)} />
              <button className="btn" onClick={checkRobots}>Check</button>
            </div>
            {robots && (
              <div className={`mt-2 rounded-lg border p-2 text-xs ${
                robots.status === "allowed" ? "border-good/30 bg-good/5 text-good"
                  : robots.status === "disallowed" ? "border-bad/30 bg-bad/5 text-bad"
                    : "border-line bg-charcoal/40 text-muted"}`}>
                <span className="font-semibold uppercase">{robots.status}</span> — {robots.detail}
              </div>
            )}
          </div>
          {msg && <p className="mt-2 text-xs text-muted">{msg}</p>}
        </div>
      </div>
    </Card>
  );
}
