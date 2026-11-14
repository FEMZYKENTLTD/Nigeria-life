import { useState } from "react";
import { api } from "../api";
import { Card, ClassPill, ErrorNote, Spinner, useFetch } from "../components/ui";

export default function Knowledge({ pid }: { pid: string }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<{ score: number; kind: string; title: string; snippet: string }[] | null>(null);
  const [explanation, setExplanation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { data: evidence, loading: lE, error: eE } = useFetch(
    () => (pid ? api.evidence(pid) : Promise.resolve([])), [pid]);
  const { data: features, loading: lF } = useFetch(
    () => (pid ? api.features(pid) : Promise.resolve([])), [pid]);

  if (!pid) return <div className="text-sm text-muted">Select a project first.</div>;
  if (eE) return <ErrorNote error={eE} />;

  async function runSearch() {
    if (!query.trim()) return;
    setBusy(true);
    setError("");
    try {
      const r = await api.search(pid, query, 15);
      setResults(r.results);
      setExplanation(r.explanation);
    } catch (e: any) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card title="Semantic search across the project knowledge base">
        <div className="flex gap-2">
          <input
            className="input"
            placeholder="Search features, pages, evidence, findings… (e.g. governor election, billboard price)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runSearch()}
          />
          <button className="btn btn-gold" disabled={busy} onClick={runSearch}>
            {busy ? "Searching…" : "Search"}
          </button>
        </div>
        {explanation && <p className="mt-2 text-[11px] text-faint">{explanation}</p>}
        {error && <div className="mt-2"><ErrorNote error={error} /></div>}

        {results !== null && (
          <div className="mt-4 space-y-2">
            {results.length === 0 && <div className="text-sm text-muted">No matches.</div>}
            {results.map((r, i) => (
              <div key={i} className="rounded-lg border border-line bg-charcoal/40 p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="badge border border-gold-dim/40 bg-gold-dim/10 text-gold-soft">{r.kind}</span>
                    <span className="truncate text-sm text-white">{r.title}</span>
                  </div>
                  <span className="font-mono text-[11px] text-faint">{r.score.toFixed(3)}</span>
                </div>
                <div className="mt-1 line-clamp-2 text-[11px] text-muted">{r.snippet}</div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title={`Evidence explorer — ${evidence?.length ?? 0} items`}>
          <div className="max-h-[28rem] space-y-2 overflow-y-auto pr-1">
            {(evidence || []).map((e) => (
              <div key={e.id} className="rounded-lg border border-line bg-charcoal/40 p-3">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-gold-soft">{e.ref_code || e.id.slice(0, 8)}</span>
                  <ClassPill cls={e.evidence_class} />
                  <span className="min-w-0 truncate text-xs text-white">{e.source_name || e.source_uri}</span>
                  <span className="ml-auto shrink-0 text-[10px] text-faint">cited ×{e.cited_by.length}</span>
                </div>
                <div className="mt-1 line-clamp-2 text-[11px] text-muted">{e.description}</div>
              </div>
            ))}
            {lE && <Spinner />}
          </div>
        </Card>

        <Card title={`Feature relationships — ${features?.length ?? 0} features`}>
          <div className="max-h-[28rem] space-y-2 overflow-y-auto pr-1">
            {(features || []).filter((f) => (f.dependencies?.length || f.related_features?.length)).slice(0, 40).map((f) => (
              <div key={f.id} className="rounded-lg border border-line bg-charcoal/40 p-3">
                <div className="text-sm text-white">{f.name}</div>
                <div className="mt-1 text-[11px] leading-relaxed text-muted">
                  {f.dependencies?.length ? (
                    <span>depends on: <span className="text-info">{f.dependencies.slice(0, 5).join(", ")}</span></span>
                  ) : null}
                  {f.dependencies?.length && f.related_features?.length ? " · " : ""}
                  {f.related_features?.length ? (
                    <span>related: <span className="text-gold-soft">{f.related_features.slice(0, 5).join(", ")}</span></span>
                  ) : null}
                </div>
              </div>
            ))}
            {lF && <Spinner />}
            {(features || []).length > 0 &&
              !(features || []).some((f) => f.dependencies?.length || f.related_features?.length) && (
              <div className="text-sm text-muted">No declared relationships yet.</div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
