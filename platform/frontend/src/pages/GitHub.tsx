import { useState } from "react";
import { api } from "../api";
import { Card, ErrorNote, Spinner, StatusPill, useFetch } from "../components/ui";

export default function GitHub({ pid }: { pid: string }) {
  const { data, error, loading, reload } = useFetch(() => api.githubStatus(), []);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  if (error) return <ErrorNote error={error} />;
  if (loading || !data) return <Spinner />;

  const info = data.info || {};

  async function sync() {
    setBusy(true);
    setMsg("");
    try {
      const r = await api.githubSync();
      setMsg(r.synced ? `Synced ${r.docs} research documents into the knowledge base.` : r.digest);
    } catch (e: any) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi label="Connection" value={data.connected ? "connected" : "not connected"}
          tone={data.connected ? "good" : "bad"} />
        <Kpi label="Local checkout" value={info.local_checkout ? "present" : "absent"} />
        <Kpi label="Research docs found" value={String(data.docs_tree?.length ?? 0)}
          sub={info.docs_dir || "docs/research"} />
        <Kpi label="Default branch" value={info.default_branch || "—"} />
      </div>

      <Card title="Remote repository" action={<button className="btn" onClick={sync} disabled={busy}>
        {busy ? "Syncing…" : "Sync research docs → knowledge base"}
      </button>}>
        <div className="grid grid-cols-1 gap-3 text-xs md:grid-cols-2">
          <Row k="Remote" v={info.remote || "not set"} />
          <Row k="Default branch" v={info.default_branch || "—"} />
          <Row k="Branches" v={(data.branches || []).join(", ") || "—"} />
          <Row k="Docs directory" v={info.docs_dir || "—"} />
          <Row k="Research README" v={info.research_readme || "—"} />
          <Row k="Investigation log" v={info.investigation_log || "—"} />
        </div>
        {msg && <div className="mt-3 text-xs text-gold-soft">{msg}</div>}
        <p className="mt-4 text-[11px] leading-relaxed text-faint">
          Before any new investigation, the agent reads the research README and the
          investigation log from the repo and notes what was already done. Reads use the local
          checkout first; writes (branch + PR, <code>docs/**</code> only) always require an
          approved repository change decision.
        </p>
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title="Recent commits">
          <div className="max-h-96 space-y-2 overflow-y-auto pr-1">
            {(data.commits || []).map((c) => (
              <div key={c.sha} className="rounded-lg border border-line bg-charcoal/40 p-3">
                <div className="flex items-center justify-between gap-2 text-[11px]">
                  <span className="font-mono text-gold-soft">{c.sha.slice(0, 10)}</span>
                  <span className="text-faint">{c.date}</span>
                </div>
                <div className="mt-1 line-clamp-2 text-xs text-white">{c.message}</div>
                <div className="mt-0.5 text-[11px] text-faint">{c.author}</div>
              </div>
            ))}
            {(data.commits || []).length === 0 && (
              <div className="text-sm text-muted">
                No commit history readable. Set <code className="text-gold-soft">RICE_GITHUB_REPO</code>{" "}
                or connect a local checkout to enable read-back.
              </div>
            )}
          </div>
        </Card>

        <Card title="Research package in repository">
          <div className="max-h-96 space-y-1.5 overflow-y-auto pr-1 font-mono text-[11px]">
            {(data.docs_tree || []).map((f) => (
              <div key={f.path} className="flex items-center justify-between gap-3 rounded-md bg-charcoal/40 px-3 py-1.5">
                <span className="min-w-0 truncate text-muted">{f.path.replace(/^docs\/research\//, "")}</span>
                <span className="shrink-0 text-faint">{(f.size / 1024).toFixed(1)} KB</span>
              </div>
            ))}
            {(data.docs_tree || []).length === 0 && (
              <div className="text-sm text-muted">No docs tree available.</div>
            )}
          </div>
        </Card>
      </div>

      <Card title="Write-back policy (enforced by the engine)">
        <ul className="grid grid-cols-1 gap-2 text-xs text-muted md:grid-cols-2">
          <li>• Branch + pull request only — never direct push to the default branch.</li>
          <li>• File scope restricted to <code className="text-gold-soft">docs/**</code>.</li>
          <li>• Every consequential change requires an approved decision first.</li>
          <li>• Secret scanning — tokens or keys in generated content abort the write.</li>
          <li>• Existing repo work is never overwritten blindly (version check first).</li>
          <li>• The investigation log is read before any new investigation starts.</li>
        </ul>
      </Card>
    </div>
  );
}

function Kpi({ label, value, sub, tone = "default" }: {
  label: string; value: string; sub?: string; tone?: "default" | "good" | "bad";
}) {
  const cls = { default: "text-white", good: "text-good", bad: "text-bad" }[tone];
  return (
    <div className="card p-4">
      <div className="card-title">{label}</div>
      <div className={`mt-1 text-xl font-semibold ${cls}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-faint">{sub}</div>}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="rounded-lg border border-line bg-charcoal/40 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-faint">{k}</div>
      <div className="mt-0.5 truncate text-white" title={v}>{v || "—"}</div>
    </div>
  );
}
