"""
Linux (freedesktop) counterparts of the Win32 APIs Music Caster relies on.

Everything in here is safe to import on any platform: nothing is executed at
import time and every helper degrades to a no-op / sensible default when the
underlying tool (pactl, systemd, xrandr, ...) is unavailable. That matters
because Fedora defaults to Wayland + PipeWire, while other distros/sessions may
be X11 + PulseAudio.
"""

import os
import platform
import shutil
import subprocess
from contextlib import suppress
from functools import lru_cache
from pathlib import Path
from subprocess import DEVNULL, PIPE

IS_LINUX = platform.system() == 'Linux'

# ---------------------------------------------------------------------------
# process helpers
# ---------------------------------------------------------------------------


def run(cmd, timeout=5, check=False) -> str:
    """Run cmd (list) and return stripped stdout, or '' on any failure."""
    try:
        p = subprocess.run(cmd, stdout=PIPE, stderr=DEVNULL, stdin=DEVNULL,
                           text=True, timeout=timeout, check=check)
    except (OSError, subprocess.SubprocessError):
        return ''
    if p.returncode != 0:
        return ''
    return (p.stdout or '').strip()


def has_cmd(cmd) -> bool:
    return shutil.which(cmd) is not None


# ---------------------------------------------------------------------------
# XDG user directories (counterpart of SHGetKnownFolderPath)
# ---------------------------------------------------------------------------

_XDG_DEFAULTS = {
    'DOWNLOAD': 'Downloads',
    'MUSIC': 'Music',
    'DESKTOP': 'Desktop',
    'DOCUMENTS': 'Documents',
    'PICTURES': 'Pictures',
    'VIDEOS': 'Videos',
}


@lru_cache(maxsize=None)
def _user_dirs_file() -> dict:
    """Parse ~/.config/user-dirs.dirs (the file xdg-user-dir reads)."""
    config_home = Path(os.environ.get('XDG_CONFIG_HOME') or (Path.home() / '.config'))
    dirs = {}
    with suppress(OSError):
        with open(config_home / 'user-dirs.dirs', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or '=' not in line:
                    continue
                key, _, value = line.partition('=')
                key = key.strip().removeprefix('XDG_').removesuffix('_DIR')
                value = value.strip().strip('"').strip("'")
                # values look like "$HOME/Downloads"
                value = os.path.expandvars(value)
                if value:
                    dirs[key] = Path(value).expanduser()
    return dirs


@lru_cache(maxsize=None)
def get_xdg_user_dir(name: str) -> Path:
    """
    Return the XDG user directory for e.g. 'DOWNLOAD' or 'MUSIC'.

    Falls back to ~/<English name> when the directory is not configured, which
    matches what xdg-user-dir itself does.
    """
    name = name.upper()
    env = os.environ.get(f'XDG_{name}_DIR')
    if env:
        return Path(os.path.expandvars(env)).expanduser()
    from_file = _user_dirs_file().get(name)
    if from_file is not None:
        return from_file
    # last resort: ask xdg-user-dir directly (handles localized folder names)
    if has_cmd('xdg-user-dir'):
        out = run(['xdg-user-dir', name])
        if out:
            return Path(out).expanduser()
    return Path.home() / _XDG_DEFAULTS.get(name, name.title())


# ---------------------------------------------------------------------------
# sleep inhibition (counterpart of SetThreadExecutionState)
# ---------------------------------------------------------------------------


class SleepInhibitor:
    """
    Keeps the machine (and optionally the screen) awake while music plays.

    Windows does this with SetThreadExecutionState(ES_CONTINUOUS |
    ES_SYSTEM_REQUIRED). On Linux the equivalent is holding a systemd-logind
    inhibitor lock, which we take by keeping a `systemd-inhibit` child alive.
    """

    __slots__ = 'proc'

    def __init__(self):
        self.proc = None

    def inhibit(self, reason='Playing audio'):
        if not IS_LINUX or self.proc is not None or not has_cmd('systemd-inhibit'):
            return False
        cmd = [
            'systemd-inhibit',
            '--what=idle:sleep',
            '--who=Music Caster',
            f'--why={reason}',
            '--mode=block',
            # sleep forever; the lock is released when the process is killed
            'sh', '-c', 'while :; do sleep 3600; done',
        ]
        try:
            self.proc = subprocess.Popen(cmd, stdout=DEVNULL, stderr=DEVNULL, stdin=DEVNULL)
        except OSError:
            self.proc = None
            return False
        return True

    def release(self):
        proc, self.proc = self.proc, None
        if proc is None:
            return False
        with suppress(OSError):
            proc.terminate()
            with suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=2)
            if proc.poll() is None:
                proc.kill()
        return True


_sleep_inhibitor = SleepInhibitor()


def allow_sleep():
    """Counterpart of SetThreadExecutionState(ES_CONTINUOUS)."""
    return _sleep_inhibitor.release()


def prevent_sleep(reason='Playing audio'):
    """Counterpart of SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)."""
    return _sleep_inhibitor.inhibit(reason)


# ---------------------------------------------------------------------------
# power actions (counterpart of shutdown /p /f and rundll32 SetSuspendState)
# ---------------------------------------------------------------------------


def _power_action(systemctl_verb, loginctl_verb) -> bool:
    if has_cmd('systemctl') and subprocess.call(
        ['systemctl', systemctl_verb], stdout=DEVNULL, stderr=DEVNULL
    ) == 0:
        return True
    if has_cmd('loginctl') and subprocess.call(
        ['loginctl', loginctl_verb], stdout=DEVNULL, stderr=DEVNULL
    ) == 0:
        return True
    if has_cmd('dbus-send'):
        # logind D-Bus API works without polkit prompts on most desktops
        method = {'poweroff': 'PowerOff', 'suspend': 'Suspend', 'hibernate': 'Hibernate'}[systemctl_verb]
        return subprocess.call([
            'dbus-send', '--system', '--print-reply',
            '--dest=org.freedesktop.login1', '/org/freedesktop/login1',
            f'org.freedesktop.login1.Manager.{method}', 'boolean:true',
        ], stdout=DEVNULL, stderr=DEVNULL) == 0
    return False


def shut_down() -> bool:
    return _power_action('poweroff', 'poweroff')


def sleep_computer() -> bool:
    return _power_action('suspend', 'suspend')


def hibernate() -> bool:
    return _power_action('hibernate', 'hibernate')


# ---------------------------------------------------------------------------
# power supply (counterpart of GetSystemPowerStatus)
# ---------------------------------------------------------------------------


def is_plugged_in() -> bool:
    """
    True when running on AC power (or when there is no battery at all).
    Raises RuntimeError when the power supply state cannot be determined.
    """
    power_supply = Path('/sys/class/power_supply')
    try:
        supplies = sorted(power_supply.iterdir())
    except OSError as e:
        raise RuntimeError('could not get power status') from e
    has_battery = False
    for supply in supplies:
        with suppress(OSError):
            supply_type = (supply / 'type').read_text().strip()
            if supply_type == 'Mains':
                # 1 == plugged in
                return (supply / 'online').read_text().strip() == '1'
            if supply_type == 'Battery':
                has_battery = True
    if not has_battery:
        # a desktop without any power_supply/Mains entry is always "plugged in"
        return True
    raise RuntimeError('could not get power status')


# ---------------------------------------------------------------------------
# audio devices (counterpart of the MMDevices registry + WASAPI loopback)
# ---------------------------------------------------------------------------


def get_default_sink() -> str:
    """Name of the default PulseAudio/PipeWire sink, or '' when unavailable."""
    if not has_cmd('pactl'):
        return ''
    name = run(['pactl', 'get-default-sink'])
    if name and name != '@DEFAULT_SINK@':
        return name
    # older pactl has no get-default-sink; parse `pactl info`
    for line in run(['pactl', 'info']).splitlines():
        if line.startswith('Default Sink:'):
            return line.split(':', 1)[1].strip()
    return ''


def get_monitor_source(sink_name='') -> str:
    """
    The `.monitor` source that loops back whatever the given sink is playing.
    This is the Linux equivalent of opening a WASAPI loopback stream.
    """
    sink_name = sink_name or get_default_sink()
    if not sink_name:
        return ''
    monitor = f'{sink_name}.monitor'
    sources = run(['pactl', 'list', 'short', 'sources'])
    if sources:
        available = {line.split('\t')[1] for line in sources.splitlines() if '\t' in line}
        if monitor in available:
            return monitor
        # fall back to any monitor source
        for source in sorted(available):
            if source.endswith('.monitor'):
                return source
        return ''
    return monitor


# ---------------------------------------------------------------------------
# display (counterpart of EnumDisplaySettings / ChangeDisplaySettings)
# ---------------------------------------------------------------------------


def _xrandr_output():
    if is_wayland() or not has_cmd('xrandr'):
        # xrandr under XWayland reports a single virtual output it cannot change
        return ''
    return run(['xrandr'])


def get_current_res():
    """(width, height) of the primary display, or None when undeterminable."""
    out = _xrandr_output()
    for line in out.splitlines():
        if ' connected ' in line:
            # e.g. "eDP-1 connected primary 1920x1080+0+0 (normal ...) 344mm x 193mm"
            for token in line.split():
                geometry = token.split('+', 1)[0]
                if 'x' in geometry:
                    w, _, h = geometry.partition('x')
                    if w.isdigit() and h.isdigit():
                        return int(w), int(h)
    # fall back to tkinter, which works on Wayland too
    with suppress(Exception):
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        res = (root.winfo_screenwidth(), root.winfo_screenheight())
        root.destroy()
        return res
    return None


@lru_cache(maxsize=1)
def get_virtual_screen_size():
    """
    (width, height) spanning all monitors -- the Linux counterpart of
    GetSystemMetrics(SM_CXVIRTUALSCREEN / SM_CYVIRTUALSCREEN).

    Cached: this may spin up a throwaway Tk root, and the monitor layout does
    not change often enough to justify paying that on every window placement.
    """
    with suppress(Exception):
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        size = (root.winfo_vrootwidth(), root.winfo_vrootheight())
        root.destroy()
        if size[0] > 0 and size[1] > 0:
            return size
    return get_current_res()


def _parse_xrandr_modes():
    """Yield (width, height, refresh_rate) for every mode of the primary output."""
    out = _xrandr_output()
    in_output = False
    for line in out.splitlines():
        if ' connected ' in line or ' disconnected ' in line:
            # only read the modes of the first connected output
            if in_output:
                break
            in_output = ' connected ' in line
            continue
        if not in_output or not line.startswith((' ', '\t')):
            continue
        parts = line.split()
        if not parts or 'x' not in parts[0]:
            continue
        w, _, h = parts[0].partition('x')
        if not (w.isdigit() and h.isdigit()):
            continue
        for rate in parts[1:]:
            rate = rate.rstrip('*+')
            with suppress(ValueError):
                yield int(w), int(h), round(float(rate))


def get_all_resolutions():
    """[(width, height), ...] supported by the primary display."""
    seen = []
    for w, h, _ in _parse_xrandr_modes():
        if (w, h) not in seen:
            seen.append((w, h))
    return seen


def get_all_refresh_rates():
    return {rate for _, _, rate in _parse_xrandr_modes()}


def set_resolution(width: int, height: int, refresh_rate=None) -> bool:
    """Change the primary display mode. Not possible on Wayland."""
    out = _xrandr_output()
    if not out:
        return False
    output_name = ''
    for line in out.splitlines():
        if ' connected ' in line:
            output_name = line.split()[0]
            break
    if not output_name:
        return False
    cmd = ['xrandr', '--output', output_name, '--mode', f'{width}x{height}']
    if refresh_rate:
        cmd += ['--rate', str(refresh_rate)]
    return subprocess.call(cmd, stdout=DEVNULL, stderr=DEVNULL) == 0


def get_dpi_scale() -> float:
    """
    Best-effort fractional scaling factor (1.0 == 100%).

    GNOME/KDE expose this differently, so try the desktop settings first and
    fall back to the toolkit-wide GDK_SCALE/QT_SCALE_FACTOR env vars.
    """
    if has_cmd('gsettings'):
        # text-scaling-factor is the fractional part users actually change
        value = run(['gsettings', 'get', 'org.gnome.desktop.interface', 'text-scaling-factor'])
        with suppress(ValueError):
            scale = float(value)
            if scale > 0:
                return scale
    for env_var in ('GDK_SCALE', 'QT_SCALE_FACTOR'):
        with suppress(ValueError, TypeError):
            scale = float(os.environ.get(env_var, ''))
            if scale > 0:
                return scale
    return 1.0


# ---------------------------------------------------------------------------
# file manager (counterpart of `explorer /select,`)
# ---------------------------------------------------------------------------


def show_in_file_manager(path) -> bool:
    """Open the file manager with `path` selected, like explorer /select."""
    path = Path(path).absolute()
    uri = path.as_uri()
    if has_cmd('dbus-send'):
        # the freedesktop FileManager1 interface is implemented by nautilus,
        # dolphin, nemo, thunar, ... and selects the item rather than opening it
        if subprocess.call([
            'dbus-send', '--session', '--print-reply',
            '--dest=org.freedesktop.FileManager1', '/org/freedesktop/FileManager1',
            'org.freedesktop.FileManager1.ShowItems',
            f'array:string:{uri}', 'string:',
        ], stdout=DEVNULL, stderr=DEVNULL) == 0:
            return True
    for file_manager, select_arg in (('nautilus', '--select'), ('nemo', ''),
                                     ('dolphin', '--select'), ('thunar', '')):
        if has_cmd(file_manager):
            cmd = [file_manager]
            if select_arg:
                cmd.append(select_arg)
            cmd.append(str(path))
            with suppress(OSError):
                subprocess.Popen(cmd, stdout=DEVNULL, stderr=DEVNULL)
                return True
    if has_cmd('xdg-open'):
        with suppress(OSError):
            subprocess.Popen(['xdg-open', str(path.parent)], stdout=DEVNULL, stderr=DEVNULL)
            return True
    return False


# ---------------------------------------------------------------------------
# misc
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def find_font(bold=True):
    """
    Locate a TrueType/OpenType font usable by Pillow.

    Fedora ships DejaVu and Liberation by default; the explicit paths avoid a
    slow fontconfig query, and `fc-match` covers everything else.
    """
    candidates = [
        '/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf' if bold
        else '/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf',
        '/usr/share/fonts/liberation-sans-fonts/LiberationSans-Bold.ttf' if bold
        else '/usr/share/fonts/liberation-sans-fonts/LiberationSans-Regular.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold
        else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf' if bold
        else '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/usr/share/fonts/gnu-free/FreeSansBold.otf' if bold
        else '/usr/share/fonts/gnu-free/FreeSans.otf',
        '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf' if bold
        else '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    if has_cmd('fc-match'):
        path = run(['fc-match', '-f', '%{file}', 'sans-serif:bold' if bold else 'sans-serif'])
        if path and os.path.isfile(path):
            return path
    return None
