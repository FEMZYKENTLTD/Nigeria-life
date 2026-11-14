import React, { useEffect, useState } from "react";

export function Card({ title, children, className = "", action }: {
  title?: string;
  children: React.ReactNode;
  className?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className={`card p-5 ${className}`}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {title && <h3 className="card-title">{title}</h3>}
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

export function Kpi({ label, value, sub, tone = "default" }: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  tone?: "default" | "gold" | "good" | "warn" | "bad";
}) {
  const toneCls = {
    default: "text-white",
    gold: "text-gold-soft",
    good: "text-good",
    warn: "text-warn",
    bad: "text-bad",
  }[tone];
  return (
    <div className="card p-4">
      <div className="card-title">{label}</div>
      <div className={`mt-1 text-2xl font-semibold tracking-tight ${toneCls}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-faint">{sub}</div>}
    </div>
  );
}

const STATUS_TONES: Record<string, string> = {
  // tasks
  complete: "bg-good/10 text-good border-good/30",
  running: "bg-info/10 text-info border-info/30",
  planned: "bg-info/10 text-info border-info/30",
  queued: "bg-muted/10 text-muted border-line",
  paused: "bg-warn/10 text-warn border-warn/30",
  waiting_decision: "bg-gold/10 text-gold-soft border-gold-dim/50",
  failed: "bg-bad/10 text-bad border-bad/30",
  cancelled: "bg-muted/10 text-muted border-line",
  // records
  documented: "bg-good/10 text-good border-good/30",
  pending: "bg-warn/10 text-warn border-warn/30",
  error: "bg-bad/10 text-bad border-bad/30",
  empty: "bg-muted/10 text-muted border-line",
  verified: "bg-good/10 text-good border-good/30",
  open: "bg-info/10 text-info border-info/30",
  superseded: "bg-muted/10 text-muted border-line",
  draft: "bg-warn/10 text-warn border-warn/30",
  approved: "bg-good/10 text-good border-good/30",
  rejected: "bg-bad/10 text-bad border-bad/30",
  authorised: "bg-good/10 text-good border-good/30",
  denied: "bg-bad/10 text-bad border-bad/30",
  unreachable: "bg-bad/10 text-bad border-bad/30",
  active: "bg-info/10 text-info border-info/30",
  aborted: "bg-muted/10 text-muted border-line",
  resolved: "bg-good/10 text-good border-good/30",
  dropped: "bg-muted/10 text-muted border-line",
  skipped: "bg-muted/10 text-muted border-line",
};

export function StatusPill({ status }: { status: string }) {
  const cls = STATUS_TONES[status] || "bg-muted/10 text-muted border-line";
  return (
    <span className={`badge border ${cls}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

export function ClassPill({ cls }: { cls: string }) {
  const map: Record<string, string> = {
    C: "bg-good/10 text-good border-good/30",
    I: "bg-info/10 text-info border-info/30",
    S: "bg-warn/10 text-warn border-warn/30",
    H: "bg-gold/10 text-gold-soft border-gold-dim/50",
    U: "bg-muted/10 text-muted border-line",
  };
  const label: Record<string, string> = {
    C: "confirmed", I: "inferred", S: "secondary", H: "hypothesis", U: "unknown",
  };
  return (
    <span className={`badge border ${map[cls] || map.U}`} title={label[cls]}>
      {cls}
    </span>
  );
}

export function Spinner() {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-gold" />
      <span className="text-sm">Loading…</span>
    </div>
  );
}

export function ErrorNote({ error }: { error: string }) {
  return (
    <div className="rounded-lg border border-bad/30 bg-bad/5 p-3 text-sm text-bad">
      {error}
    </div>
  );
}

export function useFetch<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    fn().then(
      (d) => { if (alive) { setData(d); setError(""); setLoading(false); } },
      (e) => { if (alive) { setError(e.message || String(e)); setLoading(false); } }
    );
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error, loading, reload: () => {
    setLoading(true);
    fn().then(
      (d) => { setData(d); setError(""); setLoading(false); },
      (e) => { setError(e.message || String(e)); setLoading(false); }
    );
  } };
}

export function fmtPct(x: number | null | undefined, digits = 1) {
  if (x === null || x === undefined) return "—";
  return `${(x * 100).toFixed(digits)}%`;
}

export function timeAgo(iso: string) {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return iso;
  const s = Math.max(1, Math.round((Date.now() - t) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return new Date(t).toLocaleDateString();
}
