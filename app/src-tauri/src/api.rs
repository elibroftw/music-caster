use serde::{Deserialize, Serialize};
use std::{collections::HashMap, sync::Mutex};
use tauri::{Emitter, Manager, State};
use tauri_plugin_http::reqwest;
use tokio::sync::RwLock;

use crate::{settings::Settings, tray_icon::tray_update};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum PlaybackStatus {
  NotPlaying,
  Playing,
  Paused,
  NotRunning,
}

impl PlaybackStatus {
  pub fn is_playing(&self) -> bool {
    matches!(self, PlaybackStatus::Playing)
  }

  pub fn is_paused(&self) -> bool {
    matches!(self, PlaybackStatus::Paused)
  }

  pub fn is_not_playing(&self) -> bool {
    matches!(self, PlaybackStatus::NotPlaying)
  }

  pub fn is_busy(&self) -> bool {
    matches!(self, PlaybackStatus::Playing | PlaybackStatus::Paused)
  }
}

pub struct DaemonStatus {
  pub port: u16,
  pub is_running: bool,
  pub api_key: Option<String>,
}

impl DaemonStatus {
  pub fn get_base_url(&self) -> String {
    format!("http://localhost:{}", self.port)
  }
}

pub type DaemonState = RwLock<DaemonStatus>;

impl PlayerStatus {
  pub fn new() -> Self {
    Self {
      status: PlaybackStatus::NotRunning,
      volume: 20.0,
      lang: String::from("en"),
      title: String::from("Nothing Playing"),
      artist: String::from(""),
      album: String::from(""),
      track_position: 0.0,
      track_length: 0.0,
      queue_length: 0,
      queue: Vec::new(),
      queue_position: 0,
      file_name: String::from(""),
    }
  }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PlayerStatus {
  pub status: PlaybackStatus,
  pub volume: f64,
  pub lang: String,
  pub title: String,
  pub artist: String,
  pub album: String,
  pub track_position: f64,
  pub track_length: f64,
  pub queue_length: i32,
  pub queue: Vec<(String, String)>,
  pub queue_position: i32,
  pub file_name: String,
}

pub type PlayerState = RwLock<PlayerStatus>;

#[derive(Debug, Serialize, Deserialize)]
pub struct ActionResponse {
  pub message: String,
}

#[tauri::command]
pub async fn api_is_running(state: State<'_, DaemonState>) -> Result<bool, String> {
  let state = state.read().await;
  let client = reqwest::Client::new();
  let url = format!("{}/running/", state.get_base_url());

  match client.get(&url).send().await {
    Ok(response) => {
      let text = response.text().await.map_err(|e| e.to_string())?;
      Ok(text == "true")
    }
    Err(_) => Ok(false),
  }
}

#[tauri::command]
pub async fn api_activate(state: State<'_, DaemonState>) -> Result<ActionResponse, String> {
  let state = state.read().await;
  let client = reqwest::Client::new();
  let url = format!("{}/action/activate", state.get_base_url());

  let response = client.post(&url).send().await.map_err(|e| e.to_string())?;

  response
    .json::<ActionResponse>()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_get_devices(
  state: State<'_, DaemonState>,
  friendly: bool,
) -> Result<serde_json::Value, String> {
  let state = state.read().await;
  let client = reqwest::Client::new();
  let endpoint = if friendly {
    "/devices/?friendly=true"
  } else {
    "/devices/"
  };
  let url = format!("{}{}", state.get_base_url(), endpoint);

  let response = client.get(&url).send().await.map_err(|e| e.to_string())?;

  response
    .json::<serde_json::Value>()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_change_device(
  state: State<'_, DaemonState>,
  device_id: String,
) -> Result<String, String> {
  let state = state.read().await;
  let client = reqwest::Client::new();
  let url = format!("{}/change-device/{}", state.get_base_url(), device_id);

  let response = client.post(&url).send().await.map_err(|e| e.to_string())?;

  response.text().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_play(state: State<'_, DaemonState>) -> Result<ActionResponse, String> {
  let client = reqwest::Client::new();
  let url = format!("{}/action/play", state.read().await.get_base_url());

  let response = client.post(&url).send().await.map_err(|e| e.to_string())?;

  response
    .json::<ActionResponse>()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_pause(state: State<'_, DaemonState>) -> Result<ActionResponse, String> {
  let state = state.read().await;
  let client = reqwest::Client::new();
  let url = format!("{}/action/pause", state.get_base_url());

  let response = client.post(&url).send().await.map_err(|e| e.to_string())?;

  response
    .json::<ActionResponse>()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_next(
  state: State<'_, DaemonState>,
  times: i32,
  ignore_timestamps: bool,
) -> Result<ActionResponse, String> {
  let state = state.read().await;
  let client = reqwest::Client::new();
  let mut url = format!("{}/action/next?times={}", state.get_base_url(), times);

  if ignore_timestamps {
    url.push_str("&ignore_timestamps");
  }

  let response = client.post(&url).send().await.map_err(|e| e.to_string())?;

  response
    .json::<ActionResponse>()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_prev(
  state: State<'_, DaemonState>,
  times: i32,
  ignore_timestamps: bool,
) -> Result<ActionResponse, String> {
  let state = state.read().await;
  let client = reqwest::Client::new();
  let mut url = format!("{}/action/prev?times={}", state.get_base_url(), times);

  if ignore_timestamps {
    url.push_str("&ignore_timestamps");
  }

  let response = client.post(&url).send().await.map_err(|e| e.to_string())?;

  response
    .json::<ActionResponse>()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_stop(state: State<'_, DaemonState>) -> Result<ActionResponse, String> {
  let state = state.read().await;
  let client = reqwest::Client::new();
  let url = format!("{}/action/stop", state.get_base_url());

  let response = client.post(&url).send().await.map_err(|e| e.to_string())?;

  response
    .json::<ActionResponse>()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_toggle_repeat(state: State<'_, DaemonState>) -> Result<ActionResponse, String> {
  let state = state.read().await;
  let client = reqwest::Client::new();
  let url = format!("{}/action/repeat", state.get_base_url());

  let response = client.post(&url).send().await.map_err(|e| e.to_string())?;

  response
    .json::<ActionResponse>()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_toggle_shuffle(state: State<'_, DaemonState>) -> Result<ActionResponse, String> {
  let state = state.read().await;
  let client = reqwest::Client::new();
  let url = format!("{}/action/shuffle", state.get_base_url());

  let response = client.post(&url).send().await.map_err(|e| e.to_string())?;

  response
    .json::<ActionResponse>()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_get_state(state: State<'_, DaemonState>) -> Result<PlayerStatus, String> {
  let state = state.read().await;
  let client = reqwest::Client::new();
  let url = format!("{}/state/", state.get_base_url());

  let response = client.get(&url).send().await.map_err(|e| e.to_string())?;

  response
    .json::<PlayerStatus>()
    .await
    .map_err(|e| e.to_string())
}

#[derive(Serialize, Deserialize, Default)]
pub struct PlayUrisOptions {
  #[serde(skip_serializing_if = "Option::is_none")]
  pub uris: Option<Vec<String>>,
  #[serde(skip_serializing_if = "Option::is_none")]
  pub uri: Option<String>,
  #[serde(skip_serializing_if = "Option::is_none")]
  pub queue: Option<bool>,
  #[serde(skip_serializing_if = "Option::is_none")]
  pub play_next: Option<bool>,
  #[serde(skip_serializing_if = "Option::is_none")]
  pub device: Option<String>,
}

#[tauri::command]
pub async fn api_play_uris(
  state: State<'_, DaemonState>,
  options: PlayUrisOptions,
) -> Result<PlayerStatus, String> {
  let state = state.read().await;
  let client = reqwest::Client::new();
  let url = format!("{}/play/", state.get_base_url());

  let response = client
    .post(&url)
    .json(&options)
    .send()
    .await
    .map_err(|e| e.to_string())?;

  response
    .json::<PlayerStatus>()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_exit(state: State<'_, DaemonState>) -> Result<PlayerStatus, String> {
  let state = state.read().await;
  let client = reqwest::Client::new();
  let url = format!("{}/exit/", state.get_base_url());

  let response = client.post(&url).send().await.map_err(|e| e.to_string())?;

  response
    .json::<PlayerStatus>()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_change_setting(
  state: State<'_, DaemonState>,
  setting_name: String,
  value: serde_json::Value,
) -> Result<String, String> {
  let state = state.read().await;
  let client = reqwest::Client::new();
  let url = format!("{}/change-setting/", state.get_base_url());

  let mut payload = HashMap::new();
  payload.insert("setting_name", serde_json::Value::String(setting_name));
  payload.insert("value", value);

  let response = client
    .post(&url)
    .json(&payload)
    .send()
    .await
    .map_err(|e| e.to_string())?;

  response.text().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_refresh_devices(state: State<'_, DaemonState>) -> Result<String, String> {
  let state = state.read().await;
  let client = reqwest::Client::new();
  let url = format!("{}/refresh-devices/", state.get_base_url());

  let response = client.get(&url).send().await.map_err(|e| e.to_string())?;

  response.text().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_rescan_library(state: State<'_, DaemonState>) -> Result<String, String> {
  let state = state.read().await;
  let client = reqwest::Client::new();
  let url = format!("{}/rescan-library/", state.get_base_url());

  let response = client.get(&url).send().await.map_err(|e| e.to_string())?;

  response.text().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_set_timer(state: State<'_, DaemonState>, value: String) -> Result<String, String> {
  let state = state.read().await;
  let client = reqwest::Client::new();
  let url = format!("{}/timer/", state.get_base_url());

  let response = client
    .post(&url)
    .header("Content-Type", "text/plain")
    .body(value)
    .send()
    .await
    .map_err(|e| e.to_string())?;

  response.text().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_get_timer(state: State<'_, DaemonState>) -> Result<String, String> {
  let state = state.read().await;
  let client = reqwest::Client::new();
  let url = format!("{}/timer/", state.get_base_url());

  let response = client.get(&url).send().await.map_err(|e| e.to_string())?;

  response.text().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_cancel_timer(state: State<'_, DaemonState>) -> Result<String, String> {
  api_set_timer(state, "cancel".to_string()).await
}

#[tauri::command]
pub async fn api_get_file_url(
  state: State<'_, DaemonState>,
  file_path: String,
  thumbnail_only: bool,
  api_key: Option<String>,
) -> Result<String, ()> {
  let state = state.read().await;
  let mut url = format!("{}/file/?path={}", state.get_base_url(), file_path);

  if thumbnail_only {
    url.push_str("&thumbnail_only=true");
  }

  if let Some(key) = api_key {
    url.push_str(&format!("&api_key={}", key));
  }

  Ok(url)
}

#[tauri::command]
pub async fn api_get_stream_url(
  state: State<'_, DaemonState>,
  file_path: String,
  api_key: Option<String>,
) -> Result<String, ()> {
  let state = state.read().await;
  let mut url = format!("{}/file?path={}", state.get_base_url(), file_path);

  if let Some(key) = api_key {
    url.push_str(&format!("&api_key={}", key));
  }

  Ok(url)
}

#[tauri::command]
pub async fn api_get_album_art_url(state: State<'_, DaemonState>) -> Result<String, String> {
  let state = state.read().await;
  let client = reqwest::Client::new();
  let url = format!("{}/album-art/", state.get_base_url());

  let response = client.get(&url).send().await.map_err(|e| e.to_string())?;
  let bytes = response.bytes().await.map_err(|e| e.to_string())?;

  let base64_image = base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &bytes);
  Ok(format!("data:image/png;base64,{}", base64_image))
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ModifyQueue {
  pub action: ModifyQueueAction,
  pub indices: Vec<u64>,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ModifyQueueAction {
  NextUp,
  Remove,
}

#[tauri::command]
pub async fn api_modify_queue(
  state: State<'_, DaemonState>,
  indices: Vec<u64>,
  action: ModifyQueueAction,
) -> Result<(), String> {
  let (api_key, base_url) = {
    let guard = state.read().await;
    (
      guard.api_key.clone().ok_or("API Key not set".to_string())?,
      guard.get_base_url(),
    )
  };
  let client = reqwest::Client::new();
  let url = format!("{}/modify-queue/", base_url);
  let payload = ModifyQueue { action, indices };

  let _ = client
    .post(&url)
    .header("x-api-key", api_key)
    .json(&payload)
    .send()
    .await
    .map_err(|e| e.to_string())?;
  Ok(())
}

pub async fn poll_player_state(app_handle: tauri::AppHandle) {
  let mut interval = tokio::time::interval(tokio::time::Duration::from_millis(500));

  loop {
    interval.tick().await;

    if let Some(daemon_state) = app_handle.try_state::<DaemonState>() {
      if let Some(player_state) = app_handle.try_state::<PlayerState>() {
        let client = reqwest::Client::new();
        let url = format!("{}/state/", daemon_state.read().await.get_base_url());

        let request = client.get(&url);

        match request.send().await {
          Ok(response) => match response.json::<PlayerStatus>().await {
            Ok(new_state) => {
              {
                let mut daemon_state_mut = daemon_state.write().await;
                daemon_state_mut.is_running = true;
                if daemon_state_mut.api_key.is_none() {
                  log::info!("[Player State Poll] first successful poll");
                  let settings = crate::settings::Settings::load(&app_handle);
                  let mut guard = app_handle
                    .state::<Mutex<Settings>>()
                    .inner()
                    .lock()
                    .unwrap();
                  *guard = settings;
                  daemon_state_mut.api_key = Some(guard.api_key.clone());
                }
              };

              let (state_changed, tray_needs_update) = {
                let player_state = player_state.read().await;
                let changed = *player_state != new_state;
                let tray_update = player_state.status != new_state.status
                  || player_state.lang != new_state.lang;
                (changed, tray_update)
              };

              if tray_needs_update {
                tray_update(app_handle.clone(), &new_state);
              }

              if state_changed {
								let mut player_state = player_state.write().await;
								*player_state = new_state.clone();
                if let Err(e) = app_handle.emit("playerStateChanged", &new_state) {
                  log::error!("[Player State Poll] Failed to emit event: {}", e);
                } else {
                  log::info!("[Player State Poll] emitted playerStateChanged event");
                }
              } else {
                log::info!("[Player State Poll] player state has not changed");
              }
            }
            Err(e) => {
              log::error!("[Player State Poll] Failed to parse state: {}", e);
              daemon_state.write().await.is_running = false;
            }
          },
          Err(e) => {
            log::error!("[Player State Poll] Failed to fetch state: {}", e);
            daemon_state.write().await.is_running = false;
          }
        }
      } else {
        log::error!("[Player State Poll] ApiState not found");
        break;
      }
    }
  }
}
