// Desktop shell: starts the Python engine as a child process, waits for it to listen,
// shows the dashboard in a native window, and stops the engine when the window closes.
// NOT COMPILED OR RUN YET: no Rust toolchain was available where this was written. See docs/engine/05-production-readiness.md.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::{Duration, Instant};

struct Engine(Mutex<Option<Child>>);

fn start_engine() -> std::io::Result<Child> {
    let python = std::env::var("NLIE_PYTHON").unwrap_or_else(|_| if cfg!(windows) { "python".into() } else { "python3".into() });
    let mut cmd = Command::new(python);
    cmd.args(["-m", "nlie", "--host", "127.0.0.1", "--port", "8765"]);
    if let Ok(dir) = std::env::var("NLIE_BACKEND_DIR") {
        cmd.current_dir(dir);
    }
    cmd.spawn()
}

fn wait_for_port(timeout: Duration) -> bool {
    let start = Instant::now();
    while start.elapsed() < timeout {
        if TcpStream::connect("127.0.0.1:8765").is_ok() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(200));
    }
    false
}

fn main() {
    let child = start_engine().expect("could not start the Python engine (set NLIE_PYTHON and NLIE_BACKEND_DIR)");
    if !wait_for_port(Duration::from_secs(30)) {
        eprintln!("engine did not start listening on 127.0.0.1:8765 within 30 seconds");
    }
    tauri::Builder::default()
        .manage(Engine(Mutex::new(Some(child))))
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                use tauri::Manager;
                if let Some(mut c) = window.state::<Engine>().0.lock().unwrap().take() {
                    let _ = c.kill();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running the desktop shell");
}
