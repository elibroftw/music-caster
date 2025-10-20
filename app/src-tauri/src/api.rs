use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tauri_plugin_http::reqwest;

#[derive(Debug, Serialize, Deserialize)]
pub struct PlayerState {
  pub status: String,
  pub volume: i32,
  pub lang: String,
  pub title: String,
  pub artist: String,
  pub album: String,
  pub gui_open: bool,
  pub track_position: f64,
  pub track_length: f64,
  pub queue_length: i32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ActionResponse {
  pub message: String,
}

fn get_base_url() -> String {
  "http://localhost:2001".to_string()
}

#[tauri::command]
pub async fn api_is_running() -> Result<bool, String> {
  let client = reqwest::Client::new();
  let url = format!("{}/running/", get_base_url());

  match client.get(&url).send().await {
    Ok(response) => {
      let text = response.text().await.map_err(|e| e.to_string())?;
      Ok(text == "true")
    }
    Err(_) => Ok(false),
  }
}

#[tauri::command]
pub async fn api_activate() -> Result<ActionResponse, String> {
  let client = reqwest::Client::new();
  let url = format!("{}/action/activate", get_base_url());

  let response = client.post(&url).send().await.map_err(|e| e.to_string())?;

  response
    .json::<ActionResponse>()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_get_devices(friendly: bool) -> Result<serde_json::Value, String> {
  let client = reqwest::Client::new();
  let endpoint = if friendly {
    "/devices/?friendly=true"
  } else {
    "/devices/"
  };
  let url = format!("{}{}", get_base_url(), endpoint);

  let response = client.get(&url).send().await.map_err(|e| e.to_string())?;

  response
    .json::<serde_json::Value>()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_change_device(device_id: String) -> Result<String, String> {
  let client = reqwest::Client::new();
  let url = format!("{}/change-device/{}", get_base_url(), device_id);

  let response = client.post(&url).send().await.map_err(|e| e.to_string())?;

  response.text().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_play() -> Result<ActionResponse, String> {
  let client = reqwest::Client::new();
  let url = format!("{}/action/play", get_base_url());

  let response = client.post(&url).send().await.map_err(|e| e.to_string())?;

  response
    .json::<ActionResponse>()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_pause() -> Result<ActionResponse, String> {
  let client = reqwest::Client::new();
  let url = format!("{}/action/pause", get_base_url());

  let response = client.post(&url).send().await.map_err(|e| e.to_string())?;

  response
    .json::<ActionResponse>()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_next(times: i32, ignore_timestamps: bool) -> Result<ActionResponse, String> {
  let client = reqwest::Client::new();
  let mut url = format!("{}/action/next?times={}", get_base_url(), times);

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
pub async fn api_prev(times: i32, ignore_timestamps: bool) -> Result<ActionResponse, String> {
  let client = reqwest::Client::new();
  let mut url = format!("{}/action/prev?times={}", get_base_url(), times);

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
pub async fn api_toggle_repeat() -> Result<ActionResponse, String> {
  let client = reqwest::Client::new();
  let url = format!("{}/action/repeat", get_base_url());

  let response = client.post(&url).send().await.map_err(|e| e.to_string())?;

  response
    .json::<ActionResponse>()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_toggle_shuffle() -> Result<ActionResponse, String> {
  let client = reqwest::Client::new();
  let url = format!("{}/action/shuffle", get_base_url());

  let response = client.post(&url).send().await.map_err(|e| e.to_string())?;

  response
    .json::<ActionResponse>()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_get_state() -> Result<PlayerState, String> {
  let client = reqwest::Client::new();
  let url = format!("{}/state/", get_base_url());

  let response = client.get(&url).send().await.map_err(|e| e.to_string())?;

  response
    .json::<PlayerState>()
    .await
    .map_err(|e| e.to_string())
}

#[derive(Serialize, Deserialize)]
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
pub async fn api_play_uris(options: PlayUrisOptions) -> Result<PlayerState, String> {
  let client = reqwest::Client::new();
  let url = format!("{}/play/", get_base_url());

  let response = client
    .post(&url)
    .json(&options)
    .send()
    .await
    .map_err(|e| e.to_string())?;

  response
    .json::<PlayerState>()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_exit() -> Result<PlayerState, String> {
  let client = reqwest::Client::new();
  let url = format!("{}/exit/", get_base_url());

  let response = client.post(&url).send().await.map_err(|e| e.to_string())?;

  response
    .json::<PlayerState>()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_change_setting(
  setting_name: String,
  value: serde_json::Value,
) -> Result<String, String> {
  let client = reqwest::Client::new();
  let url = format!("{}/change-setting/", get_base_url());

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
pub async fn api_refresh_devices() -> Result<String, String> {
  let client = reqwest::Client::new();
  let url = format!("{}/refresh-devices/", get_base_url());

  let response = client.get(&url).send().await.map_err(|e| e.to_string())?;

  response.text().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_rescan_library() -> Result<String, String> {
  let client = reqwest::Client::new();
  let url = format!("{}/rescan-library/", get_base_url());

  let response = client.get(&url).send().await.map_err(|e| e.to_string())?;

  response.text().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_set_timer(value: String) -> Result<String, String> {
  let client = reqwest::Client::new();
  let url = format!("{}/timer/", get_base_url());

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
pub async fn api_get_timer() -> Result<String, String> {
  let client = reqwest::Client::new();
  let url = format!("{}/timer/", get_base_url());

  let response = client.get(&url).send().await.map_err(|e| e.to_string())?;

  response.text().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn api_cancel_timer() -> Result<String, String> {
  api_set_timer("cancel".to_string()).await
}

#[tauri::command]
pub fn api_get_file_url(
  file_path: String,
  thumbnail_only: bool,
  api_key: Option<String>,
) -> String {
  let mut url = format!("{}/file/?path={}", get_base_url(), file_path);

  if thumbnail_only {
    url.push_str("&thumbnail_only=true");
  }

  if let Some(key) = api_key {
    url.push_str(&format!("&api_key={}", key));
  }

  url
}

#[tauri::command]
pub fn api_get_stream_url(file_path: String, api_key: Option<String>) -> String {
  let mut url = format!("{}/file?path={}", get_base_url(), file_path);

  if let Some(key) = api_key {
    url.push_str(&format!("&api_key={}", key));
  }

  url
}
