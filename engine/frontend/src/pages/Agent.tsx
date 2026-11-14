import { api, useData, when } from "../api";
import type { PageProps } from "../App";
import { Badge, Button, Card, Empty, Notice, PageTitle, Scroll, State, useAction } from "../ui";

export default function Agent({ pid, project, reloadProjects }: PageProps) {
  const agent = useData<any>(`/projects/${pid}/agent`, 3000);
  const tasks = useData<any[]>(`/projects/${pid}/tasks`, 3000);
  const act = useAction();
  const a = agent.data;
  const refresh = () => { agent.reload(); tasks.reload(); reloadProjects(); };
  const post = (path: string, ok: string, body?: unknown) => act.run(async () => { await api(path, { method: "POST", body }); refresh(); }, ok);

  return (
    <>
      <PageTitle title="Agent Centre" sub="What the agent is doing, what it plans next, and the decisions it is waiting on."
        action={<div className="flex gap-2">
          <Button kind="primary" disabled={act.busy} onClick={async () => {
            await act.run(async () => { const r = await api(`/projects/${pid}/plan`, { method: "POST" }); refresh(); if (!r.created.length) throw new Error(`Nothing new to queue. ${r.notes.join(" ")}`); }, "Next steps queued.");
          }}>Plan next steps</Button>
          {project.status === "active"
            ? <Button onClick={() => post(`/projects/${pid}/pause`, "Paused. Queued tasks are kept.")}>Pause</Button>
            : <Button onClick={() => post(`/projects/${pid}/resume`, "Resumed.")}>Resume</Button>}
        </div>} />
      <div className="mb-4">{act.note}</div>
      <State loading={agent.loading} error={agent.error}>
        {a && (
          <div className="grid lg:grid-cols-2 gap-5">
            <Card title="Current state">
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-[13px]">
                <dt className="text-mute">Objective</dt><dd>{a.objective || "None set"}</dd>
                <dt className="text-mute">State</dt><dd><Badge tone={a.state === "working" ? "running" : a.state}>{a.state}</Badge></dd>
                <dt className="text-mute">Current task</dt><dd>{a.current_task ?? "None running"}</dd>
                <dt className="text-mute">Tasks</dt><dd className="flex flex-wrap gap-1.5">{Object.entries(a.task_counts).map(([k, v]) => <Badge key={k} tone={k}>{`${v} ${k}`}</Badge>)}</dd>
                <dt className="text-mute">Reasoning mode</dt><dd>{a.ai.note}</dd>
              </dl>
            </Card>
            <Card title="Decisions waiting for you">
              {a.pending_decisions.length ? (
                <ul className="space-y-3">
                  {a.pending_decisions.map((d: any) => (
                    <li key={d.id} className="border border-line rounded p-3">
                      <div className="text-[13px]">{d.summary}</div>
                      <div className="text-xs text-mute mt-1">{d.action.replace(/_/g, " ")} · requested {when(d.created_at)}</div>
                      <div className="flex gap-2 mt-2">
                        <Button small kind="primary" disabled={act.busy} onClick={() => post(`/approvals/${d.id}/decide`, "Approved and carried out.", { approve: true })}>Approve</Button>
                        <Button small kind="danger" disabled={act.busy} onClick={() => post(`/approvals/${d.id}/decide`, "Rejected. Nothing was changed.", { approve: false })}>Reject</Button>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : <Empty>Nothing is waiting for approval.</Empty>}
            </Card>
            <Card title="Recommended next steps">
              {a.recommendations.length ? (
                <ul className="space-y-2.5 text-[13px]">{a.recommendations.map((r: any, i: number) => <li key={i}><div>{r.action}</div><div className="text-xs text-mute">Why: {r.basis}</div></li>)}</ul>
              ) : <Empty>No recommendations.</Empty>}
            </Card>
            <Card title="Is the objective covered?" action={<Badge tone={a.assessment.complete ? "ok" : "warn"}>{a.assessment.complete ? "complete" : "not complete"}</Badge>}>
              <p className="text-[13px] mb-2">{a.assessment.summary}</p>
              <ul className="text-[13px] space-y-1">{a.assessment.criteria.filter((c: any) => !c.met).map((c: any) => <li key={c.criterion} className="text-mute">○ {c.criterion} — {c.detail}</li>)}</ul>
            </Card>
            <Card title="Task queue" className="lg:col-span-2">
              <Scroll max={460}>
                {tasks.data?.length ? (
                  <table>
                    <thead><tr><th>#</th><th>Task</th><th>Status</th><th>Attempts</th><th>Outcome or reason</th><th></th></tr></thead>
                    <tbody>{tasks.data.map((t) => (
                      <tr key={t.id}>
                        <td className="num text-mute">{t.id}</td><td>{t.title}</td><td><Badge>{t.status}</Badge></td><td className="num">{t.attempts}/{t.max_attempts}</td>
                        <td className="text-xs text-mute max-w-[46ch]">{t.error ? t.error.split("\n")[0] : t.status === "done" ? Object.entries(t.result).filter(([, v]) => typeof v !== "object").map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(" · ") : ""}</td>
                        <td className="whitespace-nowrap">
                          {["queued", "running", "blocked"].includes(t.status) && <Button small kind="danger" onClick={() => post(`/tasks/${t.id}/cancel`, "Task cancelled.")}>Cancel</Button>}
                          {["failed", "blocked", "cancelled"].includes(t.status) && <> <Button small onClick={() => post(`/tasks/${t.id}/retry`, "Task queued again.")}>Retry</Button></>}
                        </td>
                      </tr>
                    ))}</tbody>
                  </table>
                ) : <Empty>No tasks yet. Use “Plan next steps”.</Empty>}
              </Scroll>
            </Card>
          </div>
        )}
      </State>
      {!a?.ai.model_configured && <div className="mt-5"><Notice>No language model is configured. Planning uses fixed rules and does not write prose analysis. Set NLIE_AI_BASE_URL and NLIE_AI_MODEL_SIMPLE to connect one.</Notice></div>}
    </>
  );
}
