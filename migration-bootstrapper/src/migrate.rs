//! UI-independent migration core.
//!
//! This is the part that must be rock-solid: it resolves the latest Tauri MSI from
//! GitHub, uninstalls the existing (Inno-based, v5) Music Caster, downloads the MSI and
//! launches it. It deliberately has **no** dependency on the GUI so that the volatile
//! `windows-reactor` API in `main.rs` cannot break the actual migration.
//!
//! Everything is derived from the current working directory + the GitHub API, so the
//! bootstrapper also works when it is downloaded and run standalone — the uninstall step
//! is simply skipped if no existing install is found.

use std::fs::File;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process::Command;

use serde::Deserialize;

const RELEASES_URL: &str =
    "https://api.github.com/repos/elibroftw/music-caster/releases/latest";
const USER_AGENT: &str = "MusicCasterMigrationBootstrapper";
/// Inno Setup drops its uninstaller next to the executable with this fixed name.
const INNO_UNINSTALLER: &str = "unins000.exe";

/// Progress events emitted by [`migrate`]. The UI renders these; the core never touches
/// the screen itself.
#[derive(Clone, Debug)]
pub enum Progress {
    /// Querying the GitHub releases API for the latest MSI.
    Resolving,
    /// Downloading the MSI. `total` is `None` when the server omits Content-Length.
    Downloading { downloaded: u64, total: Option<u64> },
    /// Running the old uninstaller.
    Uninstalling,
    /// Launching the new MSI installer.
    Installing { version: String },
    /// Migration handed off to msiexec successfully; the bootstrapper may now exit.
    Done,
    /// Fatal error; the message is user-facing.
    Error(String),
}

#[derive(Deserialize)]
struct Release {
    tag_name: String,
    assets: Vec<Asset>,
}

#[derive(Deserialize)]
struct Asset {
    name: String,
    browser_download_url: String,
}

/// Maps the host architecture to the token Tauri embeds in bundle file names
/// (`Music.Caster_6.0.0_<token>_en-US.msi`).
pub fn host_arch_token() -> &'static str {
    match std::env::consts::ARCH {
        "aarch64" => "arm64",
        // Tauri/WiX uses "x64" for 64-bit Intel; default there for anything else 64-bit.
        _ => "x64",
    }
}

/// Returns `(version, msi_download_url)` for the latest release, matching the host
/// architecture. Errors if the release has no MSI for this architecture.
pub fn latest_msi() -> Result<(String, String), String> {
    let release: Release = ureq::get(RELEASES_URL)
        .header("User-Agent", USER_AGENT)
        .call()
        .map_err(|e| format!("Could not reach GitHub: {e}"))?
        .body_mut()
        .read_json()
        .map_err(|e| format!("Could not parse the release info: {e}"))?;

    let version = release.tag_name.trim_start_matches('v').to_string();
    let arch = host_arch_token();
    let msi_url = release
        .assets
        .iter()
        .find(|a| {
            let name = a.name.to_ascii_lowercase();
            name.ends_with(".msi") && name.contains(arch)
        })
        .map(|a| a.browser_download_url.clone())
        .ok_or_else(|| format!("No {arch} MSI installer was found in the latest release."))?;

    Ok((version, msi_url))
}

/// Streams `url` to `dest`, reporting byte progress as it goes.
fn download(url: &str, dest: &Path, on_progress: &dyn Fn(Progress)) -> Result<(), String> {
    let response = ureq::get(url)
        .header("User-Agent", USER_AGENT)
        .call()
        .map_err(|e| format!("Download failed: {e}"))?;

    let total: Option<u64> = response
        .headers()
        .get("content-length")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.parse().ok());

    let mut reader = response.into_body().into_reader();
    let mut file = File::create(dest).map_err(|e| format!("Could not write the MSI: {e}"))?;

    let mut buf = [0u8; 64 * 1024];
    let mut downloaded: u64 = 0;
    loop {
        let n = reader
            .read(&mut buf)
            .map_err(|e| format!("Download interrupted: {e}"))?;
        if n == 0 {
            break;
        }
        file.write_all(&buf[..n])
            .map_err(|e| format!("Could not write the MSI: {e}"))?;
        downloaded += n as u64;
        on_progress(Progress::Downloading { downloaded, total });
    }
    file.flush().map_err(|e| format!("Could not finalize the MSI: {e}"))?;
    Ok(())
}

/// Locates and runs the existing uninstaller, waiting for it to finish. A missing
/// uninstaller is **not** an error (standalone runs, or already-removed installs).
fn run_uninstaller() -> Result<(), String> {
    // Prefer the uninstaller sitting in the current working directory: when the
    // bootstrapper is launched by Music Caster, the CWD is the install dir.
    let cwd_uninstaller = std::env::current_dir()
        .map(|d| d.join(INNO_UNINSTALLER))
        .ok()
        .filter(|p| p.exists())
        .map(UninstallCommand::from_path);

    // Fallback: if the uninstaller is not next to us (e.g. the bootstrapper was downloaded
    // standalone into Downloads), recover the uninstall command from the Windows registry.
    let uninstaller = cwd_uninstaller.or_else(registry_uninstaller);

    match uninstaller {
        Some(UninstallCommand { program, args }) => {
            Command::new(program)
                .args(args)
                // Inno: silent, no message boxes, don't reboot. Harmless for an MSI string.
                .args(["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"])
                .status()
                .map_err(|e| format!("Uninstaller failed to launch: {e}"))?;
            Ok(())
        }
        // Nothing to uninstall — proceed straight to install.
        None => Ok(()),
    }
}

struct UninstallCommand {
    program: PathBuf,
    args: Vec<String>,
}

impl UninstallCommand {
    fn from_path(path: PathBuf) -> Self {
        Self { program: path, args: Vec::new() }
    }
}

/// Launches the MSI via msiexec without waiting, so the bootstrapper can exit while the
/// install proceeds. `/passive` shows a minimal progress bar but needs no user input.
fn run_installer(msi_path: &Path) -> Result<(), String> {
    Command::new("msiexec")
        .arg("/i")
        .arg(msi_path)
        .args(["/passive", "/norestart"])
        .spawn()
        .map_err(|e| format!("Installer failed to launch: {e}"))?;
    Ok(())
}

/// Orchestrates the full migration, emitting [`Progress`] events for the UI. Returns
/// `Ok(())` once msiexec has been launched; the caller should then exit the process.
pub fn migrate(on_event: &dyn Fn(Progress)) -> Result<(), String> {
    on_event(Progress::Resolving);
    let (version, msi_url) = latest_msi()?;

    let dest = std::env::temp_dir().join(format!("MusicCaster_{version}.msi"));
    on_event(Progress::Downloading { downloaded: 0, total: None });
    download(&msi_url, &dest, on_event)?;

    on_event(Progress::Uninstalling);
    run_uninstaller()?;

    on_event(Progress::Installing { version });
    run_installer(&dest)?;

    on_event(Progress::Done);
    Ok(())
}

// ---------------------------------------------------------------------------
// Registry fallback for locating the uninstaller when it is not in the CWD.
// ---------------------------------------------------------------------------

use windows::Win32::Foundation::{ERROR_SUCCESS, MAX_PATH};
use windows::Win32::System::Registry::{
    HKEY, HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE, KEY_READ, KEY_WOW64_32KEY, KEY_WOW64_64KEY,
    RegCloseKey, RegEnumKeyExW, RegOpenKeyExW, RegQueryValueExW, REG_SAM_FLAGS, REG_VALUE_TYPE,
};
use windows::core::{PCWSTR, PWSTR};

const UNINSTALL_ROOT: &str =
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall";

/// Searches the standard Uninstall registry hives for a Music Caster entry and returns its
/// uninstall command (preferring `QuietUninstallString`). Returns `None` if not found.
fn registry_uninstaller() -> Option<UninstallCommand> {
    // Cover both hives and both registry views (64-bit installer on 64-bit OS, plus the
    // 32-bit WOW6432Node view that the old PyInstaller build may have written to).
    let hives = [HKEY_LOCAL_MACHINE, HKEY_CURRENT_USER];
    let views = [KEY_WOW64_64KEY, KEY_WOW64_32KEY];
    for hive in hives {
        for view in views {
            if let Some(cmd) = search_uninstall_hive(hive, view) {
                return Some(cmd);
            }
        }
    }
    None
}

fn search_uninstall_hive(hive: HKEY, view: REG_SAM_FLAGS) -> Option<UninstallCommand> {
    let root = open_key(hive, UNINSTALL_ROOT, KEY_READ | view)?;
    let mut index = 0u32;
    let result = loop {
        let mut name_buf = [0u16; MAX_PATH as usize];
        let mut name_len = name_buf.len() as u32;
        let rc = unsafe {
            RegEnumKeyExW(
                root,
                index,
                Some(PWSTR(name_buf.as_mut_ptr())),
                &mut name_len,
                None,
                None,
                None,
                None,
            )
        };
        if rc != ERROR_SUCCESS {
            break None;
        }
        index += 1;

        let subkey_name = String::from_utf16_lossy(&name_buf[..name_len as usize]);
        let Some(subkey) = open_key(root, &format!("{UNINSTALL_ROOT}\\{subkey_name}"), KEY_READ | view)
        else {
            continue;
        };

        let display_name = read_string(subkey, "DisplayName").unwrap_or_default();
        if display_name.to_ascii_lowercase().contains("music caster") {
            let cmd = read_string(subkey, "QuietUninstallString")
                .or_else(|| read_string(subkey, "UninstallString"))
                .map(parse_uninstall_string);
            unsafe { let _ = RegCloseKey(subkey); }
            if let Some(cmd) = cmd {
                break Some(cmd);
            }
            continue;
        }
        unsafe { let _ = RegCloseKey(subkey); }
    };
    unsafe { let _ = RegCloseKey(root); }
    result
}

/// Splits a registry uninstall string into a program path and arguments. Handles the
/// common `"C:\...\unins000.exe" /flags` quoting.
fn parse_uninstall_string(s: String) -> UninstallCommand {
    let s = s.trim();
    if let Some(rest) = s.strip_prefix('"') {
        if let Some(end) = rest.find('"') {
            let program = PathBuf::from(&rest[..end]);
            let args = rest[end + 1..]
                .split_whitespace()
                .map(String::from)
                .collect();
            return UninstallCommand { program, args };
        }
    }
    // Unquoted: take the first whitespace-delimited token as the program.
    let mut parts = s.split_whitespace();
    match parts.next() {
        Some(program) => UninstallCommand {
            program: PathBuf::from(program),
            args: parts.map(String::from).collect(),
        },
        None => UninstallCommand::from_path(PathBuf::from(s)),
    }
}

fn open_key(parent: HKEY, subkey: &str, access: REG_SAM_FLAGS) -> Option<HKEY> {
    let wide = wide(subkey);
    let mut handle = HKEY::default();
    let rc = unsafe {
        RegOpenKeyExW(parent, PCWSTR(wide.as_ptr()), Some(0), access, &mut handle)
    };
    (rc == ERROR_SUCCESS).then_some(handle)
}

fn read_string(key: HKEY, value: &str) -> Option<String> {
    let wide_value = wide(value);
    let mut kind = REG_VALUE_TYPE::default();
    let mut size: u32 = 0;
    // First call sizes the buffer.
    let rc = unsafe {
        RegQueryValueExW(
            key,
            PCWSTR(wide_value.as_ptr()),
            None,
            Some(&mut kind),
            None,
            Some(&mut size),
        )
    };
    if rc != ERROR_SUCCESS || size == 0 {
        return None;
    }
    let mut buf = vec![0u8; size as usize];
    let rc = unsafe {
        RegQueryValueExW(
            key,
            PCWSTR(wide_value.as_ptr()),
            None,
            Some(&mut kind),
            Some(buf.as_mut_ptr()),
            Some(&mut size),
        )
    };
    if rc != ERROR_SUCCESS {
        return None;
    }
    // REG_SZ is a wide string; reinterpret the byte buffer as u16 and trim the NUL.
    let u16s: Vec<u16> = buf
        .chunks_exact(2)
        .map(|c| u16::from_le_bytes([c[0], c[1]]))
        .take_while(|&c| c != 0)
        .collect();
    Some(String::from_utf16_lossy(&u16s))
}

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}
