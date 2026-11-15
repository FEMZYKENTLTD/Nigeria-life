// Evidence Bridge — side panel logic.
// Manual-evidence path: the human looks at a page, then explicitly posts it.
// No background capture, ever: page reads and screenshots happen only inside
// this click handler, gated on the activeTab grant from the toolbar action.
const $ = (id) => document.getElementById(id);
const DEFAULT_API = "http://localhost:8787";

function log(msg) {
  const el = $("log");
  el.textContent = `[${new Date().toLocaleTimeString()}] ${msg}\n` + el.textContent;
}

async function apiBase() {
  const stored = await chrome.storage.local.get("apiBase");
  return (stored.apiBase || $("api").value || DEFAULT_API).replace(/\/+$/, "");
}

async function loadProjects() {
  const base = await apiBase();
  try {
    const r = await fetch(base + "/api/projects");
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    const projects = await r.json();
    const sel = $("project");
    sel.innerHTML = "";
    if (!projects.length) {
      sel.innerHTML = '<option value="">no projects yet</option>';
      return;
    }
    const stored = await chrome.storage.local.get("projectId");
    for (const p of projects) {
      const o = document.createElement("option");
      o.value = p.id;
      o.textContent = p.name;
      sel.appendChild(o);
    }
    sel.value = stored.projectId && projects.some((p) => p.id === stored.projectId)
      ? stored.projectId
      : projects[0].id;
  } catch (e) {
    log(`failed to load projects: ${e.message}`);
  }
}

async function refreshTabPreview() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) return;
    $("tab").textContent = `${tab.title || "(untitled)"}\n${tab.url || ""}`;
  } catch (e) {
    log(`tab preview: ${e.message}`);
  }
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.url || !/^https?:/.test(tab.url)) {
    throw new Error("the current tab is not an http(s) page");
  }
  return tab;
}

async function capturePage() {
  const base = await apiBase();
  const projectId = $("project").value;
  if (!projectId) return log("select a project first");
  let tab;
  try {
    tab = await activeTab();
  } catch (e) {
    return log(e.message);
  }
  try {
    const body = {
      url: tab.url,
      title: $("title").value || tab.title || "",
      notes: $("notes").value,
      status: "documented",
      evidence_class: "C",
      evidence_source: "manual-evidence bridge (side panel)",
    };
    if ($("withHtml").checked) {
      try {
        const res = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: () => document.documentElement.outerHTML,
        });
        body.html = res && res[0] ? res[0].result : "";
      } catch (e) {
        log(`HTML capture blocked (${e.message}). Click the toolbar icon to open the panel, then capture again.`);
      }
    }
    if ($("withShot").checked) {
      try {
        const dataUrl = await chrome.tabs.captureVisibleTab(null, { format: "png" });
        body.screenshot_b64 = dataUrl;
      } catch (e) {
        log(`screenshot blocked (${e.message}) — continuing without it`);
      }
    }
    const r = await fetch(base + `/api/projects/${projectId}/manual-captures`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    const out = await r.json();
    log(`captured ${tab.url} (page ${out.page_id.slice(0, 10)}…, evidence ${out.evidence_id.slice(0, 10)}…)`);
    $("notes").value = "";
    $("title").value = "";
  } catch (e) {
    log(`capture failed: ${e.message}`);
  }
}

async function postObservation() {
  const base = await apiBase();
  const projectId = $("project").value;
  const text = $("obsText").value.trim();
  if (!projectId || !text) return log("select a project and describe the observation");
  try {
    const tab = await activeTab().catch(() => null);
    const r = await fetch(base + `/api/projects/${projectId}/observations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: $("obsKind").value,
        observation: text,
        page_id: "",
        evidence_class: "I",
        confidence: Number($("obsConf").value || 0.5),
        status: "open",
      }),
    });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    $("obsText").value = "";
    log(`observation posted (tab: ${tab ? tab.url : "n/a"})`);
  } catch (e) {
    log(`observation failed: ${e.message}`);
  }
}

// wiring
(async () => {
  const base = await chrome.storage.local.get("apiBase");
  $("api").value = (base.apiBase || DEFAULT_API).replace(/\/+$/, "");
  await loadProjects();
  await refreshTabPreview();
})();

$("api").addEventListener("change", async (e) => {
  await chrome.storage.local.set({ apiBase: e.target.value.replace(/\/+$/, "") });
  await loadProjects();
});
$("project").addEventListener("change", async (e) => {
  await chrome.storage.local.set({ projectId: e.target.value });
});
$("capture").addEventListener("click", capturePage);
$("addObs").addEventListener("click", () => {
  $("obsWrap").classList.toggle("hidden");
});
$("obsSend").addEventListener("click", postObservation);
window.addEventListener("focus", refreshTabPreview);
