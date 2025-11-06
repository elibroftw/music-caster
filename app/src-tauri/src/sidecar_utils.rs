use std::collections::VecDeque;
use std::marker::PhantomData;
use std::sync::Mutex;
use sysinfo::{Pid, Signal, System};
use tauri::{self, Manager};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};

pub trait SidecarConfig {
  fn binary_name() -> &'static str;

  fn args(app_handle: &tauri::AppHandle) -> Vec<String>;
}

// TODO: create a SidecarManager that can manage spawning and despawning sidecars based on Enums
/// A generic wrapper for managing sidecar processes with automatic cleanup
/// Usage:
/// 	let process = SidecarProcess::<MusicCasterDaemon>::new(&app_handle)?;
#[derive(Debug)]
pub struct SidecarProcess<T: SidecarConfig> {
  child: Option<CommandChild>,
  _phantom: PhantomData<T>,
}

impl<T: SidecarConfig> SidecarProcess<T> {
  /// Create and spawn a new sidecar process
  pub fn new(app_handle: &tauri::AppHandle) -> Result<Mutex<Self>, String> {
    let sidecar_command = app_handle
      .shell()
      .sidecar(T::binary_name())
      .map_err(|e| format!("Failed to create sidecar command: {}", e))?
      .args(T::args(app_handle));

    let (mut rx, child) = sidecar_command
      .spawn()
      .map_err(|e| format!("Failed to spawn {}: {}", T::binary_name(), e))?;

    // Spawn async task to handle process output
    let binary_name = T::binary_name().to_string();
    tauri::async_runtime::spawn(async move {
      while let Some(event) = rx.recv().await {
        match event {
          CommandEvent::Stdout(line_bytes) => {
            let line = String::from_utf8_lossy(&line_bytes);
            log::info!("[{}] {}", binary_name, line);
          }
          CommandEvent::Stderr(line_bytes) => {
            let line = String::from_utf8_lossy(&line_bytes);
            log::error!("[{} Error] {}", binary_name, line);
          }
          CommandEvent::Error(err) => {
            log::error!("[{}] Error: {}", binary_name, err);
          }
          CommandEvent::Terminated(payload) => {
            log::info!("[{}] Terminated with code: {:?}", binary_name, payload.code);
            break;
          }
          _ => {}
        }
      }
    });

    Ok(Mutex::new(SidecarProcess {
      child: Some(child),
      _phantom: PhantomData,
    }))
  }

  /// Get the process ID of the sidecar
  pub fn pid(&self) -> Option<u32> {
    self.child.as_ref().map(|c| c.pid())
  }

  /// Kill the sidecar process and all its descendants
  pub fn kill(&mut self) -> Result<(), String> {
    if let Some(child) = self.child.take() {
      kill_process_tree(child.pid())
    } else {
      Ok(())
    }
  }
}

impl<T: SidecarConfig> Drop for SidecarProcess<T> {
  fn drop(&mut self) {
    if self.child.is_some() {
      let _ = self.kill();
    }
  }
}

fn kill_process_tree(pid: u32) -> Result<(), String> {
  let mut system = System::new_all();
  system.refresh_all();

  let root_pid = Pid::from_u32(pid);

  // Collect all descendant PIDs
  let to_kill = collect_descendants(&system, root_pid);

  // Kill all processes (children first, then parent)
  for &pid in &to_kill {
    if let Some(process) = system.process(pid) {
      process.kill_with(Signal::Kill);
    }
  }

  Ok(())
}

fn collect_descendants(system: &System, root_pid: Pid) -> VecDeque<Pid> {
  let mut descendants = VecDeque::new();
  let mut queue = VecDeque::new();
  queue.push_back(root_pid);

  while let Some(current_pid) = queue.pop_front() {
    descendants.push_front(current_pid);
    // Find all direct children of current_pid
    for (child_pid, process) in system.processes() {
      if let Some(parent_pid) = process.parent() {
        if parent_pid == current_pid {
          queue.push_back(*child_pid);
        }
      }
    }
  }
  descendants
}

pub struct MusicCasterDaemon {}

impl SidecarConfig for MusicCasterDaemon {
  fn binary_name() -> &'static str {
    "music-caster-daemon"
  }

  fn args(app_handle: &tauri::AppHandle) -> Vec<String> {
    let app_args: Vec<String> = std::env::args().skip(1).collect();

    let app_data_dir = app_handle
      .path()
      .app_data_dir()
      .map_err(|e| format!("Failed to get app data directory: {}", e))
      .unwrap();

    std::fs::create_dir_all(&app_data_dir)
      .map_err(|e| format!("Failed to create app data directory: {}", e))
      .unwrap();

    let db_path = app_data_dir.join("music_caster.db").display().to_string();
    let settings_path = app_data_dir.join("settings.json").display().to_string();

		// TODO: try reading Settings file and setting Settings state

    log::info!("settings path: {}", &settings_path);
    log::info!("db_path: {}", &db_path);

    let mut sidecar_args = vec![
      "--db-path".to_string(),
      db_path,
      "--settings-path".to_string(),
      settings_path,
    ];
    sidecar_args.extend(app_args);
    sidecar_args
  }
}
