import { useState } from "react";
import { api } from "../api";
import { Card, ErrorNote, Spinner, StatusPill, useFetch } from "../components/ui";

export default function Workspace({ pid }: { pid: string }) {
  const { data: tasks, error: e1, loading: l1, reload } = useFetch(
    () => (pid ? api.tasks(pid) : Promise.resolve([])), [pid]);
  const { data: pages, error: e2, loading: l2 } = useFetch(
    () => (pid ? api.pages(pid) : Promise.resolve([])), [pid]);
  const { data: features, error: e3, loading: l3 } = useFetch(
    () => (pid ? api.features(pid) : Promise.resolve([])), [pid]);
  const { data: questions, loading: l4 } = useFetch(
    () => (pid ? api.questions(pid) : Promise.resolve([])), [pid]);
  const { data: sources, loading: l5 } = useFetch(
    () => (pid ? api.sources(pid) : Promise.resolve([])), [pid]);

  const [title, setTitle] = useState("");
  const [objective, setObjective] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  if (!pid) return <div className="text-sm text-muted">Select or create a project first.</div>;
  if (e1 || e2 || e3) return <ErrorNote error={e1 || e2 || e3 || ""} />;
  if (l1 || l2 || l3 || l4 || l5) return <Spinner />;

  const openQs = (questions || []).filter((q) => q.status === "open");

  async function createTask() {
    if (!title || !objective) { setMsg("Title and objective are required."); return; }
    setBusy(true);
    try {
      const t = await api.createTask(pid, { title, objective });
      await api.runTask(t.id);
      setMsg(`Task created and handed to the agent (${t.id.slice(0, 10)}…).`);
      setTitle(""); setObjective("");
      reload();
    } catch (e: any) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card title="New research objective">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <input className="input" placeholder="Task title"
            value={title} onChange={(e) => setTitle(e.target.value)} />
          <input className="input md:col-span-2" placeholder="Objective — what should the agent investigate?"
            value={objective} onChange={(e) => setObjective(e.target.value)} />
        </div>
        <div className="mt-3 flex items-center gap-3">
          <button className="btn btn-gold" disabled={busy} onClick={createTask}>
            {busy ? "Starting…" : "Plan & run with agent"}
          </button>
          {msg && <span className="text-xs text-muted">{msg}</span>}
        </div>
      </Card>

      <Card title={`Investigation queue — ${tasks?.length ?? 0} tasks`}>
        <div className="space-y-3">
          {(tasks || []).map((t) => (
            <div key={t.id} className="rounded-xl border border-line bg-charcoal/50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-white">{t.title}</div>
                  <div className="mt-0.5 line-clamp-1 text-xs text-faint">{t.objective}</div>
                </div>
                <div className="flex items-center gap-2">
                  <StatusPill status={t.status} />
                  <button className="btn" onClick={async () => { await api.runTask(t.id); reload(); }}>Run</button>
                  <button className="btn" onClick={async () => { await api.pauseTask(t.id); reload(); }}>Pause</button>
                  <button className="btn btn-danger" onClick={async () => { await api.cancelTask(t.id); reload(); }}>Cancel</button>
                </div>
              </div>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-ink">
                <div className="h-full bg-gold" style={{ width: `${t.progress}%` }} />
              </div>
              {t.subtasks && t.subtasks.length > 0 && (
                <div className="mt-3 grid grid-cols-2 gap-1.5 md:grid-cols-4">
                  {t.subtasks.map((s) => (
                    <div key={s.id} className="flex items-center gap-2 rounded-md bg-ink/60 px-2 py-1 text-[11px]"
                      title={s.description}>
                      <StatusPill status={s.status} />
                      <span className="truncate text-muted">{s.type}</span>
                    </div>
                  ))}
                </div>
              )}
              {t.error && <div className="mt-2 text-xs text-bad">Failed: {t.error}</div>}
              {t.result_summary && t.status === "complete" && (
                <div className="mt-2 text-xs text-good">{t.result_summary}</div>
              )}
            </div>
          ))}
          {(tasks || []).length === 0 && (
            <div className="text-sm text-muted">No research tasks yet.</div>
          )}
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title={`Page inventory — ${pages?.length ?? 0}`}>
          <div className="max-h-96 space-y-2 overflow-y-auto pr-1">
            {(pages || []).map((p) => (
              <div key={p.id} className="rounded-lg border border-line bg-charcoal/40 p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0 truncate font-mono text-xs text-white">{p.url}</div>
                  <StatusPill status={p.status} />
                </div>
                <div className="mt-1 line-clamp-1 text-[11px] text-muted">
                  {p.purpose || p.summary || p.error || "—"}
                </div>
              </div>
            ))}
            {(pages || []).length === 0 && <div className="text-sm text-muted">No pages recorded.</div>}
          </div>
        </Card>

        <Card title={`Feature inventory — ${features?.length ?? 0}`}>
          <div className="max-h-96 space-y-2 overflow-y-auto pr-1">
            {(features || []).map((f) => (
              <div key={f.id} className="rounded-lg border border-line bg-charcoal/40 p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <span className="text-sm text-white">{f.name}</span>
                    <span className="ml-2 badge border border-line bg-ink text-[10px] text-muted">
                      {f.category.replace(/_/g, " ")}
                    </span>
                  </div>
                  <StatusPill status={f.status} />
                </div>
                <div className="mt-1 line-clamp-2 text-[11px] text-muted">{f.description}</div>
              </div>
            ))}
            {(features || []).length === 0 && <div className="text-sm text-muted">No features documented.</div>}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title={`Outstanding questions — ${openQs.length} open`}>
          <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
            {openQs.map((q) => (
              <div key={q.id} className="rounded-lg border border-line bg-charcoal/40 p-3 text-xs">
                <div className="text-white">{q.question}</div>
                {q.context && <div className="mt-1 text-faint">{q.context}</div>}
              </div>
            ))}
            {openQs.length === 0 && <div className="text-sm text-muted">No open questions.</div>}
          </div>
        </Card>

        <Card title={`Sources & collection scope — ${sources?.length ?? 0}`}>
          <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
            {(sources || []).map((s) => (
              <div key={s.id} className="rounded-lg border border-line bg-charcoal/40 p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0 truncate font-mono text-xs text-white">{s.url}</div>
                  <StatusPill status={s.status} />
                </div>
                <div className="mt-1 line-clamp-2 text-[11px] text-muted">{s.notes}</div>
              </div>
            ))}
            {(sources || []).length === 0 && (
              <div className="text-sm text-muted">
                No sources registered. New sources start pending approval — the scheduler will not
                touch them until a human approves.
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
