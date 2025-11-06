use serde::{Deserialize, Serialize};
use tauri::{self, Manager};

#[derive(Clone, Serialize, Deserialize)]
struct Settings {
	api_key: String
}

impl Settings {
	fn path(app_handle: &tauri::AppHandle) -> String {
		let app_data_dir = app_handle
      .path()
      .app_data_dir()
      .map_err(|e| format!("Failed to get app data directory: {}", e))
      .unwrap();
		app_data_dir.join("settings.json").display().to_string()
	}

	fn load(app_handle: &tauri::AppHandle) -> Self {
		match std::fs::File::open(Self::path(app_handle)) {
			Ok(file) => {
				let reader = std::io::BufReader::new(file);
				let settings: Settings = serde_json::from_reader(reader).unwrap();
				settings
			},
			Err(err) => {
				// TODO: handle not found error
				// if failed, create settings.json and set api_key to random 20 letter
			}
		}
	}
}
