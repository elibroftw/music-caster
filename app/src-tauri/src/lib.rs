// this hides the console for Windows release builds
#![cfg_attr(
  all(not(debug_assertions), target_os = "windows"),
  windows_subsystem = "windows"
)]

use serde::Serialize;
use std::sync::Mutex;
use tauri::{
  self,
  Emitter,
  Manager,
};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_store;
use tauri_plugin_window_state;

mod api;
mod tray_icon;
mod utils;

use api::*;
use tauri_plugin_sql::{Migration, MigrationKind};
use tray_icon::{create_tray_icon, tray_update_lang, TrayState};
use utils::long_running_thread;

#[derive(Clone, Serialize)]
struct SingleInstancePayload {
  args: Vec<String>,
  cwd: String,
}

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

fn start_music_caster_daemon(app_handle: &tauri::AppHandle) -> Result<(), String> {
  let app_data_dir = app_handle
    .path()
    .app_data_dir()
    .map_err(|e| format!("Failed to get app data directory: {}", e))?;

  std::fs::create_dir_all(&app_data_dir)
    .map_err(|e| format!("Failed to create app data directory: {}", e))?;

  let db_path = app_data_dir.join("music_caster.db").display().to_string();
  let settings_path = app_data_dir.join("settings.json").display().to_string();
	println!("settings path: {}", &settings_path);
	println!("db_path: {}", &db_path);

  let sidecar_command = app_handle
    .shell()
    .sidecar("music-caster-daemon")
    .map_err(|e| format!("Failed to create sidecar command: {}", e))?
    .args([
      "--db-path",
      &db_path,
      "--settings-path",
      &settings_path,
    ]);

  let (mut rx, child) = sidecar_command
    .spawn()
    .map_err(|e| format!("Failed to spawn Music Caster: {}", e))?;

  tauri::async_runtime::spawn(async move {
    while let Some(event) = rx.recv().await {
      match event {
        CommandEvent::Stdout(line_bytes) => {
          let line = String::from_utf8_lossy(&line_bytes);
          println!("[Music Caster] {}", line);
        }
        CommandEvent::Stderr(line_bytes) => {
          let line = String::from_utf8_lossy(&line_bytes);
          eprintln!("[Music Caster Error] {}", line);
        }
        CommandEvent::Error(err) => {
          eprintln!("[Music Caster] Error: {}", err);
        }
        CommandEvent::Terminated(payload) => {
          println!("[Music Caster] Terminated with code: {:?}", payload.code);
          break;
        }
        _ => {}
      }
    }
  });

  Ok(())
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

  let migrations = vec![Migration {
    version: 1,
    description: "create_initial_tables",
    sql: "CREATE TABLE IF NOT EXISTS concert_events (
            artist TEXT NOT NULL,
            event_name TEXT NOT NULL,
            venue TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT,
            country TEXT,
            date TEXT NOT NULL,
            url TEXT,
            last_checked REAL NOT NULL,
            UNIQUE(artist, event_name, venue, city, date)
        );

        CREATE TABLE IF NOT EXISTS file_metadata (
            file_path TEXT PRIMARY KEY NOT NULL,
            title TEXT,
            artist TEXT,
            album TEXT,
            length INTEGER UNSIGNED,
            explicit BOOLEAN DEFAULT 0 NOT NULL CHECK (explicit IN (0, 1)),
            track_number INTEGER UNSIGNED DEFAULT 1 NOT NULL,
            sort_key TEXT DEFAULT file_path NOT NULL,
            time_modified REAL
        );

        CREATE TABLE IF NOT EXISTS url_metadata (
            src TEXT PRIMARY KEY NOT NULL,
            title TEXT,
            artist TEXT,
            album TEXT,
            length REAL,
            url TEXT,
            audio_url TEXT,
            ext TEXT,
            art TEXT,
            expiry REAL,
            id TEXT,
            pl_src TEXT,
            live BOOLEAN DEFAULT 0 NOT NULL CHECK (live IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS queues (
            name TEXT NOT NULL UNIQUE,
            tracks TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );",
    kind: MigrationKind::Up,
  }];

  // main window should be invisible to allow either the setup delay or the plugin to show the window
  tauri::Builder::default()
    .plugin(tauri_plugin_autostart::Builder::new().build())
    .plugin(
      tauri_plugin_sql::Builder::default()
        .add_migrations("sqlite:music_caster.db", migrations)
        .build(),
    )
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
    .plugin(tauri_plugin_http::init())
    .invoke_handler(tauri::generate_handler![
      tray_update_lang,
      process_file,
      api_is_running,
      api_activate,
      api_get_devices,
      api_change_device,
      api_play,
      api_pause,
      api_next,
      api_prev,
      api_toggle_repeat,
      api_toggle_shuffle,
      api_get_state,
      api_play_uris,
      api_exit,
      api_change_setting,
      api_refresh_devices,
      api_rescan_library,
      api_set_timer,
      api_get_timer,
      api_cancel_timer,
      api_get_file_url,
      api_get_stream_url
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
      app.manage(Mutex::new(TrayState::NotPlaying));
      let _ = create_tray_icon(app.handle());

      let app_handle = app.handle().clone();
      tauri::async_runtime::spawn(async move { long_running_thread(&app_handle).await });

      #[cfg(target_os = "linux")]
      app.manage(DbusState(Mutex::new(
        dbus::blocking::SyncConnection::new_session().ok(),
      )));

      // Start music caster daemon automatically after database is initialized
      let app_handle = app.handle().clone();
      if let Err(e) = start_music_caster_daemon(&app_handle) {
        eprintln!("Failed to start Music Caster daemon: {}", e);
      }

      #[cfg(desktop)]
      {
        use tauri_plugin_autostart::MacosLauncher;
        use tauri_plugin_autostart::ManagerExt;

        let _ =app.handle().plugin(tauri_plugin_autostart::init(
          MacosLauncher::LaunchAgent,
          Some(vec!["--flag1", "--flag2"]),
        ));

        // Get the autostart manager
        let autostart_manager = app.autolaunch();
        // Enable autostart
        let _ = autostart_manager.enable();
        // Check enable state
        println!(
          "registered for autostart? {}",
          autostart_manager.is_enabled().unwrap()
        );
        // Disable autostart
        let _ = autostart_manager.disable();
      }

      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}

// useful crates
// https://crates.io/crates/directories for getting common directories

// TODO: optimize permissions
// TODO: decorations false and use custom title bar
