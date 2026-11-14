import { useState } from "react";
import { api, useData, when } from "../api";
import type { PageProps } from "../App";
import { Button, Card, Empty, PageTitle, Scroll, State, useAction } from "../ui";

const FMT: Record<string, string> = { md: "Markdown", json: "JSON", csv: "CSV", html: "HTML", pdf: "PDF", mmd: "Mermaid" };

export default function Reports({ pid }: PageProps) {
  const kinds = useData<any>("/reports/kinds");
  const list = useData<any[]>(`/projects/${pid}/reports`);
  const [kind, setKind] = useState("executive");
  const [formats, setFormats] = useState<string[]>(["md", "pdf"]);
  const act = useAction();
  const allowed = (f: string) => f !== "mmd" || kind === "site_map";
  return (
    <>
      <PageTitle title="Reports" sub="Generated from the knowledge base as it stands. Every report carries its generation time, the investigation dates and the evidence IDs it cites." />
      <div className="grid xl:grid-cols-[380px_1fr] gap-5">
        <Card title="Generate a report">
          <State loading={kinds.loading} error={kinds.error}>
            <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); act.run(async () => { await api(`/projects/${pid}/reports`, { body: { kind, formats: formats.filter(allowed) } }); list.reload(); }, "Report generated."); }}>
              <div><label htmlFor="r-kind">Report</label><select id="r-kind" value={kind} onChange={(e) => setKind(e.target.value)}>{kinds.data && Object.entries(kinds.data.kinds).map(([k, v]) => <option key={k} value={k}>{v as string}</option>)}</select></div>
              <fieldset><legend className="text-xs text-mute mb-1">Formats</legend>
                <div className="grid grid-cols-3 gap-1.5">{Object.entries(FMT).map(([f, name]) => (
                  <label key={f} className={`flex items-center gap-1.5 !mb-0 !text-[13px] ${allowed(f) ? "!text-bone" : "opacity-40"}`}><input type="checkbox" disabled={!allowed(f)} checked={formats.includes(f) && allowed(f)} onChange={(e) => setFormats(e.target.checked ? [...formats, f] : formats.filter((x) => x !== f))} />{name}</label>
                ))}</div>
                <p className="text-xs text-mute mt-2">Mermaid is available for the site map diagram only.</p>
              </fieldset>
              <Button type="submit" kind="primary" disabled={act.busy || !formats.filter(allowed).length}>{act.busy ? "Generating…" : "Generate"}</Button>
              {act.note}
            </form>
          </State>
        </Card>
        <Card title="Generated reports">
          <State loading={list.loading} error={list.error}>
            <Scroll max={560}>
              {list.data?.length ? (
                <table><thead><tr><th>Report</th><th>Format</th><th>Generated</th><th></th></tr></thead>
                  <tbody>{list.data.map((r) => <tr key={r.id}><td>{r.title}<div className="text-xs text-mute font-mono">{r.path}</div></td><td>{FMT[r.format]}</td><td className="text-xs text-mute whitespace-nowrap">{when(r.created_at)}</td>
                    <td>{r.exists ? <a className="text-gold hover:underline text-[13px]" href={`/api/reports/${r.id}/download`}>Download</a> : <span className="text-mute text-xs">File removed</span>}</td></tr>)}</tbody></table>
              ) : <Empty>No reports generated yet.</Empty>}
            </Scroll>
          </State>
        </Card>
      </div>
    </>
  );
}
