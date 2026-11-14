import { useState, type ReactNode } from "react";

export function Card({ title, action, children, className = "" }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`bg-coal border border-line rounded-md ${className}`}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-3 px-4 py-3 border-b border-line">
          <h3 className="text-[15px] text-bone">{title}</h3>
          {action}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="bg-coal border border-line rounded-md px-4 py-3">
      <div className="text-[11px] uppercase tracking-[0.1em] text-mute">{label}</div>
      <div className="font-display text-3xl text-bone num mt-1">{value}</div>
      {hint && <div className="text-xs text-mute mt-1">{hint}</div>}
    </div>
  );
}

const tones: Record<string, string> = {
  confirmed: "text-ok border-ok/40", done: "text-ok border-ok/40", analysed: "text-ok border-ok/40", approved: "text-ok border-ok/40", verified: "text-ok border-ok/40", ok: "text-ok border-ok/40", active: "text-ok border-ok/40", answered: "text-ok border-ok/40",
  secondary: "text-warn border-warn/40", inference: "text-warn border-warn/40", queued: "text-warn border-warn/40", pending: "text-warn border-warn/40", blocked: "text-warn border-warn/40", paused: "text-warn border-warn/40", warn: "text-warn border-warn/40", open: "text-warn border-warn/40", thin: "text-warn border-warn/40",
  failed: "text-bad border-bad/40", error: "text-bad border-bad/40", rejected: "text-bad border-bad/40", missing: "text-bad border-bad/40", broken_link: "text-bad border-bad/40",
  running: "text-gold border-gold/50",
};

export function Badge({ children, tone }: { children: ReactNode; tone?: string }) {
  const key = tone ?? String(children);
  return <span className={`inline-block text-[11px] leading-5 px-2 rounded-sm border whitespace-nowrap ${tones[key] ?? "text-mute border-line"}`}>{String(children).replace(/_/g, " ")}</span>;
}

export function Button({ children, onClick, kind = "ghost", disabled, type = "button", small }: { children: ReactNode; onClick?: () => void; kind?: "primary" | "ghost" | "danger"; disabled?: boolean; type?: "button" | "submit"; small?: boolean }) {
  const k = kind === "primary" ? "bg-gold text-ink border-gold hover:bg-[#d4b46f]" : kind === "danger" ? "text-bad border-bad/40 hover:bg-bad/10" : "text-bone border-line hover:border-golddim hover:text-gold";
  return (
    <button type={type} onClick={onClick} disabled={disabled}
      className={`${small ? "px-2.5 py-1 text-xs" : "px-3.5 py-1.5 text-[13px]"} rounded border font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer ${k}`}>
      {children}
    </button>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-mute text-[13px] py-6 text-center">{children}</p>;
}

export function Notice({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warn" | "bad" | "ok" }) {
  const c = tone === "warn" ? "border-warn/40 text-warn" : tone === "bad" ? "border-bad/40 text-bad" : tone === "ok" ? "border-ok/40 text-ok" : "border-line text-mute";
  return <div role={tone === "bad" ? "alert" : "status"} className={`border rounded px-3 py-2 text-[13px] ${c}`}>{children}</div>;
}

export function State({ loading, error, children }: { loading: boolean; error: string; children: ReactNode }) {
  if (error) return <Notice tone="bad">Could not load: {error}</Notice>;
  if (loading) return <p className="text-mute text-[13px] py-6">Loading…</p>;
  return <>{children}</>;
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: readonly (readonly [T, string])[]; value: T; onChange: (t: T) => void }) {
  return (
    <div role="tablist" className="flex flex-wrap gap-1 border-b border-line mb-4">
      {tabs.map(([id, label]) => (
        <button key={id} role="tab" aria-selected={value === id} onClick={() => onChange(id)}
          className={`px-3 py-2 text-[13px] -mb-px border-b-2 cursor-pointer ${value === id ? "border-gold text-gold" : "border-transparent text-mute hover:text-bone"}`}>
          {label}
        </button>
      ))}
    </div>
  );
}

export function PageTitle({ title, sub, action }: { title: string; sub?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
      <div>
        <h1 className="text-[28px] leading-tight text-bone">{title}</h1>
        {sub && <p className="text-mute text-[13px] mt-1 max-w-[70ch]">{sub}</p>}
      </div>
      {action}
    </div>
  );
}

export function Scroll({ children, max = 520 }: { children: ReactNode; max?: number }) {
  return <div className="overflow-auto -mx-4 -my-4" style={{ maxHeight: max }}>{children}</div>;
}

/** Runs an async action, showing the outcome inline. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);
  const run = async (fn: () => Promise<unknown>, okText = "Done.") => {
    setBusy(true); setMsg(null);
    try { await fn(); setMsg({ tone: "ok", text: okText }); return true; }
    catch (e) { setMsg({ tone: "bad", text: (e as Error).message }); return false; }
    finally { setBusy(false); }
  };
  return { busy, run, note: msg && <Notice tone={msg.tone}>{msg.text}</Notice> };
}
