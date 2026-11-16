import { ReactNode, useEffect, useState } from "react";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { api, Project } from "./api";
import { authRequired, loadSession, signOut, type Me } from "./auth";
import Overview from "./pages/Overview";
import Workspace from "./pages/Workspace";
import Access from "./pages/Access";
import AgentCentre from "./pages/AgentCentre";
import Browsers from "./pages/Browsers";
import Knowledge from "./pages/Knowledge";
import Analytics from "./pages/Analytics";
import Reports from "./pages/Reports";
import GitHub from "./pages/GitHub";
import DataOps from "./pages/DataOps";
import Login from "./pages/Login";
import Users from "./pages/Users";
import { Spinner, useFetch } from "./components/ui";

const NAV = [
  { to: "/", label: "Overview", icon: "◈" },
  { to: "/workspace", label: "Research Workspace", icon: "⌘" },
  { to: "/agent", label: "AI Agent Centre", icon: "✦" },
  { to: "/access", label: "Data & Access", icon: "⛨" },
  { to: "/browsers", label: "Browser Management", icon: "▣" },
  { to: "/knowledge", label: "Knowledge Base", icon: "❖" },
  { to: "/analytics", label: "Analytics", icon: "◍" },
  { to: "/reports", label: "Reports", icon: "≡" },
  { to: "/github", label: "GitHub Integration", icon: "⎇" },
  { to: "/data", label: "Data & Ops", icon: "◫" },
];

const ADMIN_NAV = [{ to: "/users", label: "Users & Activity", icon: "⚉" }];

function ProjectBar() {
  const { data: projects, reload } = useFetch(() => api.projects(), []);
  const [selected, setSelected] = useState<string>("");
  useEffect(() => {
    const saved = localStorage.getItem("rice.project");
    if (saved && projects?.some((p) => p.id === saved)) setSelected(saved);
    else if (projects?.length) setSelected(projects[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projects]);
  useEffect(() => {
    if (selected) localStorage.setItem("rice.project", selected);
  }, [selected]);
  return (
    <div className="flex items-center gap-3">
      <span className="text-[11px] uppercase tracking-[0.14em] text-faint">Project</span>
      <select
        className="input !w-auto min-w-56"
        value={selected}
        onChange={(e) => setSelected(e.target.value)}
      >
        {!projects?.length && <option value="">No projects yet</option>}
        {projects?.map((p: Project) => (
          <option key={p.id} value={p.id}>{p.name}</option>
        ))}
      </select>
      <button className="btn" onClick={() => reload()}>↻</button>
    </div>
  );
}

function selectedProjectId() {
  return localStorage.getItem("rice.project") || "";
}

function UsersGate({ me, children }: { me: Me; children: ReactNode }) {
  if (me.role !== "admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [booted, setBooted] = useState(false);

  useEffect(() => {
    if (!authRequired()) {
      // local-first: single local operator, implicit admin
      setMe({ id: "local", email: "local@rice.local", display_name: "Local operator", role: "admin" });
      setBooted(true);
      return;
    }
    if (!loadSession()) {
      setBooted(true);
      return;
    }
    api
      .me()
      .then((u) => setMe(u))
      .catch(() => {
        // stale/invalid session → force re-login
        void signOut();
        setMe(null);
      })
      .finally(() => setBooted(true));
  }, []);

  if (!booted) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink">
        <Spinner />
      </div>
    );
  }

  if (authRequired() && !me) {
    return <Login onAuthed={setMe} />;
  }

  const user = me!;
  const nav = user.role === "admin" ? [...NAV, ...ADMIN_NAV] : NAV;
  const { data: health } = useFetch(() => api.health(), []);

  return (
    <div className="flex min-h-screen bg-ink">
      {/* sidebar */}
      <aside className="fixed inset-y-0 left-0 z-20 flex w-60 flex-col border-r border-line bg-charcoal/60 backdrop-blur">
        <div className="border-b border-line px-5 py-5">
          <div className="text-[10px] uppercase tracking-[0.3em] text-gold">Nigeria Life</div>
          <div className="mt-1 text-sm font-semibold tracking-wide text-white">
            Intelligence Engine
          </div>
          <div className="mt-2 text-[11px] leading-relaxed text-faint">
            Autonomous website research, intelligence &amp; analysis
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-4">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                  isActive
                    ? "bg-gold-dim/15 text-gold-soft"
                    : "text-muted hover:bg-panel hover:text-white"
                }`
              }
            >
              <span className="w-4 text-center opacity-80">{n.icon}</span>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-line px-5 py-3 text-[10px] leading-relaxed text-faint">
          {user.id !== "local" && (
            <div className="mb-2 flex items-center gap-2">
              <div className="min-w-0 flex-1">
                <div className="truncate text-[12px] font-medium text-white">
                  {user.display_name || user.email}
                </div>
                <div className="truncate text-[10px]">
                  {user.email} · {user.role}
                </div>
              </div>
              <button
                className="btn !px-2 !py-1 text-[10px]"
                onClick={() => {
                  void signOut().then(() => setMe(null));
                }}
                title="Sign out"
              >
                Sign out
              </button>
            </div>
          )}
          <div className="flex items-center gap-2">
            <span className={`h-1.5 w-1.5 rounded-full ${health ? "bg-good" : "bg-bad"}`} />
            {health ? `API online · AI: ${health.ai_provider}` : "API offline"}
          </div>
          <div className="mt-1">
            Scores are computed, never arbitrary. Findings carry evidence.
          </div>
        </div>
      </aside>

      {/* main */}
      <div className="ml-60 flex-1">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-ink/85 px-6 py-3 backdrop-blur">
          <ProjectBar />
          <div className="text-[11px] text-faint">
            {new Date().toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}
          </div>
        </header>
        <main className="p-6">
          <Routes>
            <Route path="/" element={<Overview pid={selectedProjectId()} />} />
            <Route path="/workspace" element={<Workspace pid={selectedProjectId()} />} />
            <Route path="/agent" element={<AgentCentre pid={selectedProjectId()} />} />
            <Route path="/access" element={<Access pid={selectedProjectId()} />} />
            <Route path="/browsers" element={<Browsers pid={selectedProjectId()} />} />
            <Route path="/knowledge" element={<Knowledge pid={selectedProjectId()} />} />
            <Route path="/analytics" element={<Analytics pid={selectedProjectId()} />} />
            <Route path="/reports" element={<Reports pid={selectedProjectId()} />} />
            <Route path="/github" element={<GitHub pid={selectedProjectId()} />} />
            <Route path="/data" element={<DataOps pid={selectedProjectId()} />} />
            <Route
              path="/users"
              element={
                <UsersGate me={user}>
                  <Users />
                </UsersGate>
              }
            />
            <Route path="/login" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export { selectedProjectId };
export type { ReactNode };
