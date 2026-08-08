use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::{self, Manager};

#[derive(Clone, Serialize, Deserialize)]
pub struct Settings {
  pub api_key: String,
  pub gui_exits_app: bool,
  #[serde(default)]
  pub music_folders: Vec<String>,
  #[serde(default)]
  pub playlists: BTreeMap<String, serde_json::Value>,
  /// id of the device the daemon is playing on, `None` means the local device
  #[serde(default)]
  pub device: Option<String>,
}

/// never handed to the frontend: secrets, and bulk the settings UI has no use for
const PRIVATE_SETTING_KEYS: [&str; 5] = ["api_key", "upload_pw", "queues", "playlists", "skips"];

/// the daemon's settings.json as-is (minus the keys above), so the settings UI can
/// show current values without this layer needing to know every setting's type.
/// the daemon rewrites the file on every change, so this is read fresh each call
#[tauri::command]
pub fn api_get_settings(app: tauri::AppHandle) -> Result<serde_json::Value, String> {
  let path = Settings::path(&app);
  let file =
    std::fs::File::open(&path).map_err(|e| format!("Failed to open {}: {}", path, e))?;
  let mut value: serde_json::Value = serde_json::from_reader(std::io::BufReader::new(file))
    .map_err(|e| format!("Failed to parse {}: {}", path, e))?;

  if let Some(map) = value.as_object_mut() {
    for key in PRIVATE_SETTING_KEYS {
      map.remove(key);
    }
  }
  Ok(value)
}

impl Settings {
  pub fn path(app_handle: &tauri::AppHandle) -> String {
    let app_data_dir = app_handle
      .path()
      .app_data_dir()
      .map_err(|e| format!("Failed to get app data directory: {}", e))
      .unwrap();
    app_data_dir.join("settings.json").display().to_string()
  }

  fn generate_api_key() -> String {
    let start = SystemTime::now();
    let since_the_epoch = start
      .duration_since(UNIX_EPOCH)
      .expect("Time went backwards");
    let seed = since_the_epoch.as_nanos();

    let chars: Vec<char> = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
      .chars()
      .collect();
    let mut result = String::new();
    let mut current_seed = seed;

    for _ in 0..20 {
      current_seed = current_seed
        .wrapping_mul(6364136223846793005)
        .wrapping_add(1);
      let idx = (current_seed % (chars.len() as u128)) as usize;
      result.push(chars[idx]);
    }
    result
  }

  pub fn load(app_handle: &tauri::AppHandle) -> Self {
    let path = Self::path(app_handle);
    match std::fs::File::open(&path) {
      Ok(file) => {
        let reader = std::io::BufReader::new(file);
        match serde_json::from_reader(reader) {
          Ok(settings) => settings,
          Err(_) => Self::create_default(app_handle),
        }
      }
      Err(_) => Self::create_default(app_handle),
    }
  }

  fn create_default(_app_handle: &tauri::AppHandle) -> Self {
    let settings = Settings {
      api_key: Self::generate_api_key(),
      gui_exits_app: false,
      music_folders: Vec::new(),
      playlists: BTreeMap::new(),
      device: None,
    };

    // DO NOT WRITE NEW FILE YET, AS DAEMON WILL OVERWRITE IT
    // 	DUE TO MISSING SETTINGS FIELDS
    // let path = Self::path(app_handle);
    // if let Ok(mut file) = std::fs::File::create(&path) {
    // 	let json = serde_json::to_string_pretty(&settings).unwrap();
    // 	let _ = file.write_all(json.as_bytes());
    // }

    settings
  }
}
