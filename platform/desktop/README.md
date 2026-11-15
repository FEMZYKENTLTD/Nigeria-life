# Tauri 2 Desktop Shell — Nigeria Life Intelligence Engine

A thin native window that wraps the dashboard. The engine is the FastAPI
backend; this shell either (a) points at a locally running backend, or (b)
embeds it. **This is scaffolding + instructions, not a pre-built binary.**
Packaging/installers must be produced on each target OS (a Windows or macOS
installer cannot be built from a Linux host).

> Status: scaffold only. No `.exe`/`.dmg`/`.AppImage` is committed. Build and
> verify on the target OS per the steps below.

## What it does

- Opens a single Tauri window loading the dashboard from the backend origin
  (default `http://127.0.0.1:8787`), which serves the built SPA at `/`.
- Sidebar menu with standard window actions; no extra surface area.
- All intelligence lives in the backend — the shell adds no logic, so there
  is nothing to test beyond "window opens, dashboard loads".

## Layout

```
platform/desktop/
├── README.md            # this file
├── Cargo.toml           # workspace crate (tauri 2)
├── tauri.conf.json      # window + dev/prod frontend config
└── src/
    └── main.rs          # minimal entry: default Tauri builder
```

The frontend is **not** duplicated here — Tauri loads the already-built
`platform/frontend/dist` (or the running dev server during `dev`).

## Prerequisites (per target OS)

1. Rust (stable) + the platform C toolchain
   (Linux: `build-essential`/`libwebkit2gtk-4.1-dev`; macOS: Xcode CLT;
   Windows: MSVC).
2. Node (already used by the dashboard) to build the frontend once.

## Build the frontend once

```
cd platform/frontend
npm ci
npm run build        # -> platform/frontend/dist
```

## Develop (hot reload)

```
cd platform/desktop
npm create tauri@latest -- --template vanilla   # only if you need the npm deps
# or, if you already have the cargo workspace:
cargo tauri dev
```

`cargo tauri dev` starts Vite (frontend dev) + the Rust shell and points the
window at the dev server; the API proxy in `frontend/vite.config.ts` routes
`/api` to `:8787`.

## Package an installer (per OS)

```
cd platform/desktop
cargo tauri build
```

- **Linux** → `.AppImage` / `.deb` in `target/release/bundle/`
- **macOS** → `.dmg` / `.app` (requires macOS; code-sign for distribution)
- **Windows** → `.msi` / `.exe` (requires Windows or cross-compile with
  NSIS; not producible from this Linux sandbox)

Set `bundle.identifier` in `tauri.conf.json` to your domain before release.

## Embedding the backend (optional)

By default the shell assumes the FastAPI app is running on `:8787`. To make
the desktop app self-contained, compile the backend as a sidecar and have
`main.rs` spawn it on startup, waiting for `GET /api/health` before showing
the window. That wiring is intentionally left out of the scaffold to keep it
buildable everywhere; add it in `src/main.rs` behind a `#[cfg]` flag when you
target a specific OS.
