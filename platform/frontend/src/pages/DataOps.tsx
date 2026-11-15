import { useRef, useState } from "react";
import { api } from "../api";
import { Card, ErrorNote, Spinner, useFetch } from "../components/ui";

const PLUGIN_KINDS: [string, string, string][] = [
  ["ai_provider", "AI Providers", "Model adapters (offline / OpenAI-compatible / custom)"],
  ["browser_engine", "Browser Engines", "Playwright adapters for capture"],
  ["report_format", "Report Formats", "Extra renderers (PDF built-in)"],
  ["analysis_module", "Analysis Modules", "Analytics computations fed to reports"],
];

export default function DataOps({ pid }: { pid: string }) {
  return (
    <div className="space-y-6">
      <p className="text-xs leading-relaxed text-faint">
        Platform operations: consistent database backups, the modular plugin registry, and
        project portability (export / import a full research project as a versioned bundle).
      </p>
      <BackupSection />
      <PluginSection />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ExportSection pid={pid} />
        <ImportSection />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- backups
function BackupSection() {
  const { data, loading, error, reload } = useFetch(() => api.listBackups(), []);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  async function take() {
    setBusy(true);
    setNote("");
    try {
      const r = await api.createBackup();
      setNote(`Backup written → ${r.path} (${Math.round(r.bytes / 1024)} KB, keeping ${r.kept})`);
      reload();
    } catch (e) {
      setNote(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      title="Database Backups"
      action={
        <button className="btn btn-gold" disabled={busy} onClick={take}>
          {busy ? <Spinner /> : "Create Backup"}
        </button>
      }
    >
      {loading && <div className="p-4"><Spinner /></div>}
      {error && <ErrorNote error={error} />}
      {note && <div className="px-4 pt-3 text-xs text-muted">{note}</div>}
      {(data || []).length > 0 && (
        <table className="w-full text-left text-[12px]">
          <thead>
            <tr className="border-b border-line text-faint">
              <th className="px-4 py-2 font-medium">File</th>
              <th className="px-4 py-2 font-medium">Size</th>
              <th className="px-4 py-2 font-medium">Created (UTC)</th>
            </tr>
          </thead>
          <tbody>
            {(data || []).map((b) => (
              <tr key={b.name} className="border-b border-line/60">
                <td className="px-4 py-2 font-mono text-muted">{b.name}</td>
                <td className="px-4 py-2 text-muted">{Math.round(b.bytes / 1024)} KB</td>
                <td className="px-4 py-2 text-faint">{b.modified}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {(data || []).length === 0 && !loading && (
        <div className="px-4 py-3 text-sm text-muted">No backups yet.</div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------- plugins
function PluginSection() {
  const { data, loading, error } = useFetch(() => api.plugins(), []);
  return (
    <Card title="Plugin Registry">
      <p className="px-4 pt-3 text-xs text-faint">
        The core is extensible without redesign: AI providers, browser engines, report formats and
        analysis modules register here. External plugins install via the <code className="text-muted">rice.plugins</code>{" "}
        entry-point group.
      </p>
      {loading && <div className="p-4"><Spinner /></div>}
      {error && <ErrorNote error={error} />}
      <div className="grid grid-cols-1 gap-4 p-4 sm:grid-cols-2">
        {PLUGIN_KINDS.map(([kind, label, sub]) => (
          <div key={kind} className="rounded-lg border border-line bg-charcoal p-3">
            <div className="mb-1 flex items-baseline justify-between">
              <span className="text-[13px] font-medium text-white">{label}</span>
              <span className="text-[10px] text-faint">{data?.[kind]?.length ?? 0} registered</span>
            </div>
            <div className="mb-2 text-[10px] text-faint">{sub}</div>
            <ul className="space-y-1">
              {(data?.[kind] || []).map((p) => (
                <li key={p.name} className="flex items-center gap-2 text-[12px]">
                  <span className="font-mono text-gold-soft">{p.name}</span>
                  <span className="text-[10px] text-faint">
                    {p.source === "builtin" ? "builtin" : "external"}
                  </span>
                </li>
              ))}
              {data && (data[kind] || []).length === 0 && (
                <li className="text-[11px] text-faint">none registered</li>
              )}
            </ul>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------- export
function ExportSection({ pid }: { pid: string }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  if (!pid) return <Card title="Export Project"><div className="p-4 text-sm text-muted">Select a project first.</div></Card>;

  async function doExport() {
    setBusy(true);
    setMsg("");
    try {
      const bundle = await api.exportProject(pid);
      const counts = bundle as { pages?: unknown[]; features?: unknown[]; evidence?: unknown[] };
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `project-export-${pid}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setMsg(`Exported ${counts.pages?.length ?? 0} pages, ${counts.features?.length ?? 0} features, ${counts.evidence?.length ?? 0} evidence.`);
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Export Project" action={<button className="btn" disabled={busy} onClick={doExport}>{busy ? <Spinner /> : "⬇ Export JSON Bundle"}</button>}>
      <p className="px-4 pt-3 text-xs text-faint">
        Serialises the whole project — pages, features, evidence, observations, questions, sources,
        collection scopes and reports — into a versioned, portable JSON bundle. Evidence references
        are normalised so the bundle imports cleanly on any installation.
      </p>
      {msg && <div className="px-4 pt-3 text-xs text-muted">{msg}</div>}
    </Card>
  );
}

// ---------------------------------------------------------------- import
function ImportSection() {
  const [msg, setMsg] = useState("");
  const [name, setName] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  async function onFile(f: File) {
    setMsg("");
    try {
      const bundle = JSON.parse(await f.text());
      const r = await api.importProject(bundle, name);
      setMsg(`Imported → new project ${r.project_id} (${r.counts.pages} pages, ${r.counts.features} features, ${r.counts.evidence} evidence). Select it from the top bar.`);
      if (fileRef.current) fileRef.current.value = "";
      setName("");
    } catch (e) {
      setMsg(String(e));
    }
  }

  return (
    <Card title="Import Project">
      <p className="px-4 pt-3 text-xs text-faint">
        Restore a previously exported bundle as a new, fully-isolated project. Ids are regenerated
        and cross-references remapped. Robots exceptions and approvals do not travel — re-decide
        them locally.
      </p>
      <div className="flex flex-wrap items-center gap-2 p-4">
        <input ref={fileRef} type="file" accept="application/json" className="text-xs text-muted"
          onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])} />
        <input
          className="w-48 rounded-md border border-line bg-charcoal px-2 py-1 text-xs text-white outline-none focus:border-gold-dim"
          placeholder="new project name (optional)"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>
      {msg && <div className="px-4 pb-3 text-xs text-muted">{msg}</div>}
    </Card>
  );
}
