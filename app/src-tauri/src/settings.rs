use serde::{Deserialize, Serialize};
use tauri::{self, Manager};
use std::io::Write;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Clone, Serialize, Deserialize)]
pub struct Settings {
	pub api_key: String
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

		let chars: Vec<char> = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789".chars().collect();
		let mut result = String::new();
		let mut current_seed = seed;

		for _ in 0..20 {
			current_seed = current_seed.wrapping_mul(6364136223846793005).wrapping_add(1);
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
			},
			Err(_) => {
				Self::create_default(app_handle)
			}
		}
	}

	fn create_default(app_handle: &tauri::AppHandle) -> Self {
		let settings = Settings {
			api_key: Self::generate_api_key(),
		};

		let path = Self::path(app_handle);
		if let Ok(mut file) = std::fs::File::create(&path) {
			let json = serde_json::to_string_pretty(&settings).unwrap();
			let _ = file.write_all(json.as_bytes());
		}

		settings
	}
}
