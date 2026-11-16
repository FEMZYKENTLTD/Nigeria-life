import { useState } from "react";
import { api } from "../api";
import { Card, ErrorNote, Spinner, StatusPill, useFetch } from "../components/ui";

interface UserRow {
  id: string;
  email: string;
  display_name: string;
  role: string;
  created_at: string;
  last_seen_at: string;
  counts: Record<string, number>;
}

function ago(iso: string): string {
  if (!iso) return "—";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function Users() {
  const { data, loading, error, reload } = useFetch(() => api.users(), []);
  const [selected, setSelected] = useState<string>("");
  const [roleBusy, setRoleBusy] = useState<string>("");

  if (loading) return <Spinner />;
  if (error) return <ErrorNote error={error} />;
  if (!data) return null;

  async function toggleRole(u: UserRow) {
    const next = u.role === "admin" ? "member" : "admin";
    const msg =
      next === "admin"
        ? `Promote ${u.email} to admin? They will be able to see every user's projects, scraping and results.`
        : `Demote ${u.email} to member? They will only see their own projects.`;
    if (!window.confirm(msg)) return;
    setRoleBusy(u.id);
    try {
      await api.setUserRole(u.id, next);
      reload();
    } finally {
      setRoleBusy("");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="max-w-3xl text-xs leading-relaxed text-faint">
          Everyone using the platform, and the kind of scraping each of them is doing —
          project volume, captured pages, evidence gathered and task outcomes. Open a user to
          see exactly what they are scraping and what they are getting.
        </p>
        <button className="btn" onClick={reload}>↻ Refresh</button>
      </div>

      <Card title={`Registered users · ${data.total}`}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-[0.12em] text-faint">
                <th className="pb-2 pr-4">User</th>
                <th className="pb-2 pr-4">Role</th>
                <th className="pb-2 pr-4">Last seen</th>
                <th className="pb-2 pr-4 text-right">Projects</th>
                <th className="pb-2 pr-4 text-right">Tasks</th>
                <th className="pb-2 pr-4 text-right">Pages</th>
                <th className="pb-2 pr-4 text-right">Evidence</th>
                <th className="pb-2 pr-4 text-right">Sessions</th>
                <th className="pb-2"></th>
              </tr>
            </thead>
            <tbody>
              {data.users.map((u) => (
                <tr
                  key={u.id}
                  className={`cursor-pointer border-t border-line/60 transition hover:bg-panel2/40 ${
                    selected === u.id ? "bg-panel2/60" : ""
                  }`}
                  onClick={() => setSelected(selected === u.id ? "" : u.id)}
                >
                  <td className="py-2.5 pr-4">
                    <div className="font-medium text-white">{u.display_name || u.email}</div>
                    <div className="text-[11px] text-faint">{u.email}</div>
                  </td>
                  <td className="py-2.5 pr-4">
                    <span
                      className={`badge border ${
                        u.role === "admin"
                          ? "border-gold-dim/50 bg-gold-dim/10 text-gold-soft"
                          : "border-line bg-muted/10 text-muted"
                      }`}
                    >
                      {u.role}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4 text-[12px] text-muted">{ago(u.last_seen_at)}</td>
                  {(["projects", "tasks", "pages", "evidence", "sessions"] as const).map((k) => (
                    <td key={k} className="py-2.5 pr-4 text-right tabular-nums text-white">
                      {u.counts[k] ?? 0}
                    </td>
                  ))}
                  <td className="py-2.5 text-right">
                    <button
                      className="btn !px-2.5 !py-1 text-[12px]"
                      disabled={roleBusy === u.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleRole(u);
                      }}
                    >
                      {roleBusy === u.id
                        ? "…"
                        : u.role === "admin"
                          ? "Demote"
                          : "Promote"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {selected && <UserDetail id={selected} />}
    </div>
  );
}

function UserDetail({ id }: { id: string }) {
  const { data, loading, error, reload } = useFetch(() => api.userDetail(id), [id]);
  if (loading) return <Spinner />;
  if (error) return <ErrorNote error={error} />;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-center gap-x-6 gap-y-1 px-5 py-3">
        <span className="text-sm font-semibold text-white">{data.user.display_name || data.user.email}</span>
        <span className="text-[12px] text-faint">{data.user.email}</span>
        <span className="text-[12px] text-muted">
          last seen {ago(data.user.last_seen_at)}
        </span>
        <button className="btn ml-auto !px-2.5 !py-1 text-[12px]" onClick={reload}>↻</button>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title={`What they are scraping · ${data.user.counts.pages ?? 0} pages captured`}>
          {data.recent_pages.length === 0 ? (
            <p className="text-[12px] text-faint">No pages captured yet.</p>
          ) : (
            <ul className="space-y-2">
              {data.recent_pages.map((p) => (
                <li key={p.id} className="rounded-lg border border-line/60 bg-charcoal/50 p-2.5">
                  <div className="truncate text-[13px] text-white" title={p.url}>
                    {p.url}
                  </div>
                  <div className="mt-1 flex items-center gap-2 text-[11px] text-faint">
                    <StatusPill status={p.status} />
                    <span>{p.capture_method || "—"}</span>
                    {p.browser_engine && <span>· {p.browser_engine}</span>}
                    <span>· {ago(p.observed_at)}</span>
                    {p.error && <span className="truncate text-bad" title={p.error}>{p.error}</span>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title={`What they are getting · ${data.user.counts.evidence ?? 0} evidence items`}>
          {data.recent_evidence.length === 0 ? (
            <p className="text-[12px] text-faint">No evidence captured yet.</p>
          ) : (
            <ul className="space-y-2">
              {data.recent_evidence.map((ev) => (
                <li key={ev.id} className="rounded-lg border border-line/60 bg-charcoal/50 p-2.5">
                  <div className="flex items-center gap-2">
                    <span className="badge border border-line bg-muted/10 text-muted">
                      class {ev.evidence_class}
                    </span>
                    {ev.ref_code && <span className="text-[11px] text-faint">{ev.ref_code}</span>}
                    <span className="truncate text-[13px] text-white">{ev.source_name || "—"} </span>
                    <span className="ml-auto text-[11px] text-faint">{ago(ev.created_at)}</span>
                  </div>
                  {ev.description && (
                    <p className="mt-1 line-clamp-2 text-[12px] leading-relaxed text-muted">
                      {ev.description}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title={`Research tasks · ${data.user.counts.tasks ?? 0} total`}>
          {data.recent_tasks.length === 0 ? (
            <p className="text-[12px] text-faint">No tasks yet.</p>
          ) : (
            <ul className="space-y-2">
              {data.recent_tasks.map((t) => (
                <li key={t.id} className="rounded-lg border border-line/60 bg-charcoal/50 p-2.5">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-[13px] text-white">{t.title}</span>
                    <span className="ml-auto">
                      <StatusPill status={t.status} />
                    </span>
                  </div>
                  {t.result_summary && (
                    <p className="mt-1 line-clamp-2 text-[12px] leading-relaxed text-muted">
                      {t.result_summary}
                    </p>
                  )}
                  {t.error && (
                    <p className="mt-1 truncate text-[12px] text-bad" title={t.error}>{t.error}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Recent activity">
          {data.recent_activity.length === 0 ? (
            <p className="text-[12px] text-faint">No recorded activity yet.</p>
          ) : (
            <ul className="space-y-1.5">
              {data.recent_activity.map((a, i) => (
                <li key={i} className="flex items-baseline gap-2 text-[12px]">
                  <span className="shrink-0 tabular-nums text-faint">{ago(a.ts)}</span>
                  <span className="shrink-0 text-muted">{a.actor}</span>
                  <span className="truncate text-white" title={`${a.action} ${a.subject}`}>
                    {a.action}
                    {a.subject ? ` — ${a.subject}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
