import { useEffect, useState } from "react";
import { useData } from "./api";
import { Badge, Notice } from "./ui";
import Overview from "./pages/Overview";
import Workspace from "./pages/Workspace";
import Agent from "./pages/Agent";
import Browser from "./pages/Browser";
import Knowledge from "./pages/Knowledge";
import Analytics from "./pages/Analytics";
import Reports from "./pages/Reports";
import GitHub from "./pages/GitHub";

const NAV = [
  ["overview", "Overview"], ["workspace", "Research Workspace"], ["agent", "Agent Centre"], ["browser", "Browser Management"],
  ["knowledge", "Knowledge Base"], ["analytics", "Analytics"], ["reports", "Reports"], ["github", "GitHub"],
] as const;
type Section = (typeof NAV)[number][0];
export type PageProps = { pid: number; project: any; reloadProjects: () => void };

export default function App() {
  const projects = useData<any[]>("/projects", 5000);
  const [pid, setPid] = useState<number | null>(null);
  const [section, setSection] = useState<Section>(() => (NAV.find(([id]) => id === location.hash.slice(1))?.[0] ?? "overview"));
  const pending = useData<any[]>(pid ? `/approvals?project_id=${pid}&status=pending` : null, 5000);

  useEffect(() => {
    if (projects.data?.length && (pid === null || !projects.data.some((p) => p.id === pid))) setPid(projects.data[0].id);
  }, [projects.data, pid]);
  useEffect(() => { history.replaceState(null, "", `#${section}`); }, [section]);

  const project = projects.data?.find((p) => p.id === pid);
  const Page = { overview: Overview, workspace: Workspace, agent: Agent, browser: Browser, knowledge: Knowledge, analytics: Analytics, reports: Reports, github: GitHub }[section];

  return (
    <div className="min-h-full md:grid md:grid-cols-[232px_1fr]">
      <aside className="bg-coal border-b md:border-b-0 md:border-r border-line md:sticky md:top-0 md:h-screen flex flex-col">
        <div className="px-5 pt-5 pb-4 border-b border-line">
          <div className="text-[10px] tracking-[0.22em] uppercase text-gold">Nigeria Life</div>
          <div className="font-display text-xl text-bone leading-tight mt-0.5">Intelligence Engine</div>
        </div>
        <div className="px-4 py-3 border-b border-line">
          <label htmlFor="project">Project</label>
          <select id="project" value={pid ?? ""} onChange={(e) => setPid(Number(e.target.value))}>
            {projects.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
        <nav aria-label="Sections" className="flex md:flex-col overflow-x-auto md:overflow-visible p-2 gap-0.5 flex-1">
          {NAV.map(([id, label]) => (
            <button key={id} onClick={() => setSection(id)} aria-current={section === id ? "page" : undefined}
              className={`text-left whitespace-nowrap px-3 py-2 rounded text-[13px] cursor-pointer flex items-center justify-between gap-2 ${section === id ? "bg-slate text-gold" : "text-mute hover:text-bone hover:bg-slate/60"}`}>
              {label}
              {id === "agent" && !!pending.data?.length && <span className="text-[10px] bg-gold text-ink rounded-full px-1.5 num" title="Decisions waiting for you">{pending.data.length}</span>}
            </button>
          ))}
        </nav>
        {project && <div className="hidden md:block px-5 py-3 border-t border-line text-xs text-mute">Project is <Badge>{project.status}</Badge></div>}
      </aside>
      <main className="p-5 md:p-8 min-w-0 max-w-[1400px]">
        {projects.error && <Notice tone="bad">The engine is not responding: {projects.error}</Notice>}
        {projects.data && !projects.data.length && <Notice>No projects yet. Create one from Overview.</Notice>}
        {section === "overview" && !project && projects.data && <Overview pid={0} project={null} reloadProjects={projects.reload} />}
        {project && pid && <Page key={`${section}-${pid}`} pid={pid} project={project} reloadProjects={projects.reload} />}
      </main>
    </div>
  );
}
