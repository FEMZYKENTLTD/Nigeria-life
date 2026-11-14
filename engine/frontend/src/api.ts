import { useCallback, useEffect, useRef, useState } from "react";

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  const r = await fetch(`/api${path}`, {
    method: opts.method ?? (opts.body ? "POST" : "GET"),
    headers: opts.body ? { "Content-Type": "application/json" } : undefined,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch { /* keep status text */ }
    throw new Error(msg);
  }
  return r.json();
}

/** Loads a resource, optionally refreshing on an interval. Keeps the last good data while refreshing. */
export function useData<T = any>(path: string | null, refreshMs = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(!!path);
  const current = useRef(path);
  current.current = path;
  const reload = useCallback(async () => {
    if (!path) return;
    try {
      const d = await api<T>(path);
      if (current.current === path) { setData(d); setError(""); }
    } catch (e) {
      if (current.current === path) setError((e as Error).message);
    } finally {
      if (current.current === path) setLoading(false);
    }
  }, [path]);
  useEffect(() => {
    setData(null); setLoading(!!path);
    reload();
    if (!refreshMs || !path) return;
    const t = setInterval(reload, refreshMs);
    return () => clearInterval(t);
  }, [path, refreshMs, reload]);
  return { data, error, loading, reload };
}

export const when = (iso?: string | null) => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—");
