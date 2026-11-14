import { useState } from "react";
import { api } from "../api";
import { Card, ErrorNote, Spinner, StatusPill, timeAgo, useFetch } from "../components/ui";

export default function Browsers({ pid }: { pid: string }) {
  const { data: health, error: e1, loading: l1, reload } = useFetch(
    () => api.browserHealth(false), []);
  const { data: profiles, loading: l2, reload: reloadProfiles } = useFetch(() => api.profiles(), []);
  const { data: sessions, error: e2, loading: l3 } = useFetch(
    () => api.sessions(pid), [pid]);
  const [name, setName] = useState("");
  const [engine, setEngine] = useState("chromium");
  const [busy, setBusy] = useState(false);

  if (e1 || e2) return <ErrorNote error={e1 || e2 || ""} />;
  if (l1 || l2 || l3) return <Spinner />;

  async function probe() {
    setBusy(true);
    try {
      await api.browserHealth(true);
      reload();
    } finally {
      setBusy(false);
    }
  }

  async function addProfile() {
    if (!name) return;
    setBusy(true);
    try {
      await api.createProfile({ name, engine, project_id: pid });
      setName("");
      reloadProfiles();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card title="Browser engines" action={
        <button className="btn" onClick={probe} disabled={busy}>{busy ? "Probing…" : "Re-probe health"}</button>
      }>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {(health || []).map((h) => (
            <div key={h.engine} className="rounded-xl border border-line bg-charcoal/50 p-4">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium capitalize text-white">{h.engine}</div>
                <StatusPill status={h.installed ? "active" : "denied"} />
              </div>
              <div className="mt-2 text-xs text-muted">
                {h.installed
                  ? `version ${h.version || "unknown"}`
                  : "not installed in this environment"}
              </div>
              {!h.installed && h.error && (
                <div className="mt-2 rounded-md border border-warn/20 bg-warn/5 p-2 text-[11px] leading-relaxed text-warn">
                  {h.error}
                </div>
              )}
            </div>
          ))}
        </div>
        <p className="mt-4 text-[11px] leading-relaxed text-faint">
          Health is probed by actually launching each engine headless. When binaries are absent the
          platform says so and research sessions degrade to the manual evidence import path —
          captures are recorded as failed with the reason, never silently dropped.
        </p>
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title={`Research profiles — ${profiles?.length ?? 0}`}>
          <div className="mb-4 flex gap-2">
            <input className="input" placeholder="Profile name"
              value={name} onChange={(e) => setName(e.target.value)} />
            <select className="input !w-36" value={engine} onChange={(e) => setEngine(e.target.value)}>
              <option>chromium</option>
              <option>firefox</option>
              <option>webkit</option>
            </select>
            <button className="btn btn-gold" disabled={busy || !name} onClick={addProfile}>Create</button>
          </div>
          <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
            {(profiles || []).map((p) => (
              <div key={p.id} className="rounded-lg border border-line bg-charcoal/40 p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-white">{p.name}</span>
                  <span className="badge border border-line bg-ink capitalize text-muted">{p.engine}</span>
                </div>
                <div className="mt-1 text-[11px] text-faint">
                  viewports: {p.viewports.map((v) => `${v.name} ${v.width}×${v.height}`).join(" · ")}
                </div>
              </div>
            ))}
            {(profiles || []).length === 0 && (
              <div className="text-sm text-muted">
                No profiles yet. Each profile is a separate browser user-data directory
                (separate cookies/sessions per project and purpose).
              </div>
            )}
          </div>
        </Card>

        <Card title={`Execution history — ${sessions?.length ?? 0} sessions`}>
          <div className="max-h-96 space-y-2 overflow-y-auto pr-1">
            {(sessions || []).map((s) => (
              <div key={s.id} className="rounded-lg border border-line bg-charcoal/40 p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-xs text-white">
                    <span className="badge border border-line bg-ink capitalize text-muted">{s.engine}</span>
                    <span className="capitalize text-faint">{s.mode}</span>
                  </div>
                  <StatusPill status={s.status} />
                </div>
                {s.error && <div className="mt-1 line-clamp-2 text-[11px] text-bad">{s.error}</div>}
                <div className="mt-1 text-[11px] text-faint">
                  started {timeAgo(s.started_at)} ·{" "}
                  {Number(s.summary?.pages_visited ?? 0)} page(s) · {Number(s.summary?.screenshots ?? 0)} screenshot(s)
                </div>
              </div>
            ))}
            {(sessions || []).length === 0 && (
              <div className="text-sm text-muted">
                No research sessions recorded for this project. Sessions run via
                <code className="mx-1 text-gold-soft">POST /api/projects/:id/captures</code>.
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
