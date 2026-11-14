import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { api } from "../api";
import { Card, ErrorNote, Kpi, Spinner, StatusPill, timeAgo, useFetch, fmtPct } from "../components/ui";

const GOLD = "#c9a227";

export default function Overview({ pid }: { pid: string }) {
  const { data, error, loading } = useFetch(() => api.overview(), []);
  const { data: analytics } = useFetch(
    () => (pid ? api.analytics(pid) : Promise.resolve(null as any)),
    [pid]
  );

  if (error) return <ErrorNote error={error} />;
  if (loading || !data) return <Spinner />;

  const t = data.totals;
  const conf = analytics?.confidence;
  const confData = conf
    ? Object.entries(conf.buckets).map(([name, value]) => ({ name, value }))
    : [];
  const rc = analytics?.research_completeness;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi label="Research projects" value={t.projects} sub={`${t.active_tasks ?? 0} active task(s)`} tone="gold" />
        <Kpi label="Pages documented" value={`${t.pages_documented}/${t.pages}`} sub="documented / known" />
        <Kpi label="Features identified" value={t.features} sub={`${t.observations} findings total`} />
        <Kpi label="Research sessions" value={t.sessions} sub={`${t.evidence} evidence items`} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card title="Research completeness" className="lg:col-span-1">
          {rc ? (
            <div>
              <div className="flex items-end gap-3">
                <div className="text-4xl font-semibold text-gold-soft">{fmtPct(rc.score, 0)}</div>
                <div className="pb-1 text-xs text-faint">of current objective coverage</div>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-charcoal">
                <div className="h-full bg-gold" style={{ width: `${Math.min(100, rc.score * 100)}%` }} />
              </div>
              <div className="mt-4 space-y-2">
                {Object.entries(rc.components).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between text-xs">
                    <span className="text-muted">{k.replace(/_/g, " ")}</span>
                    <span className="font-mono text-white">{fmtPct(v as number, 0)}</span>
                  </div>
                ))}
              </div>
              <p className="mt-4 text-[11px] leading-relaxed text-faint">{rc.explanation}</p>
            </div>
          ) : (
            <div className="text-sm text-muted">
              Select a project to compute completeness. Every score ships its formula.
            </div>
          )}
        </Card>

        <Card title="Confidence distribution (findings)">
          {confData.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={confData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={80}
                  stroke="none">
                  {confData.map((_, i) => (
                    <Cell key={i} fill={[GOLD, "#4a4a55", "#2b2b33"][i % 3]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-sm text-muted">No findings recorded yet.</div>
          )}
        </Card>

        <Card title="Recent activity">
          <div className="max-h-64 space-y-2 overflow-y-auto pr-1">
            {data.recent_activity.length === 0 && (
              <div className="text-sm text-muted">No activity yet.</div>
            )}
            {data.recent_activity.slice(0, 12).map((a) => (
              <div key={a.id} className="flex items-start gap-3 text-xs">
                <span className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${
                  a.actor === "agent" ? "bg-gold" : a.actor === "user" ? "bg-info" : "bg-faint"
                }`} />
                <div className="min-w-0">
                  <div className="truncate text-white">
                    <span className="text-muted">{a.action}</span> — {a.subject}
                  </div>
                  <div className="text-faint">{timeAgo(a.ts)}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card title="Active projects">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {data.projects.map((p) => (
            <div key={p.id} className="rounded-xl border border-line bg-charcoal/50 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-white">{p.name}</div>
                  <div className="mt-0.5 truncate text-xs text-faint">{p.target_base_url || "no target set"}</div>
                </div>
                <StatusPill status={p.status} />
              </div>
              {p.description && (
                <p className="mt-2 line-clamp-2 text-xs text-muted">{p.description}</p>
              )}
              <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-faint">
                <span>{p.counts?.pages_documented ?? 0}/{p.counts?.pages ?? 0} pages</span>
                <span>{p.counts?.features ?? 0} features</span>
                <span>{p.counts?.evidence ?? 0} evidence</span>
                <span>{p.counts?.active_tasks ?? 0} active tasks</span>
              </div>
            </div>
          ))}
          {data.projects.length === 0 && (
            <div className="text-sm text-muted">
              No projects yet. Create one via <code className="text-gold-soft">POST /api/projects</code>.
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

export const tooltipStyle = {
  background: "#17171e",
  border: "1px solid #26262f",
  borderRadius: 8,
  fontSize: 12,
  color: "#e8e6df",
};
