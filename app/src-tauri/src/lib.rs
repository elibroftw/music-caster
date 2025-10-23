// this hides the console for Windows release builds
#![cfg_attr(
  all(not(debug_assertions), target_os = "windows"),
  windows_subsystem = "windows"
)]

use serde::Serialize;
use std::sync::Mutex;
use tauri::{self, Emitter, Manager};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_store;
use tauri_plugin_window_state;

mod api;
mod db;
mod tray_icon;
mod utils;

use api::{ApiState, *};
use std::fs;
use std::path::PathBuf;
use tray_icon::{create_tray_icon, tray_update_lang, TrayState};
use utils::long_running_thread;

fn read_port_from_pid_file(pid_file: PathBuf) -> u16 {
  if let Ok(content) = fs::read_to_string(&pid_file) {
    let mut lines = content.lines();
    lines.next();
    if let Some(port_line) = lines.next() {
      if let Ok(port) = port_line.trim().parse::<u16>() {
        return port;
      }
    }
  }
  2001
}

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
  log::info!("Processing file: {}", filepath);
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
  let pid_file = app_data_dir.join("music_caster.pid");

  if pid_file.exists() {
    let _ = fs::remove_file(&pid_file);
  }

  log::info!("settings path: {}", &settings_path);
  log::info!("db_path: {}", &db_path);

  let app_args: Vec<String> = std::env::args().skip(1).collect();

  let mut sidecar_args = vec![
    "--db-path".to_string(),
    db_path,
    "--settings-path".to_string(),
    settings_path,
  ];
  sidecar_args.extend(app_args);

  let sidecar_command = app_handle
    .shell()
    .sidecar("music-caster-daemon")
    .map_err(|e| format!("Failed to create sidecar command: {}", e))?
    .args(sidecar_args);

  let (mut sidecar_rx, child) = sidecar_command
    .spawn()
    .map_err(|e| format!("Failed to spawn Music Caster: {}", e))?;

  let app_handle_clone = app_handle.clone();
  let pid_file_clone = pid_file.clone();
  tauri::async_runtime::spawn(async move {
    loop {
      tokio::time::sleep(tokio::time::Duration::from_secs(1)).await;

      if pid_file_clone.exists() {
        let port = read_port_from_pid_file(pid_file_clone);
        if let Some(api_state) = app_handle_clone.try_state::<ApiState>() {
          *api_state.port.write().unwrap() = port;
          log::info!("[Music Caster] Updated port to: {}", port);
        }
        break;
      }
    }
  });

  tauri::async_runtime::spawn(async move {
    while let Some(event) = sidecar_rx.recv().await {
      match event {
        CommandEvent::Stdout(line_bytes) => {
          let line = String::from_utf8_lossy(&line_bytes);
          log::info!("[Music Caster] {}", line);
        }
        CommandEvent::Stderr(line_bytes) => {
          let line = String::from_utf8_lossy(&line_bytes);
          log::error!("[Music Caster Error] {}", line);
        }
        CommandEvent::Error(err) => {
          log::error!("[Music Caster] Error: {}", err);
        }
        CommandEvent::Terminated(payload) => {
          log::info!("[Music Caster] Terminated with code: {:?}", payload.code);
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

  let mut log_builder = tauri_plugin_log::Builder::new().target(tauri_plugin_log::Target::new(
    tauri_plugin_log::TargetKind::LogDir {
      file_name: Some("logs".to_string()),
    },
  ));
  #[cfg(debug_assertions)]
  {
    log_builder = log_builder.target(tauri_plugin_log::Target::new(
      tauri_plugin_log::TargetKind::Webview,
    ));
  }

  // main window should be invisible to allow either the setup delay or the plugin to show the window
  tauri::Builder::default()
    .plugin(tauri_plugin_autostart::Builder::new().build())
    .plugin(
      tauri_plugin_sql::Builder::default()
        .add_migrations("sqlite:music_caster.db", db::get_migrations())
        .build(),
    )
    .plugin(log_builder.build())
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
      api_get_stream_url,
      api_get_album_art_url
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
      app.manage(ApiState::new());
      app.manage(Mutex::new(TrayState::NotPlaying));
      let _ = create_tray_icon(app.handle());

      let app_handle = app.handle().clone();
      tauri::async_runtime::spawn(async move { long_running_thread(&app_handle).await });

      let app_handle_poll = app.handle().clone();
      tauri::async_runtime::spawn(async move {
        api::poll_player_state(app_handle_poll).await;
      });

      #[cfg(target_os = "linux")]
      app.manage(DbusState(Mutex::new(
        dbus::blocking::SyncConnection::new_session().ok(),
      )));

      // Start music caster daemon automatically after database is initialized
      let app_handle = app.handle().clone();
      if let Err(e) = start_music_caster_daemon(&app_handle) {
        log::error!("Failed to start Music Caster daemon: {}", e);
      }

      #[cfg(desktop)]
      {
        use tauri_plugin_autostart::MacosLauncher;
        use tauri_plugin_autostart::ManagerExt;

        let _ = app.handle().plugin(tauri_plugin_autostart::init(
          MacosLauncher::LaunchAgent,
          Some(vec!["--flag1", "--flag2"]),
        ));

        // Get the autostart manager
        let autostart_manager = app.autolaunch();
        // Enable autostart
        let _ = autostart_manager.enable();
        // Check enable state
        log::info!(
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
