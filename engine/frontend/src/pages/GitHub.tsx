import { useState } from "react";
import { api, useData } from "../api";
import type { PageProps } from "../App";
import { Badge, Button, Card, Empty, Notice, PageTitle, Scroll, State, useAction } from "../ui";

export default function GitHub({ pid }: PageProps) {
  const g = useData<any>(`/projects/${pid}/github`, 15000);
  const kinds = useData<any>("/reports/kinds");
  const [f, setF] = useState({ branch: `nlie/reports-${new Date().toISOString().slice(0, 10)}`, kinds: ["executive", "evidence_register"], message: "Add generated research reports", push: false, open_pr: false });
  const act = useAction();
  const s = g.data;
  return (
    <>
      <PageTitle title="GitHub" sub="Reads the project repository freely. Any commit needs your approval and is made on a new branch; your checked-out files are not touched." />
      <State loading={g.loading} error={g.error}>
        {s && !s.connected && <Notice tone="warn">{s.reason} Set the project's repository path to connect it.</Notice>}
        {s?.connected && (
          <div className="grid lg:grid-cols-2 gap-5">
            <Card title="Repository">
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-[13px]">
                <dt className="text-mute">Repository</dt><dd>{s.slug || s.repo_url || "local only"}</dd>
                <dt className="text-mute">Branch</dt><dd className="font-mono text-xs">{s.branch} @ {s.head}</dd>
                <dt className="text-mute">Tracked files</dt><dd className="num">{s.tracked_files}</dd>
                <dt className="text-mute">Uncommitted changes</dt><dd className="num">{s.dirty_files} file(s)</dd>
                <dt className="text-mute">Top level</dt><dd>{s.top_level.join("  ")}</dd>
                <dt className="text-mute">Product code</dt><dd>{s.has_product_code ? "Present" : "None found (no src, app, apps, packages or game folder)"}</dd>
                <dt className="text-mute">Pull requests</dt><dd>{s.gh_cli ? "GitHub CLI available" : "GitHub CLI not installed: branches can be pushed, pull requests must be opened by hand"}</dd>
              </dl>
            </Card>
            <Card title={`Documentation gaps (${s.gaps.length})`}>
              <Scroll max={280}>{s.gaps.length ? <table><tbody>{s.gaps.map((x: any, i: number) => <tr key={i}><td className="font-mono text-xs">{x.path}</td><td><Badge>{x.issue}</Badge></td><td className="text-xs text-mute">{x.detail}</td></tr>)}</tbody></table> : <Empty>No gaps found against the expected documents.</Empty>}</Scroll>
            </Card>
            <Card title="Propose a commit of generated reports">
              <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); act.run(() => api(`/projects/${pid}/github/publish`, { body: f }), "Proposal created. Approve it in the Agent Centre to carry it out."); }}>
                <div><label htmlFor="g-branch">New branch name</label><input id="g-branch" required pattern="[A-Za-z0-9._/\-]{1,120}" value={f.branch} onChange={(e) => setF({ ...f, branch: e.target.value })} /></div>
                <fieldset><legend className="text-xs text-mute mb-1">Reports to include (written to docs/engine/generated/)</legend>
                  <div className="grid grid-cols-2 gap-1.5">{kinds.data && Object.entries(kinds.data.kinds).map(([k, v]) => <label key={k} className="flex items-center gap-1.5 !mb-0 !text-[13px] !text-bone"><input type="checkbox" checked={f.kinds.includes(k)} onChange={(e) => setF({ ...f, kinds: e.target.checked ? [...f.kinds, k] : f.kinds.filter((x) => x !== k) })} />{v as string}</label>)}</div>
                </fieldset>
                <div><label htmlFor="g-msg">Commit message</label><input id="g-msg" required value={f.message} onChange={(e) => setF({ ...f, message: e.target.value })} /></div>
                <label className="flex items-center gap-2 !text-[13px] !text-bone"><input type="checkbox" checked={f.push} onChange={(e) => setF({ ...f, push: e.target.checked, open_pr: e.target.checked && f.open_pr })} />Push the branch to GitHub</label>
                <label className="flex items-center gap-2 !text-[13px] !text-bone"><input type="checkbox" disabled={!f.push} checked={f.open_pr} onChange={(e) => setF({ ...f, open_pr: e.target.checked })} />Open a pull request</label>
                <Button type="submit" kind="primary" disabled={act.busy || !f.kinds.length}>Request approval</Button>
                {act.note}
              </form>
            </Card>
            <Card title="Recent commits">
              <Scroll max={300}><table><tbody>{s.recent_commits.map((c: any) => <tr key={c.sha}><td className="font-mono text-xs">{c.sha}</td><td className="text-xs text-mute whitespace-nowrap">{c.date}</td><td>{c.subject}</td></tr>)}</tbody></table></Scroll>
              <div className="mt-8 text-xs text-mute">{s.docs.length} Markdown documents tracked: {s.docs.slice(0, 30).join(", ")}{s.docs.length > 30 ? "…" : ""}</div>
            </Card>
          </div>
        )}
      </State>
    </>
  );
}
