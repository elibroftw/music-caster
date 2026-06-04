use std::fs::File;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process::Command;

use serde::Deserialize;

const RELEASES_URL: &str =
    "https://api.github.com/repos/elibroftw/music-caster/releases/latest";
const USER_AGENT: &str = "MusicCasterMusic Caster Bootstrapper";
const INNO_UNINSTALLER: &str = "unins000.exe";

/// Installer
#[derive(Clone, Debug)]
pub enum Progress {
    /// Querying the GitHub releases API for the latest MSI.
    Resolving,
    Downloading { downloaded: u64, total: Option<u64> },
    Installing { version: String },
    Done,
}

/// Uninstall
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub enum UninstallStatus {
    #[default]
    Checking,
    Exists,
    NotFound,
    Initiated,
    Removed,
}

impl UninstallStatus {
    /// Human-readable line for the UI.
    pub fn label(self) -> &'static str {
        match self {
            UninstallStatus::Checking => "Checking for a previous installation…",
            UninstallStatus::Exists => "Previous installation found.",
            UninstallStatus::NotFound => "No previous installation found.",
            UninstallStatus::Initiated => "Removing the previous version…",
            UninstallStatus::Removed => "Removed the previous version.",
        }
    }
}

#[derive(Clone, Debug)]
pub enum Event {
    Update(Progress),
    Uninstall(UninstallStatus),
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

pub fn host_arch_token() -> &'static str {
    match std::env::consts::ARCH {
        "aarch64" => "arm64",
        _ => "x64",
    }
}

// TODO: return a Struct { VERSION, MSI_DOWNLOAD_URL }
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

fn download(url: &str, dest: &Path, on_progress: &dyn Fn(Event)) -> Result<(), String> {
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
        on_progress(Event::Update(Progress::Downloading { downloaded, total }));
    }
    file.flush().map_err(|e| format!("Could not finalize the MSI: {e}"))?;
    Ok(())
}

fn find_uninstaller() -> Option<UninstallCommand> {
    let cwd_uninstaller = std::env::current_dir()
        .map(|d| d.join(INNO_UNINSTALLER))
        .ok()
        .filter(|p| p.exists())
        .map(UninstallCommand::from_path);

    cwd_uninstaller.or_else(registry_uninstaller)
}

fn run_uninstaller(
    uninstaller: Option<UninstallCommand>,
    on_event: &(dyn Fn(Event) + Sync),
) -> Result<(), String> {
    if cfg!(debug_assertions) {
        match &uninstaller {
            Some(cmd) => eprintln!("[dry-run] would uninstall: {}", cmd.program.display()),
            None => eprintln!("[dry-run] no previous installation found"),
        }
        // Hold so the existence status is comfortably visible in the window.
        std::thread::sleep(std::time::Duration::from_millis(1500));
        return Ok(());
    }

    match uninstaller {
        Some(UninstallCommand { program, args }) => {
            on_event(Event::Uninstall(UninstallStatus::Initiated));
            Command::new(program)
                .args(args)
                .args(["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"])
                .status()
                .map_err(|e| format!("Uninstaller failed to launch: {e}"))?;
            on_event(Event::Uninstall(UninstallStatus::Removed));
            Ok(())
        }
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

fn run_installer(msi_path: &Path) -> Result<(), String> {
    if cfg!(debug_assertions) {
        eprintln!("[debug] would run: msiexec /i {} /passive /norestart", msi_path.display());
        return Ok(());
    }
    Command::new("msiexec")
        .arg("/i")
        .arg(msi_path)
        .args(["/passive", "/norestart"])
        .spawn()
        .map_err(|e| format!("Installer failed to launch: {e}"))?;
    Ok(())
}

pub fn migrate(on_event: &(dyn Fn(Event) + Sync)) -> Result<(), String> {
    on_event(Event::Update(Progress::Resolving));

    let uninstaller = find_uninstaller();
    on_event(Event::Uninstall(if uninstaller.is_some() {
        UninstallStatus::Exists
    } else {
        UninstallStatus::NotFound
    }));

    let (version, msi_url) = latest_msi()?;
    let dest = std::env::temp_dir().join(format!("MusicCaster_{version}.msi"));

    let download_started = std::sync::Barrier::new(2);

    on_event(Event::Update(Progress::Downloading { downloaded: 0, total: None }));

    let (download_result, uninstall_result) = std::thread::scope(|scope| {
        let gate = &download_started;
        let uninstall = scope.spawn(move || {
            gate.wait(); // blocks until the download begins (signalled below)
            run_uninstaller(uninstaller, on_event)
        });

        download_started.wait(); // download is starting now → let the uninstaller run
        let download_result = download(&msi_url, &dest, on_event);
        let uninstall_result = uninstall
            .join()
            .unwrap_or_else(|_| Err("Uninstaller thread panicked".into()));
        (download_result, uninstall_result)
    });

    download_result?;
    uninstall_result?;

    on_event(Event::Update(Progress::Installing { version }));
    run_installer(&dest)?;

    on_event(Event::Update(Progress::Done));
    Ok(())
}

// ---------------------------------------------------------------------------
// Registry fallback for locating the uninstaller when it is not in the CWD.
// ---------------------------------------------------------------------------

use windows::Win32::Foundation::{ERROR_SUCCESS, MAX_PATH};
use windows::Win32::System::Registry::{
    HKEY, HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE, KEY_READ, KEY_WOW64_64KEY,
    RegCloseKey, RegEnumKeyExW, RegOpenKeyExW, RegQueryValueExW, REG_SAM_FLAGS, REG_VALUE_TYPE,
};
use windows::core::{PCWSTR, PWSTR};

const UNINSTALL_ROOT: &str =
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall";

fn registry_uninstaller() -> Option<UninstallCommand> {
    let hives = [HKEY_LOCAL_MACHINE, HKEY_CURRENT_USER];
    for hive in hives {
        if let Some(cmd) = search_uninstall_hive(hive, KEY_WOW64_64KEY) {
            return Some(cmd);
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
        let Some(subkey) = open_key(root, &subkey_name, KEY_READ | view) else {
            continue;
        };
        // TODO: use GUID {FBE8A652-58D6-482D-B6A9-B3D7931CC9C5}
        let display_name = read_string(subkey, "DisplayName").unwrap_or_default();
        if display_name.to_ascii_lowercase().contains("music caster") {
            let cmd = read_string(subkey, "QuietUninstallString")
                .or_else(|| read_string(subkey, "UninstallString"))
                .map(parse_uninstall_string);
            unsafe { let _ = RegCloseKey(subkey); }
            if cmd.is_some() {
                break cmd;
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
