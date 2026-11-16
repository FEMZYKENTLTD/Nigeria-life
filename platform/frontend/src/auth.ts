/** Auth: Supabase email+password (self-serve signup) when configured;
 * transparent local-operator mode otherwise (local-first development).
 *
 * The backend verifies the JWT (HS256) — this module only manages the
 * Supabase Auth session and hands API calls a fresh access token.
 */
const SUPABASE_URL: string = import.meta.env.VITE_SUPABASE_URL || "";
const SUPABASE_ANON: string = import.meta.env.VITE_SUPABASE_ANON_KEY || "";

const SESSION_KEY = "rice.session";
const USER_KEY = "rice.user";

export interface Session {
  access_token: string;
  refresh_token: string;
  expires_at: number; // epoch seconds
}

export interface Me {
  id: string;
  email: string;
  display_name: string;
  role: string; // admin | member
}

export function authRequired(): boolean {
  return Boolean(SUPABASE_URL && SUPABASE_ANON);
}

function head(): Record<string, string> {
  return {
    apikey: SUPABASE_ANON,
    Authorization: `Bearer ${SUPABASE_ANON}`,
    "Content-Type": "application/json",
  };
}

function jexp(token: string): number {
  try {
    const part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const pad = part.length % 4 ? "=".repeat(4 - (part.length % 4)) : "";
    return (JSON.parse(atob(part + pad)) as { exp?: number }).exp ?? 0;
  } catch {
    return 0;
  }
}

function store(s: Session | null): void {
  if (s) localStorage.setItem(SESSION_KEY, JSON.stringify(s));
  else localStorage.removeItem(SESSION_KEY);
}

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as Session;
    if (!s.access_token || (s.expires_at && s.expires_at * 1000 < Date.now())) return null;
    return s;
  } catch {
    return null;
  }
}

export function loadUser(): Me | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as Me) : null;
  } catch {
    return null;
  }
}

export function storeUser(u: Me | null): void {
  if (u) localStorage.setItem(USER_KEY, JSON.stringify(u));
  else localStorage.removeItem(USER_KEY);
}

let refreshPromise: Promise<Session | null> | null = null;

async function rawAuth(path: string, body: unknown, extraHeaders: Record<string, string> = {}): Promise<any> {
  const r = await fetch(`${SUPABASE_URL}/auth/v1${path}`, {
    method: "POST",
    headers: { ...head(), ...extraHeaders },
    body: JSON.stringify(body),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    const msg = (j as { msg?: string; error_description?: string }).msg ||
      (j as { error_description?: string }).error_description ||
      `auth error ${r.status}`;
    throw new Error(msg);
  }
  return j;
}

function toSession(j: { access_token: string; refresh_token?: string; expires_at?: number }): Session {
  return {
    access_token: j.access_token,
    refresh_token: j.refresh_token || "",
    expires_at: j.expires_at || jexp(j.access_token),
  };
}

/** Current access token, refreshing transparently near expiry. Null in
 * local mode (the backend then acts as the implicit local admin). */
export async function getAccessToken(): Promise<string | null> {
  if (!authRequired()) return null;
  const s = loadSession();
  if (!s) return null;
  if (s.expires_at && s.expires_at * 1000 - Date.now() < 60_000) {
    if (!refreshPromise) {
      refreshPromise = (async () => {
        if (!s.refresh_token) {
          store(null);
          return null;
        }
        try {
          const j = await rawAuth("/token?grant_type=refresh_token", {
            refresh_token: s.refresh_token,
          });
          const ns = toSession(j);
          store(ns);
          return ns;
        } catch {
          store(null);
          storeUser(null);
          return null;
        }
      })();
      refreshPromise.finally(() => {
        refreshPromise = null;
      });
    }
    const fresh = await refreshPromise;
    return fresh ? fresh.access_token : null;
  }
  return s.access_token;
}

export async function signIn(email: string, password: string): Promise<Me> {
  const j = await rawAuth("/token?grant_type=password", { email, password });
  store(toSession(j));
  return freshMe();
}

/** Self-serve signup. If email confirmation is on, the backend rejects
 * until confirmed — surface the honest message to the user. */
export async function signUp(email: string, password: string): Promise<{ user: Me | null; message: string }> {
  const j = await rawAuth("/signup", { email, password });
  if (j.access_token) {
    store(toSession(j));
    return { user: await freshMe(), message: "" };
  }
  return {
    user: null,
    message: "Account created — check your inbox to confirm the email, then sign in.",
  };
}

export async function signOut(): Promise<void> {
  const s = loadSession();
  if (s?.access_token) {
    try {
      await rawAuth("/logout", {}, { Authorization: `Bearer ${s.access_token}` });
    } catch {
      /* local logout is authoritative either way */
    }
  }
  store(null);
  storeUser(null);
}

/** Ask the backend who we are (profiles row — the role source of truth). */
async function freshMe(): Promise<Me> {
  const r = await fetch("/api/me", {
    headers: { Authorization: `Bearer ${loadSession()?.access_token ?? ""}` },
  });
  if (!r.ok) {
    store(null);
    throw new Error(`401: ${await r.text().catch(() => "")}`);
  }
  const u = (await r.json()) as Me;
  storeUser(u);
  return u;
}

export { freshMe };
