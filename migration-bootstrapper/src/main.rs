//! Music Caster migration bootstrapper.
//!
//! A standalone failsafe that upgrades an existing (v5, Inno-based) Music Caster install
//! to the Tauri v6+ MSI build. It deliberately **ignores all command-line flags**, shows
//! a small progress window, runs the old uninstaller, downloads the latest MSI from the
//! GitHub releases, launches it, and exits.
//!
//! The actual migration lives in [`migrate`] and has no GUI dependency, so it keeps
//! working even though the `windows-reactor` UI below targets a preliminary, unreleased
//! API (windows-rs PR #4479) that may still change. If the UI fails to compile against
//! the pinned git revision, only this file needs adjusting against that PR's examples.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod migrate;

use std::thread;

use migrate::Progress;
use windows_reactor::*;

fn main() -> Result<()> {
    App::new().title("Music Caster Updater").render(app)
}

/// Human-readable snapshot of the migration, shared between the worker thread and the UI.
#[derive(Clone, PartialEq)]
struct Status {
    headline: String,
    detail: String,
    /// Whether the migration has finished (success or failure); the window may close.
    finished: bool,
}

impl Status {
    fn from_progress(p: &Progress) -> Self {
        match p {
            Progress::Resolving => Self::new("Preparing update", "Checking for the latest version…"),
            Progress::Downloading { downloaded, total } => {
                let detail = match total {
                    Some(total) if *total > 0 => {
                        let pct = (*downloaded as f64 / *total as f64 * 100.0).round();
                        format!("Downloading… {pct:.0}%")
                    }
                    _ => format!("Downloading… {:.1} MB", *downloaded as f64 / 1_048_576.0),
                };
                Self::new("Downloading Music Caster", &detail)
            }
            Progress::Uninstalling => {
                Self::new("Uninstalling previous version", "Please wait…")
            }
            Progress::Installing { version } => Self {
                headline: format!("Installing Music Caster {version}"),
                detail: "The installer will finish on its own.".into(),
                finished: false,
            },
            Progress::Done => Self {
                headline: "Update started".into(),
                detail: "Music Caster is installing and will launch shortly.".into(),
                finished: true,
            },
            Progress::Error(msg) => Self {
                headline: "Update failed".into(),
                detail: msg.clone(),
                finished: true,
            },
        }
    }

    fn new(headline: &str, detail: &str) -> Self {
        Self { headline: headline.into(), detail: detail.into(), finished: false }
    }
}

fn app(cx: &mut RenderCx) -> Element {
    // The worker thread publishes into this shared snapshot; the UI reflects it.
    // use_async_state gives a setter whose `.call` is safe from any thread (the write is
    // marshalled back onto the UI thread), which is exactly what the migration worker needs.
    let (status, set_status) = cx.use_async_state(Status::new("Preparing update", "Starting…"));

    // Start the migration exactly once, on mount.
    cx.use_effect((), move || {
        let set_status = set_status.clone();
        thread::spawn(move || {
            let on_event = {
                let set_status = set_status.clone();
                move |p: Progress| set_status.call(Status::from_progress(&p))
            };
            match migrate::migrate(&on_event) {
                Ok(()) => {
                    // Give the user a beat to read "installing…", then exit so the MSI
                    // (already launched) owns the rest of the upgrade.
                    thread::sleep(std::time::Duration::from_millis(2500));
                    std::process::exit(0);
                }
                Err(e) => set_status.call(Status::from_progress(&Progress::Error(e))),
            }
        });
    });

    vstack((
        text_block(status.headline.clone()).font_size(20.0).bold(),
        text_block(status.detail.clone()).font_size(14.0),
    ))
    .into()
}
