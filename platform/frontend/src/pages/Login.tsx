import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";
import { authRequired, freshMe, loadSession, signIn, signUp, type Me } from "../auth";
import { ErrorNote } from "../components/ui";

export default function Login({ onAuthed }: { onAuthed: (u: Me) => void }) {
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  // already signed in → go to the dashboard
  if (authRequired() && loadSession()) return <Navigate to="/" replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setInfo("");
    try {
      if (mode === "in") {
        onAuthed(await signIn(email.trim(), password));
      } else {
        const r = await signUp(email.trim(), password);
        if (r.user) {
          onAuthed(r.user);
        } else {
          setInfo(r.message);
          setMode("in");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink p-6">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="text-[10px] uppercase tracking-[0.3em] text-gold">Nigeria Life</div>
          <div className="mt-1 text-xl font-semibold tracking-wide text-white">
            Intelligence Engine
          </div>
          <div className="mt-2 text-[12px] leading-relaxed text-faint">
            Autonomous website research, intelligence &amp; analysis.
            Scores are computed, never arbitrary — findings carry evidence.
          </div>
        </div>

        <div className="card p-6">
          <div className="mb-5 flex rounded-lg border border-line bg-charcoal p-1 text-sm">
            {(["in", "up"] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => { setMode(m); setError(""); setInfo(""); }}
                className={`flex-1 rounded-md py-1.5 transition ${
                  mode === m ? "bg-panel2 text-gold-soft" : "text-muted hover:text-white"
                }`}
              >
                {m === "in" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-[11px] uppercase tracking-[0.14em] text-faint">
                Email
              </label>
              <input
                className="input"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-[11px] uppercase tracking-[0.14em] text-faint">
                Password
              </label>
              <input
                className="input"
                type="password"
                required
                minLength={6}
                autoComplete={mode === "in" ? "current-password" : "new-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>

            {error && <ErrorNote error={error} />}
            {info && (
              <div className="rounded-lg border border-good/30 bg-good/5 p-3 text-sm text-good">
                {info}
              </div>
            )}

            <button className="btn btn-gold w-full justify-center !py-2.5" disabled={busy}>
              {busy ? "Working…" : mode === "in" ? "Sign in" : "Create account"}
            </button>
          </form>

          <p className="mt-4 text-[11px] leading-relaxed text-faint">
            {mode === "up"
              ? "Self-serve: your account is created in Supabase Auth and verified on every request. Your projects are private to you."
              : "Each account sees only its own projects. An admin account can see every user's scraping activity and results."}
          </p>
        </div>
      </div>
    </div>
  );
}

export { freshMe };
