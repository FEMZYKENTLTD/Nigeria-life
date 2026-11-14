import { useMemo, useState } from "react";
import { api, useData, when } from "../api";
import type { PageProps } from "../App";
import { Badge, Button, Card, Empty, Notice, PageTitle, Scroll, State, Tabs, useAction } from "../ui";

const TABS = [["features", "Features"], ["pages", "Pages"], ["findings", "Findings"], ["evidence", "Evidence"], ["screenshots", "Screenshots"], ["questions", "Open questions"], ["notes", "Notes and decisions"]] as const;
type Tab = (typeof TABS)[number][0];

export default function Workspace({ pid }: PageProps) {
  const [tab, setTab] = useState<Tab>("features");
  return (
    <>
      <PageTitle title="Research Workspace" sub="Everything recorded for this project. Empty fields are shown as empty; nothing is filled in by guesswork." />
      <Tabs tabs={TABS} value={tab} onChange={setTab} />
      {tab === "features" && <Features pid={pid} />}
      {tab === "pages" && <Pages pid={pid} />}
      {tab === "findings" && <Findings pid={pid} />}
      {tab === "evidence" && <EvidenceTab pid={pid} />}
      {tab === "screenshots" && <Screens pid={pid} />}
      {tab === "questions" && <Questions pid={pid} />}
      {tab === "notes" && <Notes pid={pid} />}
    </>
  );
}

const label = (f: string) => f.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

function Features({ pid }: { pid: number }) {
  const d = useData<any>(`/projects/${pid}/features`);
  const [cat, setCat] = useState("");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<any>(null);
  const list = useMemo(() => (d.data?.features ?? []).filter((f: any) => (!cat || f.category === cat) && (!q || f.name.toLowerCase().includes(q.toLowerCase()))), [d.data, cat, q]);
  return (
    <State loading={d.loading} error={d.error}>
      <div className={`grid gap-5 ${open ? "xl:grid-cols-[1fr_440px]" : ""}`}>
        <Card title={`${list.length} features`} action={
          <div className="flex gap-2">
            <input aria-label="Filter by name" placeholder="Filter by name" value={q} onChange={(e) => setQ(e.target.value)} className="!w-40" />
            <select aria-label="Category" value={cat} onChange={(e) => setCat(e.target.value)} className="!w-44"><option value="">All categories</option>{d.data?.categories.map((c: string) => <option key={c}>{c}</option>)}</select>
          </div>}>
          <Scroll max={640}>
            {list.length ? (
              <table>
                <thead><tr><th>Feature</th><th>Category</th><th>Confidence</th><th>Fields</th><th>Evidence</th><th>Status</th></tr></thead>
                <tbody>{list.map((f: any) => (
                  <tr key={f.id} onClick={() => setOpen(f)} className="cursor-pointer" aria-selected={open?.id === f.id}>
                    <td><button className="text-left text-bone hover:text-gold cursor-pointer">{f.name}</button></td><td className="text-mute">{f.category}</td><td><Badge>{f.confidence}</Badge></td>
                    <td className="num whitespace-nowrap">{f.fields_filled}/{f.fields_total}</td><td className="font-mono text-xs">{f.evidence_refs.join(", ") || "—"}</td><td><Badge>{f.status}</Badge></td>
                  </tr>
                ))}</tbody>
              </table>
            ) : <Empty>No features match.</Empty>}
          </Scroll>
        </Card>
        {open && <FeatureEditor key={open.id} feature={open} fields={d.data.fields} onClose={() => setOpen(null)} onSaved={(f) => { setOpen({ ...open, ...f }); d.reload(); }} />}
      </div>
    </State>
  );
}

function FeatureEditor({ feature, fields, onClose, onSaved }: { feature: any; fields: string[]; onClose: () => void; onSaved: (f: any) => void }) {
  const [vals, setVals] = useState<Record<string, string>>({ ...feature.fields });
  const [status, setStatus] = useState(feature.status);
  const [stamp, setStamp] = useState(feature.updated_at);
  const versions = useData<any[]>(`/versions/features/${feature.id}`);
  const act = useAction();
  const changed = fields.filter((k) => (vals[k] ?? "") !== (feature.fields[k] ?? ""));
  return (
    <Card title={feature.name} action={<Button small onClick={onClose}>Close</Button>}>
      <div className="flex flex-wrap gap-2 mb-3 text-xs text-mute"><Badge>{feature.confidence}</Badge><span>{feature.category}</span><span>from {feature.origin}</span></div>
      <form className="space-y-3" onSubmit={(e) => {
        e.preventDefault();
        act.run(async () => {
          const f = await api(`/features/${feature.id}`, { method: "PATCH", body: { fields: Object.fromEntries(changed.map((k) => [k, vals[k]])), status, expected_updated_at: stamp } });
          setStamp(f.updated_at); onSaved(f); versions.reload();
        }, "Saved. The previous version was kept.");
      }}>
        <div className="max-h-[430px] overflow-auto pr-1 space-y-3">
          {fields.map((k) => (
            <div key={k}><label htmlFor={`f-${k}`}>{label(k)}{!(vals[k] ?? "").trim() && <span className="text-warn"> · not documented</span>}</label>
              <textarea id={`f-${k}`} rows={k === "description" ? 3 : 2} value={vals[k] ?? ""} onChange={(e) => setVals({ ...vals, [k]: e.target.value })} /></div>
          ))}
        </div>
        <div className="flex items-end gap-2">
          <div className="flex-1"><label htmlFor="f-status">Status</label><select id="f-status" value={status} onChange={(e) => setStatus(e.target.value)}><option value="draft">Draft</option><option value="verified">Verified by a researcher</option></select></div>
          <Button type="submit" kind="primary" disabled={act.busy || (!changed.length && status === feature.status)}>Save</Button>
        </div>
        {act.note}
      </form>
      <div className="mt-4 pt-3 border-t border-line text-xs text-mute">
        <div className="mb-1 text-bone">Version history</div>
        {versions.data?.length ? <ul className="space-y-1">{versions.data.map((v) => <li key={v.id}>v{v.version} · {when(v.changed_at)} · {v.reason}</li>)}</ul> : "No earlier versions."}
      </div>
    </Card>
  );
}

function Pages({ pid }: { pid: number }) {
  const d = useData<any[]>(`/projects/${pid}/pages`);
  const [id, setId] = useState<number | null>(null);
  const detail = useData<any>(id ? `/pages/${id}` : null);
  const r = detail.data?.record;
  return (
    <State loading={d.loading} error={d.error}>
      <div className={`grid gap-5 ${id ? "xl:grid-cols-[1fr_460px]" : ""}`}>
        <Card title={`${d.data?.length ?? 0} pages`}>
          <Scroll max={640}>
            {d.data?.length ? (
              <table><thead><tr><th>URL</th><th>Status</th><th>HTTP</th><th>Engine</th><th>Purpose</th></tr></thead>
                <tbody>{d.data.map((p) => <tr key={p.id} className="cursor-pointer" onClick={() => setId(p.id)}><td><button className="text-left hover:text-gold cursor-pointer">{p.url}</button></td><td><Badge>{p.status}</Badge></td><td className="num">{p.http_status ?? "—"}</td><td>{p.engine || "—"}</td><td className="text-mute text-xs max-w-[40ch]">{p.purpose}</td></tr>)}</tbody></table>
            ) : <Empty>No pages known yet.</Empty>}
          </Scroll>
        </Card>
        {id && (
          <Card title="Page record" action={<Button small onClick={() => setId(null)}>Close</Button>}>
            <State loading={detail.loading} error={detail.error}>
              {detail.data && (
                <div className="space-y-3 text-[13px] max-h-[600px] overflow-auto">
                  <div className="break-all text-gold">{detail.data.url}</div>
                  {detail.data.status === "imported" && <Notice>Known from imported research only. The engine has not captured this page. Evidence: {(r?.evidence ?? []).join(", ") || "none listed"}.</Notice>}
                  <Row k="Title" v={detail.data.title} /><Row k="Purpose" v={`${detail.data.purpose}${r?.purpose_basis ? ` (${r.purpose_basis})` : ""}`} />
                  {r?.headings && <>
                    <Row k="States noted" v={(r.states ?? []).join(", ") || "none"} />
                    <Row k="Rendered with JavaScript" v={r.rendered_with_js ? "Yes" : "No — server HTML only"} />
                    <Row k="Regions" v={(r.regions ?? []).map((x: any) => `${x.region} ×${x.count}`).join(", ")} />
                    <Row k="Headings" v={(r.headings ?? []).slice(0, 12).map((h: any) => `H${h.level} ${h.text}`).join(" · ")} />
                    <Row k="Navigation" v={(r.navigation ?? []).map((n: any) => n.text || n.url).join(" · ")} />
                    <Row k="Forms" v={(r.forms ?? []).map((f: any) => `${f.method.toUpperCase()} ${f.action || "(same page)"}: ${f.fields.map((x: any) => x.name || x.type).join(", ")}`).join(" | ")} />
                    <Row k="Controls" v={(r.controls ?? []).slice(0, 25).map((c: any) => `${c.kind}: ${c.label || "unlabelled"}`).join(" · ")} />
                    <Row k="Repeated components" v={(r.repeated_components ?? []).map((c: any) => `${c.tag}.${c.class} ×${c.count}`).join(" · ")} />
                    <Row k="Console errors" v={(r.console_errors ?? []).join(" | ")} />
                    <Row k="Links" v={`${(r.links ?? []).length} (${(r.internal_links ?? []).length} internal)`} />
                    <Row k="Words" v={String(r.word_count ?? "")} />
                  </>}
                  <Row k="Findings" v={String(detail.data.findings.length)} />
                </div>
              )}
            </State>
          </Card>
        )}
      </div>
    </State>
  );
}
const Row = ({ k, v }: { k: string; v?: string }) => <div><div className="text-xs text-mute">{k}</div><div>{v || <span className="text-mute">—</span>}</div></div>;

function Findings({ pid }: { pid: number }) {
  const d = useData<any[]>(`/projects/${pid}/findings`);
  return (
    <State loading={d.loading} error={d.error}>
      <Card title={`${d.data?.length ?? 0} findings`}>
        <Scroll max={640}>
          {d.data?.length ? (
            <table><thead><tr><th>ID</th><th>Observation</th><th>Page</th><th>Evidence</th><th>Confidence</th><th>Status</th><th>Recorded</th></tr></thead>
              <tbody>{d.data.map((f) => <tr key={f.id}><td className="font-mono text-xs whitespace-nowrap">{f.uid}</td><td>{f.observation}</td><td className="text-xs text-mute">{f.page_url ?? "—"}</td><td className="font-mono text-xs">{f.evidence_ref ?? "—"}</td><td><Badge>{f.confidence}</Badge></td><td><Badge>{f.status}</Badge></td><td className="text-xs text-mute whitespace-nowrap">{when(f.created_at)}</td></tr>)}</tbody></table>
          ) : <Empty>No findings yet. They are created when a page is captured or when a researcher adds evidence with an observation.</Empty>}
        </Scroll>
      </Card>
    </State>
  );
}

function EvidenceTab({ pid }: { pid: number }) {
  const d = useData<any[]>(`/projects/${pid}/evidence`);
  const [f, setF] = useState({ summary: "", source_url: "", locator: "", classification: "confirmed", observation: "" });
  const [file, setFile] = useState<File | null>(null);
  const act = useAction();
  const submit = () => act.run(async () => {
    let content_base64 = "";
    if (file) {
      const bytes = new Uint8Array(await file.arrayBuffer());
      let bin = "";
      for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
      content_base64 = btoa(bin);
    }
    await api(`/projects/${pid}/evidence`, { body: { ...f, filename: file?.name ?? "", content_base64 } });
    setF({ ...f, summary: "", locator: "", observation: "" }); setFile(null); d.reload();
  }, "Evidence recorded.");
  return (
    <div className="grid xl:grid-cols-[1fr_400px] gap-5">
      <State loading={d.loading} error={d.error}>
        <Card title={`${d.data?.length ?? 0} evidence items`}>
          <Scroll max={640}>
            {d.data?.length ? (
              <table><thead><tr><th>ID</th><th>Class</th><th>Kind</th><th>Source</th><th>Summary</th><th>Captured</th><th>File</th></tr></thead>
                <tbody>{d.data.map((e) => <tr key={e.id}><td className="font-mono text-xs whitespace-nowrap">{e.ref}</td><td><Badge>{e.classification}</Badge></td><td className="text-mute">{e.kind}</td><td className="text-xs max-w-[26ch]">{e.source_url}<div className="text-mute">{e.locator}</div></td><td className="text-xs max-w-[52ch]">{e.summary.length > 260 ? e.summary.slice(0, 260) + "…" : e.summary}</td><td className="text-xs text-mute whitespace-nowrap">{when(e.captured_at)}<div>{e.captured_by}</div></td><td className="text-xs">{e.archived ? <span title={`SHA-256 ${e.sha256}`}>Archived</span> : <span className="text-mute">None</span>}</td></tr>)}</tbody></table>
            ) : <Empty>No evidence yet.</Empty>}
          </Scroll>
        </Card>
      </State>
      <Card title="Add evidence by hand">
        <p className="text-xs text-mute mb-3">Use this for sources that do not allow automation. Do not paste passwords, cookies, tokens or payment details; anything that looks like one is removed before saving.</p>
        <form className="space-y-2.5" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <div><label htmlFor="e-sum">What this evidence shows</label><textarea id="e-sum" required minLength={3} rows={3} value={f.summary} onChange={(e) => setF({ ...f, summary: e.target.value })} /></div>
          <div><label htmlFor="e-url">Source URL</label><input id="e-url" value={f.source_url} onChange={(e) => setF({ ...f, source_url: e.target.value })} /></div>
          <div><label htmlFor="e-loc">Screen or component</label><input id="e-loc" value={f.locator} onChange={(e) => setF({ ...f, locator: e.target.value })} /></div>
          <div><label htmlFor="e-class">Evidence class</label><select id="e-class" value={f.classification} onChange={(e) => setF({ ...f, classification: e.target.value })}>
            <option value="confirmed">Confirmed — seen first-hand</option><option value="secondary">Secondary — reported by others</option><option value="inference">Inference</option><option value="hypothesis">Hypothesis</option><option value="unknown">Unknown</option></select></div>
          <div><label htmlFor="e-obs">Observation to record as a finding (optional)</label><textarea id="e-obs" rows={2} value={f.observation} onChange={(e) => setF({ ...f, observation: e.target.value })} /></div>
          <div><label htmlFor="e-file">Screenshot or file (optional, up to 15 MB)</label><input id="e-file" type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></div>
          <Button type="submit" kind="primary" disabled={act.busy}>Record evidence</Button>
          {act.note}
        </form>
      </Card>
    </div>
  );
}

function Screens({ pid }: { pid: number }) {
  const d = useData<any[]>(`/projects/${pid}/screenshots`);
  const [pick, setPick] = useState<number[]>([]);
  const [cmp, setCmp] = useState<any>(null);
  const act = useAction();
  const toggle = (id: number) => { setCmp(null); setPick((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p.slice(-1), id])); };
  return (
    <State loading={d.loading} error={d.error}>
      <Card title={`${d.data?.length ?? 0} screenshots`} action={<Button small disabled={pick.length !== 2 || act.busy} onClick={() => act.run(async () => setCmp(await api(`/screenshots/compare?a=${pick[0]}&b=${pick[1]}`)), "Compared.")}>Compare two selected</Button>}>
        {cmp && <div className="mb-4"><Notice>{cmp.changed_pixels.toLocaleString()} of {cmp.total_pixels.toLocaleString()} pixels differ ({(cmp.changed_ratio * 100).toFixed(2)}%). {cmp.changed_region ? `Changed area: x ${cmp.changed_region[0]}–${cmp.changed_region[2]}, y ${cmp.changed_region[1]}–${cmp.changed_region[3]}.` : "No changed area."} {cmp.same_dimensions ? "" : "The images have different sizes, so the second was resized first and the figure is approximate."} Method: {cmp.method}.</Notice></div>}
        {d.data?.length ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {d.data.map((s) => (
              <button key={s.id} onClick={() => toggle(s.id)} aria-pressed={pick.includes(s.id)} className={`text-left border rounded overflow-hidden cursor-pointer ${pick.includes(s.id) ? "border-gold" : "border-line"}`}>
                <img src={`/api/screenshots/${s.id}/file`} alt={`Screenshot ${s.id}, ${s.category}`} loading="lazy" className="w-full h-36 object-cover object-top bg-slate" />
                <div className="p-2 text-xs text-mute">{s.category} · {s.width}×{s.height} · {s.engine}<div>{when(s.created_at)}</div>{s.annotations.length > 0 && <div>{s.annotations.length} annotation(s)</div>}</div>
              </button>
            ))}
          </div>
        ) : <Empty>No screenshots. They are taken when a rendering browser engine is installed, or uploaded as manual evidence.</Empty>}
        <p className="text-xs text-mute mt-4">Image comparison counts changed pixels. It does not interpret what the image shows; no vision model is configured.</p>
      </Card>
    </State>
  );
}

function Questions({ pid }: { pid: number }) {
  const d = useData<any[]>(`/projects/${pid}/questions`);
  const [text, setText] = useState("");
  const [ans, setAns] = useState<Record<number, string>>({});
  const act = useAction();
  return (
    <State loading={d.loading} error={d.error}>
      <Card title={`${d.data?.filter((q) => q.status === "open").length ?? 0} open of ${d.data?.length ?? 0}`}>
        <form className="flex gap-2 mb-4" onSubmit={(e) => { e.preventDefault(); act.run(async () => { await api(`/projects/${pid}/questions`, { body: { text } }); setText(""); d.reload(); }, "Question added."); }}>
          <input aria-label="New question" required minLength={3} placeholder="Add a question to investigate" value={text} onChange={(e) => setText(e.target.value)} /><Button type="submit" disabled={act.busy}>Add</Button>
        </form>
        {act.note}
        <ul className="divide-y divide-line">
          {d.data?.map((q) => (
            <li key={q.id} className="py-3">
              <div className="flex gap-2 items-start"><Badge>{q.status}</Badge><div className="flex-1"><div className="text-[13px]">{q.text}</div><div className="text-xs text-mute">{q.origin}</div>{q.answer && <div className="text-[13px] mt-1 text-ok">Answer: {q.answer}</div>}</div></div>
              {q.status === "open" && (
                <form className="flex gap-2 mt-2 ml-14" onSubmit={(e) => { e.preventDefault(); act.run(async () => { await api(`/questions/${q.id}/answer`, { body: { answer: ans[q.id] ?? "" } }); d.reload(); }, "Answer saved."); }}>
                  <input aria-label={`Answer for question ${q.id}`} required placeholder="Answer, with evidence ID" value={ans[q.id] ?? ""} onChange={(e) => setAns({ ...ans, [q.id]: e.target.value })} /><Button small type="submit">Save answer</Button>
                </form>
              )}
            </li>
          ))}
        </ul>
        {!d.data?.length && <Empty>No questions recorded.</Empty>}
      </Card>
    </State>
  );
}

function Notes({ pid }: { pid: number }) {
  const d = useData<any>(`/projects/${pid}/notes`);
  const [note, setNote] = useState("");
  const [dec, setDec] = useState({ text: "", rationale: "" });
  const act = useAction();
  return (
    <State loading={d.loading} error={d.error}>
      <div className="grid lg:grid-cols-2 gap-5">
        <Card title="Notes">
          <form className="space-y-2 mb-4" onSubmit={(e) => { e.preventDefault(); act.run(async () => { await api(`/projects/${pid}/notes`, { body: { text: note } }); setNote(""); d.reload(); }, "Note saved."); }}>
            <textarea aria-label="New note" required rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Write a note" /><Button type="submit">Save note</Button>
          </form>
          {d.data?.notes.length ? <ul className="space-y-3">{d.data.notes.map((n: any) => <li key={n.id} className="text-[13px]"><div className="whitespace-pre-wrap">{n.text}</div><div className="text-xs text-mute">{when(n.created_at)}</div></li>)}</ul> : <Empty>No notes.</Empty>}
        </Card>
        <Card title="Decisions">
          <form className="space-y-2 mb-4" onSubmit={(e) => { e.preventDefault(); act.run(async () => { await api(`/projects/${pid}/decisions`, { body: dec }); setDec({ text: "", rationale: "" }); d.reload(); }, "Decision recorded."); }}>
            <input aria-label="Decision" required placeholder="Decision" value={dec.text} onChange={(e) => setDec({ ...dec, text: e.target.value })} />
            <input aria-label="Reason" placeholder="Reason" value={dec.rationale} onChange={(e) => setDec({ ...dec, rationale: e.target.value })} /><Button type="submit">Record decision</Button>
          </form>
          {d.data?.decisions.length ? <ul className="space-y-3">{d.data.decisions.map((n: any) => <li key={n.id} className="text-[13px]"><div>{n.text}</div>{n.rationale && <div className="text-mute">Because: {n.rationale}</div>}<div className="text-xs text-mute">{n.made_by} · {when(n.created_at)}</div></li>)}</ul> : <Empty>No decisions recorded.</Empty>}
        </Card>
        <div className="lg:col-span-2">{act.note}</div>
      </div>
    </State>
  );
}
