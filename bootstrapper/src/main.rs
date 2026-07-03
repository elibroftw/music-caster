//! Music Caster migration bootstrapper.
//!
//! A standalone failsafe that upgrades an existing (v5, Inno-based) Music Caster install
//! to the Tauri v6+ MSI build. It deliberately **ignores all command-line flags**, shows
//! a small progress window, runs the old uninstaller, downloads the latest MSI from the
//! GitHub releases, launches it, and exits.
//!
//! The actual migration lives in [`migrate`] and has no GUI dependency. The window here is
//! built with `iced` using its software (tiny-skia) renderer, so the executable is fully
//! self-contained and runs on any Windows machine without a GPU/runtime requirement.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod migrate;

use iced::futures::{SinkExt, Stream, StreamExt};
use iced::widget::{column, container, progress_bar, text};
use iced::{Element, Length, Size, Subscription, Task};

use migrate::{Event, Progress, UninstallStatus};

/// Raw RGBA window icon decoded from `icon.ico` by `build.rs` (see `ICON_RGBA`/`ICON_SIZE`).
/// winit doesn't reuse the .exe's embedded resource for the live window, so we set it here.
mod window_icon {
    include!(concat!(env!("OUT_DIR"), "/window_icon.rs"));
}

fn main() -> iced::Result {
    iced::application("Music Caster Bootstrapper", App::update, App::view)
        .subscription(App::subscription)
        .window(iced::window::Settings {
            size: Size::new(460.0, 230.0),
            resizable: false,
            icon: window_icon(),
            ..Default::default()
        })
        .run()
}

/// Builds the live-window icon from the baked RGBA data, or `None` (system default) if the
/// build-time decode produced nothing.
fn window_icon() -> Option<iced::window::Icon> {
    if window_icon::ICON_SIZE == 0 {
        return None;
    }
    iced::window::icon::from_rgba(
        window_icon::ICON_RGBA.to_vec(),
        window_icon::ICON_SIZE,
        window_icon::ICON_SIZE,
    )
    .ok()
}

/// A human-readable snapshot of migration progress shown in the window.
#[derive(Debug, Clone)]
struct Status {
    headline: String,
    detail: String,
    /// Overall progress, 0.0..=1.0, used to drive the progress bar.
    fraction: f32,
}

impl Status {
    fn from_progress(p: &Progress) -> Self {
        match p {
            Progress::Resolving => {
                Self::new("Preparing update", "Checking for the latest version…", 0.05)
            }
            Progress::Downloading { downloaded, total } => match total {
                Some(total) if *total > 0 => {
                    let ratio = *downloaded as f32 / *total as f32;
                    Self::new(
                        "Downloading Music Caster",
                        &format!("Downloading… {:.0}%", ratio * 100.0),
                        // reserve the 0.10..0.85 band for the download
                        0.10 + 0.75 * ratio,
                    )
                }
                _ => Self::new(
                    "Downloading Music Caster",
                    &format!("Downloading… {:.1} MB", *downloaded as f32 / 1_048_576.0),
                    0.10,
                ),
            },
            Progress::Installing { version } => Self::new(
                &format!("Installing Music Caster {version}"),
                "The installer will finish on its own.",
                0.95,
            ),
            Progress::Done => Self::new(
                "Update started",
                "Music Caster is installing and will launch shortly.",
                1.0,
            ),
        }
    }

    fn new(headline: &str, detail: &str, fraction: f32) -> Self {
        Self { headline: headline.into(), detail: detail.into(), fraction }
    }
}

struct App {
    /// Status of the MSI track (resolve → download → install).
    installer: Status,
    /// Status of the uninstall track, retained so it stays visible through later phases
    /// and on the failure screen.
    uninstaller: UninstallStatus,
    /// Set once the migration ends (success or failure) so the worker subscription stops.
    finished: bool,
}

impl Default for App {
    fn default() -> Self {
        Self {
            installer: Status::new("Preparing update", "Starting…", 0.0),
            uninstaller: UninstallStatus::default(),
            finished: false,
        }
    }
}

#[derive(Debug, Clone)]
enum Message {
    Step(Event),
    Done,
    Failed(String),
}

impl App {
    fn update(&mut self, message: Message) -> Task<Message> {
        match message {
            Message::Step(event) => {
                // Route each event to its own track so the two statuses update independently.
                match event {
                    Event::Update(progress) => self.installer = Status::from_progress(&progress),
                    Event::Uninstall(status) => self.uninstaller = status,
                }
                Task::none()
            }
            Message::Done => {
                self.finished = true;
                // The MSI is already running; close the bootstrapper window.
                iced::exit()
            }
            Message::Failed(error) => {
                self.installer = Status::new("Update failed", &error, 0.0);
                // Leave the window open so the user can read the error; the retained
                // uninstall status stays visible below it.
                self.finished = true;
                Task::none()
            }
        }
    }

    fn view(&self) -> Element<'_, Message> {
        // Two independent status tracks shown at once: the MSI installer (with a progress
        // bar) and the uninstaller.
        let content = column![
            text(self.installer.headline.clone()).size(22),
            text(format!("Installer: {}", self.installer.detail)).size(14),
            progress_bar(0.0..=1.0, self.installer.fraction),
            text(format!("Uninstaller: {}", self.uninstaller.label())).size(14),
        ]
        .spacing(14);

        container(content)
            .padding(24)
            .width(Length::Fill)
            .height(Length::Fill)
            .center_x(Length::Fill)
            .center_y(Length::Fill)
            .into()
    }

    fn subscription(&self) -> Subscription<Message> {
        if self.finished {
            Subscription::none()
        } else {
            Subscription::run(migration_worker)
        }
    }
}

/// Runs the (blocking) migration on a dedicated OS thread and streams progress back into
/// iced as [`Message`]s. The thread bridges to iced's async runtime via an unbounded
/// channel, since `migrate::migrate` is synchronous (ureq + msiexec).
fn migration_worker() -> impl Stream<Item = Message> {
    iced::stream::channel(64, |mut output| async move {
        let (tx, mut rx) = iced::futures::channel::mpsc::unbounded::<Message>();

        std::thread::spawn(move || {
            let on_event = {
                let tx = tx.clone();
                move |event: Event| {
                    let _ = tx.unbounded_send(Message::Step(event));
                }
            };
            match migrate::migrate(&on_event) {
                Ok(()) => {
                    // Let the user read "Installing…" before the window closes; the MSI
                    // (already launched) continues independently.
                    std::thread::sleep(std::time::Duration::from_millis(2500));
                    let _ = tx.unbounded_send(Message::Done);
                }
                Err(error) => {
                    let _ = tx.unbounded_send(Message::Failed(error));
                }
            }
        });

        while let Some(message) = rx.next().await {
            let _ = output.send(message).await;
        }
    })
}
