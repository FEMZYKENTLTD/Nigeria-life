import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useData } from "../api";
import type { PageProps } from "../App";
import { Card, Empty, PageTitle, Scroll, State } from "../ui";

const GOLD = "#c6a45c";
const tip = { contentStyle: { background: "#121214", border: "1px solid #29292e", borderRadius: 4, fontSize: 12 }, labelStyle: { color: "#ece7db" }, itemStyle: { color: GOLD }, cursor: { fill: "#1a1a1d" } };
const axis = { stroke: "#29292e", tick: { fill: "#9b968a", fontSize: 11 } };

function Bars({ data, x, y, height = 260 }: { data: any[]; x: string; y: string; height?: number }) {
  return (
    <div style={{ height }} role="img" aria-label={`Bar chart: ${data.map((d) => `${d[x]} ${d[y]}`).join(", ")}`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
          <CartesianGrid stroke="#1f1f23" horizontal={false} />
          <XAxis type="number" allowDecimals={false} {...axis} />
          <YAxis type="category" dataKey={x} width={150} interval={0} {...axis} />
          <Tooltip {...tip} />
          <Bar dataKey={y} fill={GOLD} radius={[0, 2, 2, 0]} barSize={10} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function Analytics({ pid }: PageProps) {
  const d = useData<any>(`/projects/${pid}/analytics`, 15000);
  const a = d.data;
  return (
    <>
      <PageTitle title="Analytics" sub="Each figure shows the formula and the counts behind it. Where there is nothing to count, no figure is shown." />
      <State loading={d.loading} error={d.error}>
        {a && (
          <div className="space-y-5">
            <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
              {a.metrics.map((m: any) => (
                <div key={m.name} className="bg-coal border border-line rounded-md p-4">
                  <div className="text-[11px] uppercase tracking-[0.1em] text-mute">{m.name}</div>
                  <div className="font-display text-3xl num mt-1">{m.value === null ? <span className="text-mute text-xl">No data</span> : <>{m.value}<span className="text-lg text-mute">{m.unit}</span></>}</div>
                  <div className="text-xs text-mute mt-2"><span className="text-golddim">How:</span> {m.formula}</div>
                  <div className="text-xs text-mute mt-1 num"><span className="text-golddim">Counts:</span> {Object.entries(m.inputs).map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`).join(" · ")}</div>
                  {m.note && <div className="text-xs text-mute mt-1"><span className="text-golddim">Limit:</span> {m.note}</div>}
                </div>
              ))}
            </div>
            <div className="grid lg:grid-cols-2 gap-5">
              <Card title="Features by category"><Bars data={a.features_by_category} x="category" y="count" height={470} /></Card>
              <div className="space-y-5">
                <Card title="Evidence by class"><Bars data={a.evidence_by_class} x="class" y="count" height={170} /></Card>
                <Card title="Features by weakest evidence class"><Bars data={a.feature_confidence} x="class" y="count" height={170} /></Card>
              </div>
              <Card title="Fields most often missing" className="lg:col-span-2"><Bars data={[...a.missing_fields].sort((p: any, q: any) => q.missing - p.missing).map((m: any) => ({ field: m.field.replace(/_/g, " "), missing: m.missing }))} x="field" y="missing" height={380} /></Card>
              <List title={`Gaps (${a.gaps.length})`} rows={a.gaps.map((g: any) => [g.gap, g.basis])} head={["Gap", "Basis"]} />
              <List title={`Recorded contradictions (${a.contradictions.length})`} rows={a.contradictions.map((c: any) => [c.text, c.status])} head={["Conflict", "Status"]} note={a.contradiction_note} />
              <List title={`Possible duplicates (${a.duplicates.length})`} rows={a.duplicates.map((x: any) => [x.a, x.b, x.similarity])} head={["Feature", "Feature", "Name overlap"]} note="Name overlap = shared words ÷ all words in both names. Pairs at 0.6 or above are listed for a person to check." />
              <List title="Most depended-on features" rows={a.dependencies.most_depended_on.map((x: any) => [x.feature, x.dependants])} head={["Feature", "Named as a dependency by"]} note={a.dependencies.note} />
              <List title={`Opportunities (${a.opportunities.length})`} rows={a.opportunities.map((o: any) => [o.feature, o.text, o.evidence.join(", ")])} head={["Feature", "Opportunity", "Evidence"]} note={a.opportunity_note} />
              <List title={`Page links (${a.journeys.edges.length})`} rows={a.journeys.edges.slice(0, 60).map((e: any) => [e.from, e.to])} head={["From", "To"]} note={a.journeys.note} />
            </div>
          </div>
        )}
      </State>
    </>
  );
}

function List({ title, head, rows, note }: { title: string; head: string[]; rows: any[][]; note?: string }) {
  return (
    <Card title={title}>
      {note && <p className="text-xs text-mute mb-3">{note}</p>}
      {rows.length ? <div className="mt-4"><Scroll max={300}><table><thead><tr>{head.map((h, i) => <th key={i}>{h}</th>)}</tr></thead><tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className={j ? "text-mute text-xs" : ""}>{c}</td>)}</tr>)}</tbody></table></Scroll></div> : <Empty>None recorded.</Empty>}
    </Card>
  );
}
