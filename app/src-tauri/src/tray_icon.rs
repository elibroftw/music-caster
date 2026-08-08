use serde::Serialize;
use std::path::Path;
use std::sync::Mutex;
use tauri::menu::{CheckMenuItemBuilder, Menu, MenuBuilder, MenuItemBuilder, SubmenuBuilder};
use tauri::tray::{MouseButton, MouseButtonState, TrayIcon, TrayIconBuilder, TrayIconEvent};
use tauri::{self, Emitter, Manager, Runtime, command};
use tauri_plugin_dialog::DialogExt;

use crate::api::{
  DaemonState, Device, DevicesState, LOCAL_DEVICE_ID, PlayUrisOptions, PlaybackStatus, PlayerState,
  PlayerStatus, RepeatMode,
};
use crate::settings::Settings;

#[derive(Clone, Serialize)]
pub struct IconTrayPayload {
  message: String,
}

impl IconTrayPayload {
  pub fn new(message: &str) -> IconTrayPayload {
    IconTrayPayload {
      message: message.into(),
    }
  }
}

#[derive(Clone)]
pub enum TrayState {
  NotPlaying,
  Paused,
  Playing,
}

const AUDIO_EXTENSIONS: &[&str] = &[
  "mp3", "mp4", "mpeg", "m4a", "flac", "aac", "ogg", "opus", "wma", "wav", "aiff", "m3u", "m3u8",
];

pub fn create_tray_menu<R: Runtime>(
  app: &tauri::AppHandle<R>,
  _lang: String,
) -> Result<Menu<R>, tauri::Error> {
  let tray_state = app.state::<Mutex<TrayState>>().lock().unwrap().clone();
  let settings_guard = app.state::<Mutex<Settings>>().lock().unwrap().clone();
  let music_folders = &settings_guard.music_folders;
  let playlist_names: Vec<&String> = settings_guard.playlists.keys().collect();
  let devices: Vec<Device> = app
    .try_state::<DevicesState>()
    .map(|state| state.lock().unwrap().clone())
    .unwrap_or_default();

  let text = match tray_state {
    TrayState::Playing => "Pause",
    TrayState::Paused => "Resume",
    TrayState::NotPlaying => "Play",
  };

  // repeat is a daemon setting, mirrored into the polled player state
  let repeat = current_repeat(app);

  let mut folders_submenu = SubmenuBuilder::new(app, "Folders")
    .item(&MenuItemBuilder::with_id("select-folder", "Select Folder").build(app)?);
  for (i, folder) in music_folders.iter().enumerate() {
    let display = format_folder_name(folder);
    folders_submenu =
      folders_submenu.item(&MenuItemBuilder::with_id(format!("folder-{i}"), display).build(app)?);
  }

  // `device` is None when the daemon is playing on the local device
  let selected_device = settings_guard.device.as_deref().unwrap_or(LOCAL_DEVICE_ID);
  let mut devices_submenu = SubmenuBuilder::new(app, "Select Device");
  if devices.is_empty() {
    devices_submenu = devices_submenu.item(
      &MenuItemBuilder::with_id("devices-empty", "No Devices Found")
        .enabled(false)
        .build(app)?,
    );
  }
  for device in &devices {
    let id = format!("device-{}", device.id);
    devices_submenu = devices_submenu.item(
      &CheckMenuItemBuilder::with_id(id, &device.name)
        .checked(device.id == selected_device)
        .build(app)?,
    );
  }

  let mut playlists_submenu = SubmenuBuilder::new(app, "Playlists")
    .item(&MenuItemBuilder::with_id("playlists-tab", "Playlists Tab").build(app)?);
  for name in &playlist_names {
    let id = format!("playlist-{}", name);
    playlists_submenu =
      playlists_submenu.item(&MenuItemBuilder::with_id(id, name.as_str()).build(app)?);
  }

  MenuBuilder::new(app)
    .items(&[
      &MenuItemBuilder::with_id("mc-rescan", "Rescan Library").build(app)?,
      &MenuItemBuilder::with_id("mc-refresh", "Refresh Devices").build(app)?,
      &devices_submenu.build()?,
      &SubmenuBuilder::new(app, "Timer")
        .item(&MenuItemBuilder::with_id("timer-set", "Set Timer").build(app)?)
        .item(&MenuItemBuilder::with_id("timer-cancel", "Cancel Timer").build(app)?)
        .build()?,
      &SubmenuBuilder::new(app, "Controls")
        .item(&MenuItemBuilder::with_id("locate-track", "Locate Track").build(app)?)
        .item(
          &SubmenuBuilder::new(app, "Repeat Options")
            .item(
              &CheckMenuItemBuilder::with_id("repeat-all", "Repeat All")
                .checked(repeat == RepeatMode::All)
                .build(app)?,
            )
            .item(
              &CheckMenuItemBuilder::with_id("repeat-one", "Repeat One")
                .checked(repeat == RepeatMode::One)
                .build(app)?,
            )
            .item(
              &CheckMenuItemBuilder::with_id("repeat-off", "Repeat Off")
                .checked(repeat == RepeatMode::Off)
                .build(app)?,
            )
            .build()?,
        )
        .item(&MenuItemBuilder::with_id("mc-controls-prev", "Previous Track").build(app)?)
        .item(&MenuItemBuilder::with_id("mc-controls-next", "Next Track").build(app)?)
        .item(&MenuItemBuilder::with_id("mc-controls-pause", &text).build(app)?)
        .build()?,
      &SubmenuBuilder::new(app, "Play")
        .item(&MenuItemBuilder::with_id("play-system", "System Audio").build(app)?)
        .item(
          &SubmenuBuilder::new(app, "URL")
            .item(&MenuItemBuilder::with_id("url-play", "Play URL").build(app)?)
            .item(&MenuItemBuilder::with_id("url-queue", "Queue URL").build(app)?)
            .item(&MenuItemBuilder::with_id("url-next", "Play URL Next").build(app)?)
            .build()?,
        )
        .item(&folders_submenu.build()?)
        .item(&playlists_submenu.build()?)
        .item(
          &SubmenuBuilder::new(app, "Select Files")
            .item(&MenuItemBuilder::with_id("play-files", "Play Files").build(app)?)
            .item(&MenuItemBuilder::with_id("queue-files", "Queue Files").build(app)?)
            .item(&MenuItemBuilder::with_id("play-files-next", "Play Files Next").build(app)?)
            .build()?,
        )
        .item(&MenuItemBuilder::with_id("play-all", "Play All").build(app)?)
        .build()?,
      &MenuItemBuilder::with_id("mc-exit", "Exit").build(app)?,
    ])
    .build()
}

/// last repeat mode the state poll saw; `Off` until the first poll succeeds. the menu is built
/// synchronously, so a contended lock falls back to the default rather than blocking
fn current_repeat<R: Runtime>(app: &tauri::AppHandle<R>) -> RepeatMode {
  app
    .try_state::<PlayerState>()
    .and_then(|state| state.try_read().ok().map(|state| state.repeat))
    .unwrap_or_default()
}

fn format_folder_name(folder: &str) -> String {
  let path = Path::new(folder);
  let components: Vec<&std::ffi::OsStr> = path.iter().collect();
  if components.len() > 2 {
    let len = components.len();
    format!(
      "../{}",
      components[len - 2..]
        .iter()
        .filter_map(|c| c.to_str())
        .collect::<Vec<_>>()
        .join("/")
    )
  } else {
    folder.replace('\\', "/")
  }
}

/// Fetch the devices the daemon knows about (and the settings it owns, which hold the selected
/// device) and rebuild the tray menu when either changed.
pub async fn refresh_tray_devices(app: &tauri::AppHandle) {
  let Some(daemon_state) = app.try_state::<DaemonState>() else {
    return;
  };
  let base_url = daemon_state.read().await.get_base_url();

  let devices = match crate::api::fetch_devices(&base_url).await {
    Ok(devices) => devices,
    Err(e) => {
      log::error!("[Devices] failed to fetch devices: {}", e);
      return;
    }
  };
  let settings = Settings::load(app);
  let lang = app.state::<PlayerState>().read().await.lang.clone();

  let changed = {
    let devices_state = app.state::<DevicesState>();
    let mut devices_guard = devices_state.lock().unwrap();
    let settings_state = app.state::<Mutex<Settings>>();
    let mut settings_guard = settings_state.lock().unwrap();

    let changed = *devices_guard != devices
      || settings_guard.device != settings.device
      || settings_guard.music_folders != settings.music_folders
      || settings_guard.playlists != settings.playlists;
    *devices_guard = devices;
    *settings_guard = settings;
    changed
  };

  if changed {
    if let Some(tray_handle) = app.tray_by_id(TRAY_ID) {
      let _ = tray_handle.set_menu(create_tray_menu(app, lang).ok());
    }
  }
}

fn show_window_and_emit(app: &tauri::AppHandle, event_id: &str) {
  if let Some(main_window) = app.get_webview_window("main") {
    let _ = main_window.show();
    let _ = main_window.set_focus();
    let _ = main_window.emit("systemTray", IconTrayPayload::new(event_id));
  }
}

pub static TRAY_ID: &'static str = "main";

pub fn create_tray_icon(app: &tauri::AppHandle) -> Result<TrayIcon, tauri::Error> {
  TrayIconBuilder::with_id(TRAY_ID)
    .icon(
      tauri::image::Image::from_bytes(include_bytes!("../icons/SystemTray1.ico"))
        .ok()
        .expect("SystemTray1.icon not found"),
    )
    .tooltip("Loading Daemon")
    .menu(&create_tray_menu(app, "en".into())?)
    .show_menu_on_left_click(false)
    .on_menu_event(move |app, event| {
      let event_id = event.id().as_ref().to_string();

      match event_id.as_str() {
        "mc-rescan" => {
          let app_clone = app.clone();
          tauri::async_runtime::spawn(async move {
            let state = app_clone.state::<DaemonState>();
            let _ = crate::api::api_rescan_library(state).await;
          });
        }
        "mc-refresh" => {
          let app_clone = app.clone();
          tauri::async_runtime::spawn(async move {
            let state = app_clone.state::<DaemonState>();
            let _ = crate::api::api_refresh_devices(state).await;
            refresh_tray_devices(&app_clone).await;
          });
        }
        "mc-controls-prev" => {
          let app_clone = app.clone();
          tauri::async_runtime::spawn(async move {
            let state = app_clone.state::<DaemonState>();
            let _ = crate::api::api_prev(state, 1, false).await;
          });
        }
        "mc-controls-next" => {
          let app_clone = app.clone();
          tauri::async_runtime::spawn(async move {
            let state = app_clone.state::<DaemonState>();
            let _ = crate::api::api_next(state, 1, false).await;
          });
        }
        "mc-controls-pause" => {
          let tray_state = app.state::<Mutex<TrayState>>().lock().unwrap().clone();
          let app_clone = app.clone();
          tauri::async_runtime::spawn(async move {
            let daemon_state = app_clone.state::<DaemonState>();
            match tray_state {
              TrayState::Playing => {
                let _ = crate::api::api_pause(daemon_state).await;
              }
              _ => {
                let _ = crate::api::api_play(daemon_state).await;
              }
            }
          });
        }
        "mc-exit" => {
          app.exit(0);
        }
        "select-folder" => {
          let app_clone = app.clone();
          tauri::async_runtime::spawn(async move {
            let folder = app_clone
              .dialog()
              .file()
              .set_title("Select Folder")
              .blocking_pick_folder();
            if let Some(folder_path) = folder {
              let path_str = folder_path.to_string();
              let state = app_clone.state::<DaemonState>();
              let options = PlayUrisOptions {
                uris: Some(vec![path_str]),
                ..Default::default()
              };
              let _ = crate::api::api_play_uris(state, options).await;
            }
          });
        }
        "play-files" => {
          let app_clone = app.clone();
          tauri::async_runtime::spawn(async move {
            let files = app_clone
              .dialog()
              .file()
              .set_title("Select Audio Files")
              .add_filter("Audio Files", AUDIO_EXTENSIONS)
              .blocking_pick_files();
            if let Some(file_paths) = files {
              if !file_paths.is_empty() {
                let uris: Vec<String> = file_paths.iter().map(|p| p.to_string()).collect();
                let state = app_clone.state::<DaemonState>();
                let options = PlayUrisOptions {
                  uris: Some(uris),
                  ..Default::default()
                };
                let _ = crate::api::api_play_uris(state, options).await;
              }
            }
          });
        }
        "queue-files" => {
          let app_clone = app.clone();
          tauri::async_runtime::spawn(async move {
            let files = app_clone
              .dialog()
              .file()
              .set_title("Select Audio Files")
              .add_filter("Audio Files", AUDIO_EXTENSIONS)
              .blocking_pick_files();
            if let Some(file_paths) = files {
              if !file_paths.is_empty() {
                let uris: Vec<String> = file_paths.iter().map(|p| p.to_string()).collect();
                let state = app_clone.state::<DaemonState>();
                let options = PlayUrisOptions {
                  uris: Some(uris),
                  queue: Some(true),
                  ..Default::default()
                };
                let _ = crate::api::api_play_uris(state, options).await;
              }
            }
          });
        }
        "play-files-next" => {
          let app_clone = app.clone();
          tauri::async_runtime::spawn(async move {
            let files = app_clone
              .dialog()
              .file()
              .set_title("Select Audio Files")
              .add_filter("Audio Files", AUDIO_EXTENSIONS)
              .blocking_pick_files();
            if let Some(file_paths) = files {
              if !file_paths.is_empty() {
                let uris: Vec<String> = file_paths.iter().map(|p| p.to_string()).collect();
                let state = app_clone.state::<DaemonState>();
                let options = PlayUrisOptions {
                  uris: Some(uris),
                  play_next: Some(true),
                  ..Default::default()
                };
                let _ = crate::api::api_play_uris(state, options).await;
              }
            }
          });
        }
        "play-system" => {
          let app_clone = app.clone();
          tauri::async_runtime::spawn(async move {
            let state = app_clone.state::<DaemonState>();
            let options = PlayUrisOptions {
              uri: Some("systemaudio".to_string()),
              ..Default::default()
            };
            let _ = crate::api::api_play_uris(state, options).await;
          });
        }
        "play-all" => {
          let app_clone = app.clone();
          tauri::async_runtime::spawn(async move {
            let state = app_clone.state::<DaemonState>();
            let _ = crate::api::api_play(state).await;
          });
        }
        "timer-cancel" => {
          let app_clone = app.clone();
          tauri::async_runtime::spawn(async move {
            let state = app_clone.state::<DaemonState>();
            let _ = crate::api::api_cancel_timer(state).await;
          });
        }
        "timer-set" => {
          show_window_and_emit(app, "timer-set");
        }
        "repeat-all" | "repeat-one" | "repeat-off" => {
          let mode = match event_id.as_str() {
            "repeat-all" => RepeatMode::All,
            "repeat-one" => RepeatMode::One,
            _ => RepeatMode::Off,
          };
          let app_clone = app.clone();
          tauri::async_runtime::spawn(async move {
            let state = app_clone.state::<DaemonState>();
            let _ =
              crate::api::api_change_setting(state, "repeat".to_string(), mode.setting_value())
                .await;
          });
        }
        "url-play" | "url-queue" | "url-next" => {
          show_window_and_emit(app, &event_id);
        }
        "playlists-tab" => {
          show_window_and_emit(app, "playlists-tab");
        }
        "locate-track" => {
          let player_state_guard = app
            .state::<Mutex<crate::api::PlayerState>>()
            .inner()
            .lock()
            .unwrap();
          if let Ok(player_state) = player_state_guard.try_read() {
            let file_name = player_state.file_name.clone();
            if !file_name.is_empty() {
              if file_name.starts_with("http") {
                let _ = open::that(&file_name);
              } else if Path::new(&file_name).exists() {
                #[cfg(target_os = "windows")]
                {
                  let _ = std::process::Command::new("explorer")
                    .args(["/select,", &file_name])
                    .spawn();
                }
                #[cfg(not(target_os = "windows"))]
                {
                  let _ = open::that(Path::new(&file_name).parent().unwrap_or(Path::new("/")));
                }
              }
            }
          }
        }
        _ => {
          if let Some(folder_idx) = event_id.strip_prefix("folder-") {
            if let Ok(idx) = folder_idx.parse::<usize>() {
              let folder_path = {
                let settings_guard = app.state::<Mutex<Settings>>().lock().unwrap().clone();
                settings_guard.music_folders.get(idx).cloned()
              };
              if let Some(path) = folder_path {
                let app_clone = app.clone();
                tauri::async_runtime::spawn(async move {
                  let state = app_clone.state::<DaemonState>();
                  let options = PlayUrisOptions {
                    uris: Some(vec![path]),
                    ..Default::default()
                  };
                  let _ = crate::api::api_play_uris(state, options).await;
                });
              }
            }
          } else if let Some(playlist_name) = event_id.strip_prefix("playlist-") {
            let name = playlist_name.to_string();
            let app_clone = app.clone();
            tauri::async_runtime::spawn(async move {
              let state = app_clone.state::<DaemonState>();
              let options = PlayUrisOptions {
                uri: Some(name),
                ..Default::default()
              };
              let _ = crate::api::api_play_uris(state, options).await;
            });
          } else if let Some(device_id) = event_id.strip_prefix("device-") {
            let device_id = device_id.to_string();
            let app_clone = app.clone();
            tauri::async_runtime::spawn(async move {
              let state = app_clone.state::<DaemonState>();
              let _ = crate::api::api_change_device(state, device_id).await;
              // rebuild the menu so the check mark follows the daemon's selected device
              refresh_tray_devices(&app_clone).await;
            });
          }
        }
      }
    })
    .on_tray_icon_event(|tray, event| {
      let app = tray.app_handle();
      if let TrayIconEvent::Click {
        button: MouseButton::Left,
        button_state: MouseButtonState::Up,
        ..
      } = event
      {
        if let Some(main_window) = app.get_webview_window("main") {
          let _ = main_window.emit("system-tray", IconTrayPayload::new("left-click"));
          let _ = main_window.show();
          let _ = main_window.set_focus();
        }
      }
    })
    .build(app)
}

#[command]
#[allow(unused_must_use)]
pub fn tray_update_lang(app: tauri::AppHandle, lang: String) {
  let tray_handle = app.tray_by_id(TRAY_ID);
  if let Some(t) = tray_handle {
    t.set_menu(create_tray_menu(&app, lang).ok());
  }
}

pub fn tray_update(app: tauri::AppHandle, player_state: &PlayerStatus) {
  let tray_state_mutex = app.state::<Mutex<TrayState>>();
  let mut tray_state = tray_state_mutex.lock().unwrap();
  let tray_icon: TrayIcon = app.tray_by_id(TRAY_ID).unwrap();

  let icon_empty = include_bytes!("../icons/SystemTray1.ico");
  let icon_full = include_bytes!("../icons/SystemTray2.ico");

  match &player_state.status {
    PlaybackStatus::Playing => {
      tray_icon
        .set_icon(tauri::image::Image::from_bytes(icon_full).ok())
        .unwrap();
      let mut tooltip = String::from("Playing");
      if player_state.artist != "" && player_state.title != "" {
        tooltip = format!("{} - {}", player_state.artist, player_state.title);
      }

      let _ = tray_icon.set_tooltip(Some(tooltip));
      *tray_state = TrayState::Playing;
    }
    PlaybackStatus::Paused => {
      tray_icon
        .set_icon(tauri::image::Image::from_bytes(icon_empty).ok())
        .unwrap();
      let mut tooltip = String::from("Paused");
      if player_state.artist != "" && player_state.title != "" {
        tooltip = format!("{} - {}", player_state.artist, player_state.title);
      }
      let _ = tray_icon.set_tooltip(Some(tooltip));
      *tray_state = TrayState::Paused;
    }
    PlaybackStatus::NotPlaying => {
      tray_icon
        .set_icon(tauri::image::Image::from_bytes(icon_empty).ok())
        .unwrap();
      let _ = tray_icon.set_tooltip(Some(String::from("Not Playing")));
      *tray_state = TrayState::NotPlaying;
    }
    PlaybackStatus::NotRunning => {}
  }
  drop(tray_state);
  if let Some(tray_handle) = app.tray_by_id(TRAY_ID) {
    let _ = tray_handle.set_menu(create_tray_menu(&app, player_state.lang.clone()).ok());
  }
}
