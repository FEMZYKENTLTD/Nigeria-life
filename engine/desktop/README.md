# Desktop shell (Tauri 2) — not yet built

This folder holds the Tauri 2 configuration and a small Rust launcher that starts the Python engine and shows the dashboard in a native window.

**Status: written, never compiled.** The environment it was written in had no Rust toolchain and no access to crates.io. Expect to fix compile errors on first build.

To try it on a machine with Rust, Node 20+ and Python 3.11+:

```
cd engine/frontend && npm install && npm install -D @tauri-apps/cli@^2
cd ../desktop
npx --prefix ../frontend tauri icon path/to/a-1024px-logo.png      # creates src-tauri/icons
NLIE_BACKEND_DIR=$(pwd)/../backend NLIE_PYTHON=$(pwd)/../.venv/bin/python npx --prefix ../frontend tauri dev
```

Known gaps: no icon files are included; the Python runtime is not bundled, so an installer made from this would still need Python on the target machine (bundle it as a sidecar with PyInstaller before shipping).
