// Typed API client. All calls are relative URLs — same origin in production,
// proxied in dev.
async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const j = await r.json();
      detail = j.detail || JSON.stringify(j);
    } catch {
      /* ignore */
    }
    throw new Error(`${r.status}: ${detail}`);
  }
  return r.json() as Promise<T>;
}

const post = <T = unknown>(path: string, body?: unknown): Promise<T> =>
  req<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const patch = <T = unknown>(path: string, body: unknown): Promise<T> =>
  req<T>(path, { method: "PATCH", body: JSON.stringify(body) });

export interface Project {
  id: string;
  name: string;
  slug: string;
  description: string;
  industry: string;
  target_base_url: string;
  status: string;
  permissions: Record<string, unknown>;
  repo_url: string;
  counts?: Record<string, number>;
}

export interface Overview {
  projects: Project[];
  totals: Record<string, number>;
  recent_activity: {
    id: string;
    project_id: string;
    actor: string;
    action: string;
    subject: string;
    detail: string;
    ts: string;
  }[];
}

export interface Task {
  id: string;
  project_id: string;
  title: string;
  objective: string;
  status: string;
  priority: number;
  progress: number;
  error: string;
  result_summary: string;
  subtasks?: {
    id: string;
    idx: number;
    type: string;
    description: string;
    status: string;
    attempts: number;
    last_error: string;
    requires_approval: boolean;
  }[];
  running?: boolean;
}

export interface Decision {
  id: string;
  project_id: string;
  task_id: string;
  kind: string;
  question: string;
  status: string;
  created_at: string;
}

export interface PageRecord {
  id: string;
  url: string;
  title: string;
  status: string;
  content_category: string;
  purpose: string;
  summary: string;
  capture_method: string;
  observed_at: string;
  error: string;
  evidence_refs?: string[];
}

export interface Feature {
  id: string;
  name: string;
  category: string;
  description: string;
  purpose: string;
  access_location: string;
  limitations: string;
  opportunities: string;
  dependencies: string[];
  related_features: string[];
  confidence: number;
  status: string;
  evidence_refs?: string[];
  evidence_ids?: string[];
}

export interface Evidence {
  id: string;
  ref_code: string;
  evidence_class: string;
  source_uri: string;
  source_name: string;
  capture_method: string;
  description: string;
  cited_by: string[];
}

export interface Report {
  id: string;
  type: string;
  title: string;
  format: string;
  content: string;
  generated_at: string;
  chars?: number;
}

export const api = {
  health: () => req<{ status: string; ai_provider: string; db: string }>("/api/health"),
  overview: () => req<Overview>("/api/overview"),
  projects: () => req<Project[]>("/api/projects"),
  createProject: (body: Partial<Project>) => post<Project>("/api/projects", body),
  project: (id: string) => req<Project & { tasks: Task[] }>(`/api/projects/${id}`),
  deleteProject: (id: string, confirm: string) =>
    req(`/api/projects/${id}?confirm=${encodeURIComponent(confirm)}`, { method: "DELETE" }),

  tasks: (pid: string) => req<Task[]>(`/api/projects/${pid}/tasks`),
  createTask: (pid: string, body: { title: string; objective: string; priority?: number }) =>
    post<Task>(`/api/projects/${pid}/tasks`, body),
  runTask: (id: string) => post(`/api/tasks/${id}/run`),
  pauseTask: (id: string) => post(`/api/tasks/${id}/pause`),
  cancelTask: (id: string) => post(`/api/tasks/${id}/cancel`),

  decisions: (pid: string) => req<Decision[]>(`/api/projects/${pid}/decisions`),
  decide: (id: string, verdict: "approve" | "reject") =>
    post(`/api/decisions/${id}/${verdict}`),

  agentStatus: () => req<{
    active_tasks: Task[];
    queue: Task[];
    failed: Task[];
    complete: Task[];
    pending_decisions: Decision[];
    recent_runs: { id: string; mode: string; status: string; started_at: string }[];
    ai_provider: string;
  }>("/api/agent/status"),
  agentLogs: (n = 60) => req<{ action: string; subject: string; detail: string; ts: string }[]>(
    `/api/agent/logs?limit=${n}`
  ),

  pages: (pid: string, q = "") => req<PageRecord[]>(`/api/projects/${pid}/pages?q=${encodeURIComponent(q)}`),
  features: (pid: string) => req<Feature[]>(`/api/projects/${pid}/features`),
  evidence: (pid: string) => req<Evidence[]>(`/api/projects/${pid}/evidence`),
  observations: (pid: string) =>
    req<{ id: string; kind: string; observation: string; key: string; value: string; evidence_class: string; confidence: number; status: string; created_at: string }[]>(
      `/api/projects/${pid}/observations`
    ),
  questions: (pid: string) =>
    req<{ id: string; question: string; context: string; status: string }[]>(
      `/api/projects/${pid}/questions`
    ),
  sources: (pid: string) =>
    req<{ id: string; name: string; url: string; domain: string; status: string; notes: string }[]>(
      `/api/projects/${pid}/sources`
    ),

  analytics: (pid: string) => req<Record<string, any>>(`/api/projects/${pid}/analytics`),
  reports: (pid: string) => req<Report[]>(`/api/projects/${pid}/reports`),
  reportTypes: () => req<Record<string, string>>("/api/reports/types"),
  generateReport: (pid: string, type: string, format: string) =>
    post<{ id: string; title: string }>(`/api/projects/${pid}/reports/generate`, { type, format }),
  report: (id: string) => req<Report>(`/api/reports/${id}`),

  search: (pid: string, query: string, limit = 15) =>
    post<{ query: string; count: number; results: { score: number; kind: string; title: string; snippet: string; ref_id: string }[]; explanation: string }>(
      `/api/projects/${pid}/knowledge/search`,
      { query, limit }
    ),

  browserHealth: (refresh = false) =>
    req<{ engine: string; installed: boolean; version: string; error: string; checked_at?: string }[]>(
      `/api/browsers/health?refresh=${refresh}`
    ),
  profiles: () =>
    req<{ id: string; name: string; engine: string; viewports: { name: string; width: number; height: number }[] }[]>(
      "/api/browsers/profiles"
    ),
  createProfile: (body: { name: string; engine: string; project_id?: string }) =>
    post("/api/browsers/profiles", body),
  sessions: (pid = "") =>
    req<{ id: string; project_id: string; engine: string; mode: string; status: string; summary: Record<string, unknown>; error: string; started_at: string }[]>(
      `/api/sessions?project_id=${pid}`
    ),
  sessionLog: (id: string) =>
    req<{ level: string; event: string; message: string; ts: string; engine: string }[]>(
      `/api/sessions/${id}/log`
    ),

  githubStatus: () =>
    req<{
      connected: boolean;
      info: Record<string, string>;
      commits: { sha: string; date: string; author: string; message: string }[];
      branches: string[];
      docs_tree: { path: string; size: number }[];
    }>("/api/github/status"),
  githubSync: () => post<{ synced: boolean; docs: number; digest: string }>("/api/github/sync"),
};
