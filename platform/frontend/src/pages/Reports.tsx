import { useState } from "react";
import { api, Report } from "../api";
import { Card, ErrorNote, Spinner, timeAgo, useFetch } from "../components/ui";

const FORMATS = ["md", "html", "json", "csv", "pdf"] as const;

export default function Reports({ pid }: { pid: string }) {
  const { data: reports, error, loading, reload } = useFetch(
    () => (pid ? api.reports(pid) : Promise.resolve([])), [pid]);
  const { data: types } = useFetch(() => api.reportTypes(), []);
  const [type, setType] = useState("executive");
  const [format, setFormat] = useState<string>("md");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [open, setOpen] = useState<Report | null>(null);

  if (error) return <ErrorNote error={error} />;
  if (loading || !types) return <Spinner />;

  const available = (t: string) => types[t] ? true : false;

  async function generate() {
    setBusy(true);
    setMsg("");
    try {
      const r = await api.generateReport(pid, type, format);
      setMsg(`Generated "${r.title}" (${format}).`);
      reload();
    } catch (e: any) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function openReport(r: Report) {
    try {
      setOpen(await api.report(r.id));
    } catch (e: any) {
      setMsg(String(e.message || e));
    }
  }

  return (
    <div className="space-y-6">
      {open && <ReportViewer report={open} onClose={() => setOpen(null)} />}
      <Card title="Generate a report">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <div className="card-title mb-1">Type</div>
            <select className="input min-w-64" value={type} onChange={(e) => setType(e.target.value)}>
              {Object.entries(types).map(([t, desc]) => (
                <option key={t} value={t}>{t.replace(/_/g, " ")} — {desc}</option>
              ))}
            </select>
          </div>
          <div>
            <div className="card-title mb-1">Format</div>
            <select className="input !w-32" value={format} onChange={(e) => setFormat(e.target.value)}>
              {FORMATS.map((f) => (
                <option key={f} value={f}>{f.toUpperCase()}</option>
              ))}
            </select>
          </div>
          <button className="btn btn-gold" disabled={busy} onClick={generate}>
            {busy ? "Generating…" : "Generate"}
          </button>
          {msg && <span className="text-xs text-muted">{msg}</span>}
        </div>
        <p className="mt-3 text-[11px] leading-relaxed text-faint">
          Every report carries an evidence footer citing the exact evidence items behind each
          finding, and is persisted under <code>data/reports/</code> in every requested format.
        </p>
      </Card>

      <Card title={`Report library — ${reports?.length ?? 0} generated`}>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-wider text-faint">
                <th className="py-2 pr-4">Title</th>
                <th className="py-2 pr-4">Format</th>
                <th className="py-2 pr-4">Size</th>
                <th className="py-2 pr-4">Generated</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {(reports || []).map((r) => (
                <tr key={r.id} className="border-b border-line/60">
                  <td className="py-2 pr-4 text-white">{r.title}</td>
                  <td className="py-2 pr-4 uppercase font-mono text-gold-soft">{r.format}</td>
                  <td className="py-2 pr-4 font-mono text-muted">{(r.content?.length || 0).toLocaleString()} chars</td>
                  <td className="py-2 pr-4 text-faint">{timeAgo(r.generated_at)}</td>
                  <td className="py-2 text-right">
                    <button className="btn" onClick={() => openReport(r)}>Open</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {(reports || []).length === 0 && (
            <div className="py-4 text-sm text-muted">
              No reports yet. Generate one above — 14 report types, each with an evidence footer.
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

export function ReportViewer({ report, onClose }: { report: Report; onClose: () => void }) {
  const isMd = ["md", "csv", "json"].includes(report.format);
  const isPdf = report.format === "pdf" && report.content.startsWith("data:");
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6" onClick={onClose}>
      <div
        className="flex max-h-[85vh] w-full max-w-4xl flex-col overflow-hidden rounded-xl border border-line bg-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-line px-5 py-3">
          <div>
            <div className="text-sm font-medium text-white">{report.title}</div>
            <div className="text-[11px] text-faint">{report.format.toUpperCase()}</div>
          </div>
          <div className="flex gap-2">
            {isPdf ? (
              <a className="btn" href={report.content} download={report.title.replace(/\s+/g, "_") + ".pdf"}>
                ⬇ Download PDF
              </a>
            ) : !isMd ? (
              <a
                className="btn"
                href={URL.createObjectURL(new Blob([report.content], { type: "text/html" }))}
                download={report.title.replace(/\s+/g, "_") + ".html"}
              >
                ⬇ Download
              </a>
            ) : null}
            <button className="btn" onClick={onClose}>Close ✕</button>
          </div>
        </div>
        <div className="overflow-auto p-5">
          {isMd ? (
            <pre className="whitespace-pre-wrap font-mono text-[12px] leading-relaxed text-muted">
              {report.content}
            </pre>
          ) : isPdf ? (
            <iframe title={report.title} src={report.content} className="h-[65vh] w-full rounded-lg border border-line bg-white" />
          ) : (
            <iframe
              title={report.title}
              srcDoc={report.content}
              className="h-[65vh] w-full rounded-lg border border-line bg-white"
            />
          )}
        </div>
      </div>
    </div>
  );
}
