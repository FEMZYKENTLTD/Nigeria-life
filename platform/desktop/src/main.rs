// Desktop shell entry point. All logic lives in the backend; the window
// just loads the dashboard. See README.md for build/package instructions.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    rice_desktop_lib::run()
}
