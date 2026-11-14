// Tauri 2 desktop shell — single window around the dashboard.
// The FastAPI backend serves the built SPA (and the API) at one origin;
// the shell is intentionally logic-free.
use tauri::Manager;

const DEFAULT_APP_URL: &str = "http://127.0.0.1:8787";

pub fn run() {
    // Allow overriding the backend origin at runtime: RICE_APP_URL.
    let url = std::env::var("RICE_APP_URL").unwrap_or_else(|_| DEFAULT_APP_URL.to_string());

    tauri::Builder::default()
        .setup(move |app| {
            let window = app.get_webview_window("main").unwrap();
            // In dev, Tauri injects its own URL; in prod we load the
            // backend origin which serves frontend/dist at "/".
            if !cfg!(dev) {
                let _ = window.set_url(url);
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running the desktop application");
}
