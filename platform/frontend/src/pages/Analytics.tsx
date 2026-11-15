import { useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";
import { Card, ErrorNote, Spinner, fmtPct, useFetch } from "../components/ui";
import { tooltipStyle } from "./Overview";

export default function Analytics({ pid }: { pid: string }) {
  const { data: a, error, loading, reload } = useFetch(
    () => (pid ? api.analytics(pid) : Promise.resolve(null as any)), [pid]);
  const [expanded, setExpanded] = useState<string | null>(null);

  const coverageData = useMemo(() => {
    if (!a) return [];
    return [
      { name: "page coverage", value: a.page_coverage.score * 100 },
      { name: "feature docs", value: a.feature_completeness.score * 100 },
      { name: "evidence quality", value: a.evidence_quality.score * 100 },
      { name: "completeness", value: a.research_completeness.score * 100 },
    ];
  }, [a]);

  const byCategory = useMemo(() => {
    if (!a) return [];
    // feature_completeness doesn't carry per-category counts; derive from
    // gaps/opportunities rows which include categories.
    const counts: Record<string, number> = {};
    for (const o of a.gaps_and_opportunities.opportunities) {
      counts[o.category] = (counts[o.category] || 0) + 1;
    }
    return Object.entries(counts)
      .map(([name, value]) => ({ name: name.replace(/_/g, " "), value }))
      .sort((x, y) => y.value - x.value)
      .slice(0, 12);
  }, [a]);

  if (error) return <ErrorNote error={error} />;
  if (loading || !a) return <Spinner />;

  const rc = a.research_completeness;
  const mi = a.missing_information;
  const cc = a.contradictions;
  const dd = a.duplicates;
  const go = a.gaps_and_opportunities;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title="Coverage & completeness" action={<button className="btn" onClick={reload}>↻ recompute</button>}>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={coverageData} margin={{ top: 8, right: 8, bottom: 8, left: -18 }}>
              <CartesianGrid stroke="#283453" vertical={false} />
              <XAxis dataKey="name" tick={{ fill: "#97a3c0", fontSize: 11 }} />
              <YAxis tick={{ fill: "#97a3c0", fontSize: 11 }} domain={[0, 100]} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {coverageData.map((_, i) => (
                  <Cell key={i} fill={i === 3 ? "#c17d4f" : "#1b2540"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <Explain text={rc.explanation} open={expanded === "rc"} toggle={() => setExpanded(expanded === "rc" ? null : "rc")} />
        </Card>

        <Card title="Feature categories (opportunity-scored)">
          {byCategory.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={byCategory} layout="vertical" margin={{ top: 4, right: 12, bottom: 4, left: 30 }}>
                <CartesianGrid stroke="#283453" horizontal={false} />
                <XAxis type="number" tick={{ fill: "#97a3c0", fontSize: 11 }} />
                <YAxis type="category" dataKey="name" width={110} tick={{ fill: "#97a3c0", fontSize: 11 }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="value" fill="#c17d4f" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-sm text-muted">No features to chart.</div>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Card title={`Contradictions — ${cc.count}`}>
          <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
            {cc.conflicts.map((c: any, i: number) => (
              <div key={i} className="rounded-lg border border-line bg-charcoal/40 p-3">
                <div className="text-sm text-white">{c.topic}</div>
                {c.values.map((v: any, j: number) => (
                  <div key={j} className="mt-1 text-[11px] text-muted">
                    <span className="text-gold-soft">value {j + 1}:</span> {v.value}
                    <span className="text-faint"> ({v.sources.length} source(s))</span>
                  </div>
                ))}
              </div>
            ))}
            {cc.count === 0 && <div className="text-sm text-muted">No field-level contradictions detected.</div>}
            <p className="mt-3 text-[11px] text-faint">{cc.explanation}</p>
          </div>
        </Card>

        <Card title={`Duplicates — ${dd.count} candidate pair(s)`}>
          <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
            {dd.candidates.map((c: any, i: number) => (
              <div key={i} className="rounded-lg border border-line bg-charcoal/40 p-3 text-xs">
                <div className="text-white">{c.a.name}</div>
                <div className="text-faint">↔</div>
                <div className="text-white">{c.b.name}</div>
                <div className="mt-1 text-[11px] text-gold-soft">similarity {c.similarity.toFixed(2)}</div>
              </div>
            ))}
            {dd.count === 0 && <div className="text-sm text-muted">No duplicate candidates.</div>}
            <p className="mt-3 text-[11px] text-faint">{dd.explanation}</p>
          </div>
        </Card>

        <Card title={`Missing information — ${mi.count} gap(s)`}>
          <div className="max-h-80 space-y-1.5 overflow-y-auto pr-1 text-[11px]">
            {mi.gaps.map((g: any, i: number) => (
              <div key={i} className="flex items-start gap-2">
                <span className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${g.severity === "major" ? "bg-bad" : "bg-warn"}`} />
                <span className="min-w-0 text-muted">
                  <span className="text-white">{g.kind.replace(/_/g, " ")}</span> · {g.subject}
                  <span className="text-faint"> — {g.gap}</span>
                </span>
              </div>
            ))}
            {mi.count === 0 && <div className="text-sm text-muted">No gaps recorded.</div>}
            <p className="mt-3 text-[11px] text-faint">{mi.explanation}</p>
          </div>
        </Card>
      </div>

      <Card title="Product opportunity ranking (formula in Analytics engine)">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-wider text-faint">
                <th className="py-2 pr-4">Feature</th>
                <th className="py-2 pr-4">Category</th>
                <th className="py-2 pr-4">Score</th>
                <th className="py-2 pr-4">Components (pressure / weak-evidence / category)</th>
                <th className="py-2">Noted opportunity</th>
              </tr>
            </thead>
            <tbody>
              {go.opportunities.slice(0, 25).map((o: any) => (
                <tr key={o.id || o.feature} className="border-b border-line/60">
                  <td className="py-2 pr-4 text-white">{o.feature}</td>
                  <td className="py-2 pr-4 text-muted">{o.category.replace(/_/g, " ")}</td>
                  <td className="py-2 pr-4 font-mono text-gold-soft">{o.score.toFixed(2)}</td>
                  <td className="py-2 pr-4 font-mono text-faint">
                    {o.components.limitation_pressure.toFixed(2)} / {o.components.evidence_weakness.toFixed(2)} / {o.components.category_weight.toFixed(1)}
                  </td>
                  <td className="py-2 text-muted">{o.opportunity_note || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-[11px] text-faint">{go.explanation}</p>
      </Card>
    </div>
  );
}

function Explain({ text, open, toggle }: { text: string; open: boolean; toggle: () => void }) {
  return (
    <div className="mt-2">
      <button className="text-[11px] text-gold-soft hover:underline" onClick={toggle}>
        {open ? "Hide calculation" : "Show calculation"}
      </button>
      {open && <p className="mt-2 text-[11px] leading-relaxed text-faint">{text}</p>}
    </div>
  );
}
