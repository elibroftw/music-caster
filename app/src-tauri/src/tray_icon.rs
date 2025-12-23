use serde::Serialize;
use std::sync::Mutex;
use tauri::menu::{Menu, MenuBuilder, MenuItemBuilder, SubmenuBuilder};
use tauri::tray::{MouseButton, MouseButtonState, TrayIcon, TrayIconBuilder, TrayIconEvent};
use tauri::{self, Emitter, Manager, Runtime, command};

use crate::api::{PlaybackStatus, PlayerState};

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

// ENTER rust_i18n::set_locale(lang) IF LOCAL=lang DOES NOT COMPILE
pub fn create_tray_menu<R: Runtime>(
  app: &tauri::AppHandle<R>,
  _lang: String,
) -> Result<Menu<R>, tauri::Error> {
  let tray_state = app.state::<Mutex<TrayState>>().lock().unwrap().clone();

  let text = match tray_state {
    TrayState::Playing => "Pause",
    TrayState::Paused => "Resume",
    TrayState::NotPlaying => "Play",
  };

  // Menu for when Music Caster is running
  MenuBuilder::new(app)
    .items(&[
      &MenuItemBuilder::with_id("mc-rescan", "Rescan Library").build(app)?,
      &MenuItemBuilder::with_id("mc-refresh", "Refresh Devices").build(app)?,
      &SubmenuBuilder::new(app, "Select Device")
        .item(&MenuItemBuilder::with_id("device-1", "Device 1").build(app)?)
        .item(&MenuItemBuilder::with_id("device-2", "Device 2").build(app)?)
        .build()?,
      &SubmenuBuilder::new(app, "Timer")
        .item(&MenuItemBuilder::with_id("timer-set", "Set Timer").build(app)?)
        .item(&MenuItemBuilder::with_id("timer-cancel", "Cancel Timer").build(app)?)
        .build()?,
      &SubmenuBuilder::new(app, "Controls")
        .item(&MenuItemBuilder::with_id("locate-track", "Locate Track").build(app)?)
        .item(
          &SubmenuBuilder::new(app, "Repeat Options")
            .item(&MenuItemBuilder::with_id("repeat-all", "Repeat All").build(app)?)
            .item(&MenuItemBuilder::with_id("repeat-one", "Repeat One ✓").build(app)?)
            .item(&MenuItemBuilder::with_id("repeat-off", "Repeat Off").build(app)?)
            .build()?,
        )
        .item(&MenuItemBuilder::with_id("mc-controls-stop", "Stop").build(app)?)
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
        .item(
          &SubmenuBuilder::new(app, "Folders")
            .item(&MenuItemBuilder::with_id("select-folder", "Select Folder").build(app)?)
            .item(&MenuItemBuilder::with_id("folder-1", "../Music").build(app)?)
            .build()?,
        )
        .item(
          &SubmenuBuilder::new(app, "Playlists")
            .item(&MenuItemBuilder::with_id("playlists-tab", "Playlists Tab").build(app)?)
            .item(&MenuItemBuilder::with_id("playlist-1", "My Playlist").build(app)?)
            .build()?,
        )
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

pub static TRAY_ID: &'static str = "main";

pub fn create_tray_icon(app: &tauri::AppHandle) -> Result<TrayIcon, tauri::Error> {
  TrayIconBuilder::with_id(TRAY_ID)
    .icon(
      tauri::image::Image::from_bytes(include_bytes!("../icons/SystemTray1.ico"))
        .ok()
        .expect("SystemTray1.icon not found"),
    )
    // TODO: update this
    .tooltip("Loading Daemon")
    .menu(&create_tray_menu(app, "en".into())?)
    .show_menu_on_left_click(false)
    .on_menu_event(move |app, event| {
      // Forward tray events to the frontend with Music Caster prefix
      if let Some(main_window) = app.get_webview_window("main") {
        let _ = main_window.emit("systemTray", IconTrayPayload::new(&event.id().as_ref()));
      }

      // Handle Music Caster tray events by forwarding them to MC if running
      if let Some(event_id) = event.id().as_ref().strip_prefix("mc-") {
        match event_id {
          _ => {
            // Forward other commands to Music Caster via invoke
            println!("Forwarding tray command '{}' to Music Caster", event_id);
          }
        }
      }

      let _tray_icon = app.tray_by_id(TRAY_ID).unwrap();

      // TODO: FIGURE OUT HOW TO GET THE ITEM HANDLER IN v2
      // let item_handle: MenuItem = tray_icon.get_item();

      match event.id().as_ref() {
        "quit" => {
          std::process::exit(0);
        }
        "toggle-visibility" => {
          if let Some(main_window) = app.get_webview_window("main") {
            // update menu item example (TODO: support tauri v2)
            // proposed implementation: update entire menu
            if main_window.is_visible().unwrap() {
              main_window.hide().unwrap();
              // item_handle.set_title("Show Window").unwrap();
            } else {
              main_window.show().unwrap();
              // item_handle.set_title("Hide Window").unwrap();
            }
          }
        }
        _ => {}
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
        println!("system tray received a left click");
      } else if let TrayIconEvent::Click {
        button: MouseButton::Right,
        button_state: MouseButtonState::Up,
        ..
      } = event
      {
        println!("system tray received a right click");
      } else if let TrayIconEvent::DoubleClick { .. } = event {
        println!("system tray received a double click");
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

pub fn tray_update(app: tauri::AppHandle, player_state: &PlayerState) {
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
}
