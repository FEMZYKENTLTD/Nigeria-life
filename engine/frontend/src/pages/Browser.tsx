import { useState } from "react";
import { api, useData, when } from "../api";
import type { PageProps } from "../App";
import { Badge, Button, Card, Empty, Notice, PageTitle, Scroll, State, useAction } from "../ui";

export default function Browser({ pid }: PageProps) {
  const b = useData<any>(`/browser?project_id=${pid}`, 5000);
  const sources = useData<any[]>(`/projects/${pid}/sources`, 5000);
  const [cap, setCap] = useState({ url: "", profile: "" });
  const [prof, setProf] = useState({ name: "", engine: "chromium", viewport_width: 1440, viewport_height: 900, mobile: false, headless: true, persistent: false });
  const [src, setSrc] = useState({ name: "", base_url: "", automation: "manual_only", max_pages: 25 });
  const capAct = useAction(), profAct = useAction(), srcAct = useAction();

  return (
    <>
      <PageTitle title="Browser Management" sub="Engines, profiles, sources and capture runs. Captures only run against sources a person has approved for automation." />
      <State loading={b.loading} error={b.error}>
        {b.data && (
          <div className="grid lg:grid-cols-2 gap-5">
            <Card title="Engines">
              <table>
                <thead><tr><th>Engine</th><th>Status</th><th>JavaScript</th><th>Screenshots</th></tr></thead>
                <tbody>{b.data.engines.map((e: any) => <tr key={e.engine}><td>{e.engine}<div className="text-xs text-mute">{e.available ? "" : e.detail}</div></td><td><Badge tone={e.available ? "ok" : "missing"}>{e.available ? "ready" : "not installed"}</Badge></td><td>{e.renders_js ? "Yes" : "No"}</td><td>{e.screenshots ? "Yes" : "No"}</td></tr>)}</tbody>
              </table>
              {!b.data.engines.some((e: any) => e.available && e.renders_js) && <div className="mt-4"><Notice tone="warn">No rendering engine is installed on this machine. Captures fall back to plain HTTP: no JavaScript and no screenshots.</Notice></div>}
            </Card>
            <Card title="Sources and permissions">
              {sources.data?.length ? (
                <table>
                  <thead><tr><th>Source</th><th>Mode</th><th>Approved</th><th>Page limit</th></tr></thead>
                  <tbody>{sources.data.map((s) => <tr key={s.id}><td>{s.name}<div className="text-xs text-mute">{s.base_url}</div>{s.notes && <div className="text-xs text-mute mt-1">{s.notes}</div>}</td><td><Badge tone={s.automation === "automated" ? "ok" : "warn"}>{s.automation}</Badge></td><td><Badge tone={s.approved ? "ok" : "pending"}>{s.approved ? "yes" : "awaiting"}</Badge></td><td className="num">{s.max_pages}</td></tr>)}</tbody>
                </table>
              ) : <Empty>No sources configured.</Empty>}
              <form className="grid sm:grid-cols-2 gap-2 mt-4 pt-4 border-t border-line" onSubmit={(e) => { e.preventDefault(); srcAct.run(async () => { await api(`/projects/${pid}/sources`, { body: src }); sources.reload(); setSrc({ ...src, name: "", base_url: "" }); }, "Source added. It needs approval in the Agent Centre before use."); }}>
                <div><label htmlFor="s-name">Source name</label><input id="s-name" required value={src.name} onChange={(e) => setSrc({ ...src, name: e.target.value })} /></div>
                <div><label htmlFor="s-url">Base URL</label><input id="s-url" required type="url" placeholder="https://example.com/" value={src.base_url} onChange={(e) => setSrc({ ...src, base_url: e.target.value })} /></div>
                <div><label htmlFor="s-mode">Collection mode requested</label><select id="s-mode" value={src.automation} onChange={(e) => setSrc({ ...src, automation: e.target.value })}><option value="manual_only">Manual evidence only</option><option value="automated">Automated capture</option></select></div>
                <div><label htmlFor="s-max">Page limit</label><input id="s-max" type="number" min={1} max={500} value={src.max_pages} onChange={(e) => setSrc({ ...src, max_pages: Number(e.target.value) })} /></div>
                <div className="sm:col-span-2"><Button type="submit" disabled={srcAct.busy}>Request source</Button></div>
              </form>
              <div className="mt-3">{srcAct.note}</div>
            </Card>
            <Card title="Profiles">
              <table>
                <thead><tr><th>Name</th><th>Engine</th><th>Viewport</th><th>Mode</th><th>Session</th></tr></thead>
                <tbody>{b.data.profiles.map((p: any) => <tr key={p.id}><td>{p.name}</td><td>{p.engine}</td><td className="num">{p.viewport_width}×{p.viewport_height}{p.mobile ? " mobile" : ""}</td><td>{p.headless ? "Headless" : "Visible"}</td><td>{p.persistent ? (p.session_on_disk ? "Kept on disk" : "Persistent, unused") : "Fresh each run"}</td></tr>)}</tbody>
              </table>
              <form className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-4 pt-4 border-t border-line items-end" onSubmit={(e) => { e.preventDefault(); profAct.run(async () => { await api("/browser/profiles", { body: prof }); b.reload(); setProf({ ...prof, name: "" }); }, "Profile added."); }}>
                <div className="col-span-2"><label htmlFor="p-name">Profile name</label><input id="p-name" required minLength={2} value={prof.name} onChange={(e) => setProf({ ...prof, name: e.target.value })} /></div>
                <div><label htmlFor="p-eng">Engine</label><select id="p-eng" value={prof.engine} onChange={(e) => setProf({ ...prof, engine: e.target.value })}>{["chromium", "firefox", "webkit", "http"].map((x) => <option key={x}>{x}</option>)}</select></div>
                <div><label htmlFor="p-w">Width</label><input id="p-w" type="number" value={prof.viewport_width} onChange={(e) => setProf({ ...prof, viewport_width: Number(e.target.value) })} /></div>
                <div><label htmlFor="p-h">Height</label><input id="p-h" type="number" value={prof.viewport_height} onChange={(e) => setProf({ ...prof, viewport_height: Number(e.target.value) })} /></div>
                {(["mobile", "headless", "persistent"] as const).map((k) => <label key={k} className="flex items-center gap-2 !mb-2 !text-[13px] !text-bone"><input type="checkbox" checked={prof[k]} onChange={(e) => setProf({ ...prof, [k]: e.target.checked })} />{k === "mobile" ? "Mobile emulation" : k === "headless" ? "Headless" : "Keep session"}</label>)}
                <div className="col-span-2 sm:col-span-4"><Button type="submit" disabled={profAct.busy}>Add profile</Button></div>
              </form>
              <div className="mt-3">{profAct.note}</div>
              <p className="text-xs text-mute mt-3">{b.data.session_note}</p>
            </Card>
            <Card title="Capture a page">
              <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); capAct.run(async () => { const r = await api(`/projects/${pid}/capture`, { body: cap }); if (!r.created) throw new Error(`This capture already exists as task #${r.task.id} (${r.task.status}).`); }, "Capture queued. Follow it in the Agent Centre."); }}>
                <div><label htmlFor="c-url">Page URL (must belong to an approved, automated source)</label><input id="c-url" required type="url" value={cap.url} onChange={(e) => setCap({ ...cap, url: e.target.value })} /></div>
                <div><label htmlFor="c-prof">Profile</label><select id="c-prof" value={cap.profile} onChange={(e) => setCap({ ...cap, profile: e.target.value })}><option value="">Best available engine, 1440×900</option>{b.data.profiles.map((p: any) => <option key={p.id}>{p.name}</option>)}</select></div>
                <Button type="submit" kind="primary" disabled={capAct.busy}>Queue capture</Button>
              </form>
              <div className="mt-3">{capAct.note}</div>
            </Card>
            <Card title="Capture runs" className="lg:col-span-2">
              <Scroll max={340}>
                {b.data.runs.length ? (
                  <table><thead><tr><th>When</th><th>URL</th><th>Engine</th><th>Status</th><th>HTTP</th><th>Time</th><th>Console errors</th><th>Error</th></tr></thead>
                    <tbody>{b.data.runs.map((r: any) => <tr key={r.id}><td className="text-xs text-mute whitespace-nowrap">{when(r.started_at)}</td><td>{r.url}</td><td>{r.engine}</td><td><Badge>{r.status}</Badge></td><td className="num">{r.http_status ?? "—"}</td><td className="num whitespace-nowrap">{r.duration_ms} ms</td><td className="num">{r.console_errors.length}</td><td className="text-xs text-mute">{r.error}</td></tr>)}</tbody></table>
                ) : <Empty>No captures have run for this project.</Empty>}
              </Scroll>
            </Card>
          </div>
        )}
      </State>
    </>
  );
}
