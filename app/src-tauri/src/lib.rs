// this hides the console for Windows release builds
#![cfg_attr(
  all(not(debug_assertions), target_os = "windows"),
  windows_subsystem = "windows"
)]

use serde::Serialize;
use std::sync::Mutex;
use tauri::{
  // state is used in Linux
  self,
  Emitter,
  Manager,
};
use tauri_plugin_store;
use tauri_plugin_window_state;

mod tray_icon;
mod utils;

use tray_icon::{create_tray_icon, tray_update_lang, TrayState};
use utils::long_running_thread;

#[derive(Clone, Serialize)]
struct SingleInstancePayload {
  args: Vec<String>,
  cwd: String,
}

#[derive(Debug)]
struct MusicCasterState(Mutex<Option<std::process::Child>>);

#[derive(Debug, Default, Serialize)]
struct Example<'a> {
  #[serde(rename = "Attribute 1")]
  attribute_1: &'a str,
}

#[cfg(target_os = "linux")]
pub struct DbusState(Mutex<Option<dbus::blocking::SyncConnection>>);

#[tauri::command]
fn process_file(filepath: String) -> String {
  println!("Processing file: {}", filepath);
  "Hello from Rust!".into()
}

#[tauri::command]
async fn start_music_caster(app_handle: tauri::AppHandle) -> Result<String, String> {
  use std::process::{Command, Stdio};

  // Check if it's already running
  let state = app_handle.state::<MusicCasterState>();
  if let Ok(guard) = state.0.lock() {
    if guard.is_some() {
      return Err("Music Caster is already running".to_string());
    }
  }

  // Use the bundled binary - tauri handles path resolution for externalBin
  #[cfg(debug_assertions)]
  let exe_path = std::path::PathBuf::from("../../dist/Music Caster.exe");

  #[cfg(not(debug_assertions))]
  let exe_path = String::from("Music Caster");

  println!("Starting Music Caster from: {:?}", exe_path);

  #[cfg(debug_assertions)]
  println!("Exe path exists: {}", exe_path.exists());

  // Spawn the process
  let child = std::process::Command::new(&exe_path)
    .stdout(std::process::Stdio::null())
    .stderr(std::process::Stdio::null())
    .spawn()
    .map_err(|e| format!("Failed to start Music Caster: {}", e))?;

  // Store the child process
  *app_handle
    .state::<MusicCasterState>()
    .0
    .lock()
    .map_err(|e| format!("State lock error: {}", e))? = Some(child);

  Ok("Music Caster started successfully".to_string())
}

#[tauri::command]
async fn stop_music_caster(app_handle: tauri::AppHandle) -> Result<String, String> {
  let state = app_handle.state::<MusicCasterState>();
  let mut guard = state.0.lock().map_err(|e| format!("State lock error: {}", e))?;
  let mut child_opt = std::mem::replace(&mut *guard, None);

  if let Some(mut child) = child_opt.take() {
    println!("Stopping Music Caster process...");
    if let Err(e) = child.kill() {
      eprintln!("Warning: Failed to kill Music Caster process: {}", e);
    }
    if let Err(e) = child.wait() {
      eprintln!("Warning: Failed to wait for Music Caster process: {}", e);
    }
    Ok("Music Caster stopped successfully".to_string())
  } else {
    Ok("Music Caster was not running".to_string())
  }
}

#[tauri::command]
async fn is_music_caster_running(app_handle: tauri::AppHandle) -> Result<bool, String> {
  let state = app_handle.state::<MusicCasterState>();
  let mut guard = state.0.lock().map_err(|e| format!("State lock error: {}", e))?;

  if let Some(child) = guard.as_mut() {
    match child.try_wait() {
      Ok(None) => Ok(true), // Still running
      Ok(Some(_)) => Ok(false), // Exited
      Err(e) => {
        eprintln!("Warning: Failed to check process status: {}", e);
        Ok(false)
      }
    }
  } else {
    Ok(false) // Not running
  }
}

#[cfg(target_os = "linux")]
fn webkit_hidpi_workaround() {
  // See: https://github.com/spacedriveapp/spacedrive/issues/1512#issuecomment-1758550164
  std::env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1");
}

fn main_prelude() {
  #[cfg(target_os = "linux")]
  webkit_hidpi_workaround();
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  main_prelude();
  // main window should be invisible to allow either the setup delay or the plugin to show the window
  tauri::Builder::default()
    .plugin(tauri_plugin_log::Builder::new().build())
    .plugin(tauri_plugin_opener::init())
    .plugin(tauri_plugin_store::Builder::new().build())
    .plugin(tauri_plugin_updater::Builder::new().build())
    .plugin(tauri_plugin_process::init())
    .plugin(tauri_plugin_dialog::init())
    .plugin(tauri_plugin_os::init())
    .plugin(tauri_plugin_notification::init())
    .plugin(tauri_plugin_shell::init())
    .plugin(tauri_plugin_fs::init())
    // custom commands
    .invoke_handler(tauri::generate_handler![
      tray_update_lang,
      process_file,
      start_music_caster,
      stop_music_caster,
      is_music_caster_running
    ])
    // allow only one instance and propagate args and cwd to existing instance
    .plugin(tauri_plugin_single_instance::init(|app, args, cwd| {
      app
        .emit("newInstance", SingleInstancePayload { args, cwd })
        .unwrap();
    }))
    // persistent storage with filesystem
    .plugin(tauri_plugin_store::Builder::default().build())
    // save window position and size between sessions
    // if you remove this, make sure to uncomment the mainWebview?.show line in TauriProvider.tsx
    .plugin(tauri_plugin_window_state::Builder::default().build())
    // custom setup code
    .setup(|app| {
      let _ = create_tray_icon(app.handle());
      app.manage(Mutex::new(TrayState::NotPlaying));
      app.manage(MusicCasterState(Mutex::new(None)));

      let app_handle = app.handle().clone();
      tauri::async_runtime::spawn(async move { long_running_thread(&app_handle).await });

      #[cfg(target_os = "linux")]
      app.manage(DbusState(Mutex::new(
        dbus::blocking::SyncConnection::new_session().ok(),
      )));

      // TODO: AUTOSTART
      // FOLLOW: https://v2.tauri.app/plugin/autostart/

      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}

// useful crates
// https://crates.io/crates/directories for getting common directories

// TODO: optimize permissions
// TODO: decorations false and use custom title bar
