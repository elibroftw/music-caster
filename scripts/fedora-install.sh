#!/usr/bin/env bash
PYTHON=$1

echo "Installing Fedora system dependencies"
sudo dnf install -y "$PYTHON" python-pip "$PYTHON-devel" "$PYTHON-virtualenv" "$PYTHON-tkinter" portaudio-devel redhat-rpm-config

# Runtime dependencies of the Linux code paths (see src/modules/linux.py):
#   pulseaudio-utils           pactl: default sink + monitor source for "System Audio"
#   xdg-utils                  xdg-open/xdg-mime/xdg-user-dir: file assoc + folder opening
#   desktop-file-utils         update-desktop-database: register the .desktop handler
#   python3-gobject +
#     libayatana-appindicator-gtk3   pystray appindicator backend (tray icon)
#   dejavu-sans-fonts          album art text rendering + Tk UI font
#   fontconfig                 fc-match font lookup fallback
echo "Installing Music Caster runtime dependencies"
sudo dnf install -y pulseaudio-utils xdg-utils desktop-file-utils python3-gobject \
  libayatana-appindicator-gtk3 dejavu-sans-fonts fontconfig

# Optional: only used to switch resolution/refresh rate on X11 sessions.
# Wayland compositors do not allow this, so a failure here is not fatal.
sudo dnf install -y xrandr || echo "xrandr unavailable: resolution switching will be disabled"

# GNOME hides tray icons unless the AppIndicator extension is installed
if [ "$XDG_CURRENT_DESKTOP" = "GNOME" ]; then
  echo "GNOME detected: install the 'AppIndicator and KStatusNotifierItem Support'"
  echo "extension (gnome-shell-extension-appindicator) for the tray icon to appear."
fi
