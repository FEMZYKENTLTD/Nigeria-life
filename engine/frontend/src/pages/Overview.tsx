import { useState } from "react";
import { api, useData, when } from "../api";
import type { PageProps } from "../App";
import { Badge, Button, Card, Empty, PageTitle, Scroll, Stat, State, useAction } from "../ui";

export default function Overview({ pid, project, reloadProjects }: PageProps) {
  const health = useData<any>("/health", 10000);
  const projects = useData<any[]>("/projects", 5000);
  const an = useData<any>(pid ? `/projects/${pid}/analytics` : null, 8000);
  const agent = useData<any>(pid ? `/projects/${pid}/agent` : null, 5000);
  const activity = useData<any[]>(pid ? `/activity?project_id=${pid}&limit=25` : "/activity?limit=25", 5000);
  const findings = useData<any[]>(pid ? `/projects/${pid}/findings` : null, 8000);
  const [form, setForm] = useState({ name: "", objective: "", repo_path: "" });
  const act = useAction();
  const c = an.data?.counts;
  const asm = agent.data?.assessment;

  return (
    <>
      <PageTitle title="Overview" sub={project?.objective || "Create a project to begin."} />
      {pid > 0 && (
        <State loading={an.loading} error={an.error}>
          {c && (
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-5">
              <Stat label="Features" value={c.features} />
              <Stat label="Findings" value={c.findings} />
              <Stat label="Evidence items" value={c.evidence} />
              <Stat label="Pages known" value={Object.values(c.pages as Record<string, number>).reduce((a, b) => a + b, 0)} hint={Object.entries(c.pages).map(([k, v]) => `${v} ${k}`).join(" · ") || undefined} />
              <Stat label="Open questions" value={c.questions_open} />
            </div>
          )}
        </State>
      )}
      <div className="grid lg:grid-cols-2 gap-5">
        {asm && (
          <Card title="Project completeness" action={<span className="text-xs text-mute num">{asm.criteria_met} of {asm.criteria_total} criteria met</span>}>
            <div className="h-1.5 bg-slate rounded mb-3" role="progressbar" aria-valuemin={0} aria-valuemax={asm.criteria_total} aria-valuenow={asm.criteria_met} aria-label="Criteria met">
              <div className="h-full bg-gold rounded" style={{ width: `${(100 * asm.criteria_met) / asm.criteria_total}%` }} />
            </div>
            <ul className="space-y-1.5 text-[13px]">
              {asm.criteria.map((x: any) => (
                <li key={x.criterion} className="flex gap-2">
                  <span className={x.met ? "text-ok" : "text-warn"} aria-hidden>{x.met ? "✓" : "○"}</span>
                  <span><span className="sr-only">{x.met ? "Met: " : "Not met: "}</span>{x.criterion} <span className="text-mute">— {x.detail}</span></span>
                </li>
              ))}
            </ul>
          </Card>
        )}
        <Card title="System health">
          <State loading={health.loading} error={health.error}>
            {health.data && (
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-[13px]">
                <dt className="text-mute">Database</dt><dd>{health.data.database.kind} <Badge tone="ok">connected</Badge></dd>
                <dt className="text-mute">Background worker</dt><dd><Badge tone={health.data.worker_alive ? "ok" : "failed"}>{health.data.worker_alive ? "running" : "stopped"}</Badge></dd>
                <dt className="text-mute">Language model</dt><dd>{health.data.ai.model_configured ? health.data.ai.provider : "None configured — rule-based mode"}</dd>
                <dt className="text-mute">Browser engines</dt>
                <dd className="flex flex-wrap gap-1.5">{health.data.engines.map((e: any) => <Badge key={e.engine} tone={e.available ? "ok" : "missing"}>{`${e.engine}: ${e.available ? "ready" : "not installed"}`}</Badge>)}</dd>
                <dt className="text-mute">Version</dt><dd className="num">{health.data.version}</dd>
              </dl>
            )}
          </State>
        </Card>
        <Card title="Projects">
          <Scroll max={260}>
            <table>
              <thead><tr><th>Name</th><th>Status</th><th>Queued</th><th>Done</th><th>Failed</th><th>Blocked</th></tr></thead>
              <tbody>{projects.data?.map((p) => <tr key={p.id}><td>{p.name}</td><td><Badge>{p.status}</Badge></td><td className="num">{p.tasks.queued + p.tasks.running}</td><td className="num">{p.tasks.done}</td><td className="num">{p.tasks.failed}</td><td className="num">{p.tasks.blocked}</td></tr>)}</tbody>
            </table>
          </Scroll>
          <form className="grid sm:grid-cols-[1fr_1fr_auto] gap-2 items-end mt-8 pt-4 border-t border-line"
            onSubmit={(e) => { e.preventDefault(); act.run(async () => { await api("/projects", { body: form }); setForm({ name: "", objective: "", repo_path: "" }); reloadProjects(); projects.reload(); }, "Project created."); }}>
            <div><label htmlFor="np-name">New project name</label><input id="np-name" required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div><label htmlFor="np-obj">Objective</label><input id="np-obj" value={form.objective} onChange={(e) => setForm({ ...form, objective: e.target.value })} /></div>
            <Button type="submit" kind="primary" disabled={act.busy}>Create</Button>
          </form>
          <div className="mt-3">{act.note}</div>
        </Card>
        <Card title="Recent activity">
          <Scroll max={340}>
            {activity.data?.length ? (
              <table><tbody>{activity.data.map((a) => (
                <tr key={a.id}><td className="text-mute whitespace-nowrap text-xs">{when(a.ts)}</td><td><Badge tone={a.level}>{a.event}</Badge></td><td className="text-xs text-mute">{a.detail.title ?? a.detail.reason ?? a.detail.url ?? a.detail.summary ?? a.detail.error ?? ""}</td></tr>
              ))}</tbody></table>
            ) : <Empty>Nothing has happened yet.</Empty>}
          </Scroll>
        </Card>
        {pid > 0 && (
          <Card title="Latest findings" className="lg:col-span-2">
            <Scroll max={300}>
              {findings.data?.length ? (
                <table><thead><tr><th>ID</th><th>Observation</th><th>Confidence</th><th>Evidence</th><th>Recorded</th></tr></thead>
                  <tbody>{findings.data.slice(0, 15).map((f) => <tr key={f.id}><td className="font-mono text-xs whitespace-nowrap">{f.uid}</td><td>{f.observation}</td><td><Badge>{f.confidence}</Badge></td><td className="font-mono text-xs">{f.evidence_ref ?? "—"}</td><td className="text-xs text-mute whitespace-nowrap">{when(f.created_at)}</td></tr>)}</tbody></table>
              ) : <Empty>No findings recorded by the engine yet. Findings come from captured pages and from researcher-entered evidence.</Empty>}
            </Scroll>
          </Card>
        )}
      </div>
    </>
  );
}
