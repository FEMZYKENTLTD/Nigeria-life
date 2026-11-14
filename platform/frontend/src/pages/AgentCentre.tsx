import { useState } from "react";
import { api } from "../api";
import { Card, ErrorNote, Spinner, StatusPill, timeAgo, useFetch } from "../components/ui";

export default function AgentCentre({ pid }: { pid: string }) {
  const { data, error, loading, reload } = useFetch(() => api.agentStatus(), []);
  const { data: logs, reload: reloadLogs } = useFetch(() => api.agentLogs(80), []);
  const [msg, setMsg] = useState("");

  if (error) return <ErrorNote error={error} />;
  if (loading || !data) return <Spinner />;

  const all: { id: string; title: string; status: string; project_id: string }[] = [
    ...data.active_tasks.map((t) => ({ id: t.id, title: t.title, status: t.status, project_id: t.project_id })),
    ...data.queue.map((t) => ({ id: t.id, title: t.title, status: t.status, project_id: t.project_id })),
    ...data.failed.map((t) => ({ id: t.id, title: t.title, status: t.status, project_id: t.project_id })),
    ...data.complete.map((t) => ({ id: t.id, title: t.title, status: t.status, project_id: t.project_id })),
  ];
  const visible = pid ? all.filter((t) => t.project_id === pid) : all;

  async function decide(id: string, verdict: "approve" | "reject") {
    try {
      await api.decide(id, verdict);
      setMsg(`${verdict === "approve" ? "Approved" : "Rejected"} ${id.slice(0, 10)}…`);
      reload();
    } catch (e: any) {
      setMsg(String(e.message || e));
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="AI provider" value={data.ai_provider} sub={data.ai_provider === "off"
          ? "Running on deterministic offline logic — fully functional, no model required."
          : "Model-assisted planning/synthesis enabled."} />
        <Stat label="Active tasks" value={String(data.active_tasks.length)} />
        <Stat label="Waiting on decisions" value={String(data.pending_decisions.length)}
          tone={data.pending_decisions.length ? "warn" : "default"} />
        <Stat label="Queue / failed" value={`${data.queue.length} / ${data.failed.length}`} />
      </div>

      <Card title="Pending decisions (human approval required)"
        action={<button className="btn" onClick={() => { reload(); reloadLogs(); }}>↻ refresh</button>}>
        {data.pending_decisions.length === 0 ? (
          <div className="text-sm text-muted">
            Nothing awaits approval. Consequential actions (new sources, permission changes,
            publication, repository changes, destructive acts) always stop here.
          </div>
        ) : (
          <div className="space-y-3">
            {data.pending_decisions.map((d) => (
              <div key={d.id} className="rounded-xl border border-gold-dim/40 bg-gold-dim/5 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-[11px] uppercase tracking-wider text-gold-soft">
                      {d.kind.replace(/_/g, " ")}
                    </div>
                    <div className="mt-1 text-sm text-white">{d.question}</div>
                    <div className="mt-1 text-[11px] text-faint">raised {timeAgo(d.created_at)}</div>
                  </div>
                  <div className="flex gap-2">
                    <button className="btn btn-gold" onClick={() => decide(d.id, "approve")}>Approve</button>
                    <button className="btn btn-danger" onClick={() => decide(d.id, "reject")}>Reject</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
        {msg && <div className="mt-3 text-xs text-muted">{msg}</div>}
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title={`Task queue — ${visible.length}`}>
          <div className="max-h-96 space-y-2 overflow-y-auto pr-1">
            {visible.map((t) => (
              <div key={t.id} className="flex items-center justify-between gap-2 rounded-lg border border-line bg-charcoal/40 p-3">
                <div className="min-w-0">
                  <div className="truncate text-sm text-white">{t.title}</div>
                  <div className="text-[11px] text-faint">{t.id.slice(0, 14)}…</div>
                </div>
                <StatusPill status={t.status} />
              </div>
            ))}
            {visible.length === 0 && <div className="text-sm text-muted">No tasks in this project.</div>}
          </div>
        </Card>

        <Card title="Agent activity log">
          <div className="max-h-96 space-y-1.5 overflow-y-auto pr-1 font-mono text-[11px]">
            {(logs || []).map((l) => (
              <div key={l.ts + l.action} className="flex gap-3">
                <span className="shrink-0 text-faint">{new Date(l.ts).toLocaleTimeString()}</span>
                <span className="shrink-0 text-gold-soft">{l.action}</span>
                <span className="min-w-0 truncate text-muted" title={l.detail}>
                  {l.subject ? `${l.subject} — ` : ""}{l.detail}
                </span>
              </div>
            ))}
            {(logs || []).length === 0 && <div className="text-sm text-muted">No agent activity yet.</div>}
          </div>
        </Card>
      </div>

      <Card title="Recent agent runs">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          {data.recent_runs.map((r) => (
            <div key={r.id} className="flex items-center justify-between rounded-lg border border-line bg-charcoal/40 p-3 text-xs">
              <span className="text-muted">mode: <span className="text-white">{r.mode}</span></span>
              <StatusPill status={r.status} />
            </div>
          ))}
          {data.recent_runs.length === 0 && <div className="text-sm text-muted">No runs yet.</div>}
        </div>
      </Card>
    </div>
  );
}

function Stat({ label, value, sub, tone = "default" }: {
  label: string; value: string; sub?: string; tone?: "default" | "warn";
}) {
  return (
    <div className="card p-4">
      <div className="card-title">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${tone === "warn" ? "text-warn" : "text-white"}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-faint">{sub}</div>}
    </div>
  );
}
