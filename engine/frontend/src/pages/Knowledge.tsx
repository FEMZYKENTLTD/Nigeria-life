import { useState } from "react";
import { api } from "../api";
import type { PageProps } from "../App";
import { Badge, Button, Card, Empty, PageTitle, useAction } from "../ui";

const TYPES = ["feature", "finding", "page", "evidence", "question", "decision"];

export default function Knowledge({ pid }: PageProps) {
  const [q, setQ] = useState("");
  const [types, setTypes] = useState<string[]>([]);
  const [res, setRes] = useState<any>(null);
  const act = useAction();
  const go = () => act.run(async () => setRes(await api(`/projects/${pid}/search?q=${encodeURIComponent(q)}&types=${types.join(",")}`)), "");
  return (
    <>
      <PageTitle title="Knowledge Base" sub="Search across features, findings, pages, evidence, questions and decisions. Matching is by shared words weighted by rarity; it is not meaning-based search." />
      <Card>
        <form className="flex flex-wrap gap-2 items-center" onSubmit={(e) => { e.preventDefault(); go(); }}>
          <input aria-label="Search the knowledge base" required className="!flex-1 !min-w-[240px] !w-auto" placeholder="e.g. billboard advertising price" value={q} onChange={(e) => setQ(e.target.value)} />
          <Button type="submit" kind="primary" disabled={act.busy}>Search</Button>
          <div className="basis-full flex flex-wrap gap-3 text-[13px]">
            {TYPES.map((t) => <label key={t} className="flex items-center gap-1.5 !mb-0 !text-[13px]"><input type="checkbox" checked={types.includes(t)} onChange={(e) => setTypes(e.target.checked ? [...types, t] : types.filter((x) => x !== t))} />{t}s</label>)}
            <span className="text-mute">{types.length ? "" : "All types"}</span>
          </div>
        </form>
      </Card>
      <div className="mt-5">
        {res && (res.results.length ? (
          <ul className="space-y-2">
            {res.results.map((r: any) => (
              <li key={`${r.type}-${r.id}`} className="bg-coal border border-line rounded-md p-4">
                <div className="flex flex-wrap items-center gap-2"><Badge tone="x">{r.type}</Badge><span className="text-bone">{r.title}</span>{r.confidence && <Badge>{r.confidence}</Badge>}
                  <span className="ml-auto text-xs text-mute num" title="Cosine similarity of TF-IDF vectors, 0 to 1">match {r.score.toFixed(3)}</span></div>
                <p className="text-[13px] text-mute mt-1.5">{r.snippet}</p>
                <div className="text-xs text-mute mt-1.5">Matched words: {r.matched_terms.join(", ")}{r.evidence.length ? ` · Evidence: ${r.evidence.join(", ")}` : ""}</div>
              </li>
            ))}
          </ul>
        ) : <Empty>Nothing in this project contains those words. Try different or fewer words.</Empty>)}
      </div>
    </>
  );
}
