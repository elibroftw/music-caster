# Music Caster Migration Bootstrapper

`MigrationBootstrapper.exe` is a small, standalone failsafe that upgrades an existing
(v5, Inno-Setup-based) Music Caster install to the **Tauri v6+ MSI** build.

## What it does

1. **Ignores all command-line flags** — it always performs the same migration.
2. Shows a small progress window (downloading / uninstalling / installing).
3. Resolves the latest release's **architecture-matched MSI** from the GitHub releases API
   (`x64` / `arm64`). If no MSI matches the host architecture it reports an error and stops.
4. Downloads the MSI to the temp directory.
5. Runs the existing uninstaller, found via the **current working directory**
   (`unins000.exe`) first, falling back to the Windows **registry** uninstall string
   (`…\CurrentVersion\Uninstall`, both hives + WOW6432Node) — see `src/migrate.rs`.
6. Launches the MSI with `msiexec /i <msi> /passive /norestart` and exits, leaving the
   installer to finish on its own.

Because every input is derived from the CWD + the GitHub API, the bootstrapper also works
when **downloaded and run standalone**; the uninstall step is simply skipped when no
existing install is found.

## Layout

- `src/migrate.rs` — UI-independent migration core (resolve → download → uninstall →
  install). This is intentionally decoupled from the GUI so the migration keeps working
  regardless of UI-library changes.
- `src/main.rs` — the [`windows-reactor`](https://github.com/microsoft/windows-rs/pull/4479)
  (WinUI 3, windows-rs) progress UI that drives `migrate::migrate`.

> **Note:** `windows-reactor` is currently an unreleased git dependency with a preliminary
> API. If the UI fails to build against the pinned revision, adjust `main.rs` against that
> PR's examples — `migrate.rs` is unaffected.

## Build

```sh
cargo build --release
# -> target/release/MigrationBootstrapper.exe
```

## Follow-ups (not yet wired)

- Compile this crate in `build.py` and publish `MigrationBootstrapper.exe` as a release
  asset in [`.github/workflows/tauri_build.yml`](../.github/workflows/tauri_build.yml).
- Once published, have the Python updater (`auto_update` in `src/music_caster.py`)
  download and run this bootstrapper for the v6 migration instead of performing the
  download/uninstall/`msiexec` sequence inline.
