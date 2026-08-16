from lzma import PRESET_DEFAULT

from meta import (
    State,
    SUN_VALLEY_TCL,
    PID_FILENAME,
    LOCK_FILENAME,
    VERSION,
    UNINSTALLER,
    DEFAULT_THEME,
    EMAIL,
    WAIT_TIMEOUT,
    UPDATE_MESSAGE,
    IMPORTANT_INFORMATION,
    AUDIO_FILE_TYPES,
    USING_TAURI_FRONTEND,
    BUNDLE_IDENTIFIER
)
import time

from modules.db import FileMetadata
from utils import install_deno

start_time = time.monotonic()
from contextlib import suppress
from itertools import islice, chain
import io
import multiprocessing as mp
import os
import platform
import threading
from subprocess import Popen, PIPE, DEVNULL # noqa
import re
import sys
from shutil import copy2
from shared import is_already_running


def create_pid_file(port=None):
    pid_filename = Path(appdirs.user_data_dir(roaming=True)) / BUNDLE_IDENTIFIER / PID_FILENAME
    pid_filename.parent.mkdir(parents=True, exist_ok=True)
    if not USING_TAURI_FRONTEND:
        pid_filename = PID_FILENAME
    with open(pid_filename, 'w', encoding='utf-8') as f:
        f.write(str(os.getpid()))
        if port is not None:
            f.write(f'\n{port}')


def parse_pid_file():
    pid_filename = Path(appdirs.user_data_dir(roaming=True)) / BUNDLE_IDENTIFIER / PID_FILENAME
    pid_filename.parent.mkdir(parents=True, exist_ok=True)
    if not USING_TAURI_FRONTEND:
        pid_filename = PID_FILENAME
    with suppress(FileNotFoundError):
        with open(pid_filename, encoding='utf-8') as f:
            pid = int(f.readline().strip())
            try:
                port = int(f.readline().strip())
            except ValueError:
                port = 2001
            return pid, port
    return None, 2001


def ensure_single_instance(debugging=False):
    file = open(LOCK_FILENAME, 'w+', encoding='utf-8')
    if USING_TAURI_FRONTEND:
        return file
    # no old running instances found, try locking file
    try:
        # exclusively locked
        portalocker.lock(file, portalocker.LockFlags.EXCLUSIVE | portalocker.LockFlags.NON_BLOCKING)
        create_pid_file()
        if debugging:
            print(f'Locked {LOCK_FILENAME} pid = {os.getpid()}')
    except LockException as e:
        # another instance is probably running
        # wait a bit for pid to be written to file
        time.sleep(0.1)
        pid, port = parse_pid_file()
        look_for = 'Music Caster' if IS_FROZEN else Path(sys.executable).name
        # double check if it's already running
        # if more than one instance, there's definitely >3 processes
        threshold = 3 if pid is None else 0
        if is_already_running(threshold=threshold, look_for=look_for, pid=pid):
            if debugging:
                print('not exiting because we are DEBUGGING')
            else:
                try:
                    activate_instance(port=port, default_timeout=5)
                except Exception as activation_e:
                    app_log.exception('Failed to activate existing instance')
                    handle_exception(activation_e, restart_program=False)
                sys.exit()
        else:
            app_log.exception('Instance was not found. Is the lock broken?')
            handle_exception(e, restart_program=False)
    return file


if __name__ == '__main__':
    mp.freeze_support()
    import argparse
    from inspect import currentframe
    from pathlib import Path
    from urllib.request import pathname2url, urlopen, Request
    from urllib.error import URLError

    import appdirs
    import portalocker
    from portalocker.exceptions import LockException
    import ujson as json

    from sys_tray import system_tray

    parser = argparse.ArgumentParser(description='Music Caster')
    parser.add_argument('--debug', '-d', default=False, action='store_true', help='allows more than one music caster instance and no telemetry')
    parser.add_argument('--start-playing', default=False, action='store_true', help='resume or shuffle play all')
    parser.add_argument('--queue', '-q', default=False, action='store_true', help='uris are queued rather than immediately played')
    parser.add_argument('--playnext', '-n', default=False, action='store_true', help='paths are added to "next up"')
    parser.add_argument('--urlprotocol', default=False, action='store_true', help='launched using uri protocol')
    parser.add_argument('--update', '-u', default=False, action='store_true', help='allow music caster to update when other CLI args are provided')
    parser.add_argument('--nupdate', default=False, action='store_true', help='start without auto-update')
    parser.add_argument('--exit', '-x', default=False, action='store_true',
                        help='exits any existing instance (including self)')
    parser.add_argument('--minimized', '-m', default=False, action='store_true', help='start minimized to tray')
    parser.add_argument('--version', '-v', default=False, action='store_true', help='returns the version')
    parser.add_argument('uris', nargs='*', default=[], help='list of files/dirs/playlists/urls/"System Audio" to play/queue')
    parser.add_argument('--position', default=0, help='position to start at if resume_playing')
    parser.add_argument('--shell', default=False, action='store_true', help='if from shell/explorer')
    parser.add_argument('--device', action='store', help='select device to use (cast UUID or "local")', default=None)
    parser.add_argument('--db-path', action='store', help='path to sqlite database file', default=None)
    parser.add_argument('--settings-path', action='store', help='path to settings.json file', default=None)
    # freeze_support() adds the following
    parser.add_argument('--multiprocessing-fork', default=False, action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    # if from url protocol, re-parse arguments
    if args.urlprotocol:
        new_args = args.uris[0].replace('music-caster://', '', 1).replace('music-caster:', '').replace('music-caster', '')
        if new_args:
            new_args = new_args.split(';')
        args = parser.parse_args(new_args)
    if args.version:
        print(VERSION)
        sys.exit()
    DEBUG = args.debug
    print(f'DEBUG: {DEBUG}')
    IS_FROZEN = getattr(sys, 'frozen', False)
    working_dir = Path(sys.argv[0]).absolute().parent
    os.chdir(working_dir)
    OLD_SETTINGS_FILE = Path('settings.json').absolute()
    DEFAULT_SETTINGS_FILE = Path(appdirs.user_data_dir(roaming=True)) / BUNDLE_IDENTIFIER / 'settings.json'
    SETTINGS_FILE = OLD_SETTINGS_FILE
    if IS_FROZEN:
        SETTINGS_FILE = Path(args.settings_path).absolute() if args.settings_path and USING_TAURI_FRONTEND else DEFAULT_SETTINGS_FILE
        if OLD_SETTINGS_FILE.exists() and not SETTINGS_FILE.exists():
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            # renaming doesn't work across disks
            copy2(OLD_SETTINGS_FILE, SETTINGS_FILE)
            os.remove(OLD_SETTINGS_FILE)


    PHANTOMJS_DIR = Path('phantomjs')
    # c:\Users\maste\AppData\Local\Programs\Music Caster\settings.json

    def json_dumps(d):
        return json.dumps(d).encode('utf-8')

    def activate_instance(port=2001, default_timeout=0.5, to_port=2004):
        # by default activates if running already
        response, local_ipv6, local_ipv4 = '', 'http://[::1]:', 'http://127.0.0.1:'
        try:
            with open(SETTINGS_FILE, encoding='utf-8') as json_file:
                api_key = json.load(json_file).get('api_key', '')
        except (FileNotFoundError, ValueError):
            api_key = ''
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        data = {'api_key': api_key}
        while port < to_port and response == '':
            for localhost in (local_ipv4, local_ipv6):
                timeout = default_timeout
                with suppress(URLError):
                    if args.exit:  # --exit argument
                        req = Request(f'{localhost}{port}/exit/', data=json_dumps(data))
                    elif args.uris:  # MC was supplied at least one path to a folder/file
                        uri_data = json_dumps({**data, 'uris': args.uris, 'queue': args.queue, 'play_next': args.playnext, 'device': args.device})
                        req = Request(f'{localhost}{port}/play/', data=uri_data, headers=headers)
                        timeout += 0.5
                    else:  # neither --exit nor paths was supplied
                        req = Request(f'{localhost}{port}/action/activate', data=json_dumps(data))
                    response = urlopen(req, timeout=timeout).read()
                if response:
                    return True
            port += 1
        return False

    lock_file = ensure_single_instance(debugging=DEBUG)
    daemon_commands, tray_process_queue = mp.Queue(), mp.Queue()
    if args.exit:
        sys.exit()
    import asyncio
    from base64 import b64encode, b64decode
    import concurrent.futures
    from collections import deque
    from collections.abc import Iterable
    import ctypes
    import encodings.idna  # noqa # DO NOT REMOVE
    from functools import cmp_to_key
    import glob
    import hashlib
    from copy import deepcopy
    from datetime import datetime, timedelta
    import errno
    from functools import lru_cache
    import logging
    from logging.handlers import RotatingFileHandler
    from math import log10, floor
    import pprint
    from random import shuffle
    from shutil import copyfileobj, rmtree
    from queue import Queue
    import secrets
    import socket
    from threading import Thread
    import traceback
    import urllib.parse
    from urllib.parse import urlsplit
    from uuid import UUID
    import zipfile

    from b64_images import PAUSE_BUTTON_IMG, PLAY_BUTTON_IMG, SHUFFLE_OFF, SHUFFLE_ON, VOLUME_IMG, VOLUME_MUTED_IMG, WINDOW_ICON, DEFAULT_ART
    from audio_player import AudioPlayer
    from modules import linux
    from modules.win32_media_controls import SystemMediaTransportControlsButton # SystemMediaControls
    from mutagen._util import MutagenError
    from modules.playing_status import PlayingStatus
    from modules.url_metadata import ydl_get_metadata, URLMetadata
    from utils import (
        get_first_artist,
        t,
        SystemAudioRecorder,
        startfile,
        custom_art,
        get_album_art,
        get_lan_ip,
        get_metadata,
        Unknown,
        get_file_name,
        parse_m3u,
        valid_audio_file,
        valid_color_code,
        get_mac,
        Device,
        natural_key_file,
        better_shuffle,
        truncate_title,
        resize_img,
        repeat_img_tooltip,
        DiscordPresence,
        get_ipv4,
        ydl_extract_info,
        parse_qs,
        urlparse,
        get_yt_id,
        get_yt_urls,
        install_phantomjs,
        add_to_path,
        open_in_browser,
        get_video_timestamps,
        get_deezer_tracks,
        get_ipv6,
        cmd_exists,
        get_latest_release,
        rm_old_startup_shortcuts,
        start_on_login_win32,
        create_progress_bar_texts,
        set_metadata,
        get_spotify_headers,
        get_cut_text,
        export_playlist,
        fix_path,
        drop_target_register,
        dnd_bind,
        InvalidAudioFile,
        get_audio_length,
        get_spotify_tracks,
    )
    from modules.resolution_switcher import fmt_res, get_all_resolutions, set_resolution, get_all_refresh_rates, get_initial_res, get_current_res, is_plugged_in, get_initial_dpi_scale
    get_initial_dpi_scale()
    from modules.db import DatabaseConnection, init_db
    if IS_FROZEN:
        DatabaseConnection.move_to_new_location(args.db_path)
    # 0.5 seconds gone to 3rd party imports
    from flask import Flask, jsonify, render_template, request, redirect, send_file, Response, make_response
    import waitress
    from jinja2.exceptions import TemplateNotFound
    from werkzeug.exceptions import InternalServerError, BadRequest, UnsupportedMediaType
    from PIL import Image
    import pychromecast
    from pychromecast.controllers.media import MediaStatusListener
    from pychromecast.controllers.receiver import CastStatusListener
    from pychromecast.error import PyChromecastError, UnsupportedNamespace, NotConnected, RequestTimeout, RequestFailed
    from pychromecast.config import APP_MEDIA_RECEIVER
    from pychromecast import Chromecast
    from pychromecast.models import CastInfo
    import pyperclip
    import requests
    from tempfile import NamedTemporaryFile
    try:
        import fcntl
    except ImportError:
        pass
    import scrapetube
    import zeroconf
    TIME_TO_IMPORT = time.monotonic() - start_time
    try:
        sun_valley_tcl_path = f'{sys._MEIPASS}/{SUN_VALLEY_TCL}'
    except AttributeError:
        sun_valley_tcl_path = SUN_VALLEY_TCL
    sun_valley_tcl_path = os.path.abspath(sun_valley_tcl_path)
    # LOGS
    log_format = logging.Formatter('%(asctime)s %(levelname)s (%(lineno)d) %(funcName)s(): %(message)s')
    # max 1 MB log file
    installed_log_file_path = Path(appdirs.user_data_dir()) / BUNDLE_IDENTIFIER / 'logs' /'daemon.log'
    installed_log_file_path.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE = installed_log_file_path if IS_FROZEN else 'music_caster.log'
    if IS_FROZEN and os.path.exists('music_caster.log') and not os.path.exists(LOG_FILE):
        # renaming doesn't work across disks
        copy2('music_caster.log', LOG_FILE)
        os.remove('music_caster.log')
    log_handler = RotatingFileHandler(LOG_FILE, maxBytes=1000000, backupCount=1, encoding='UTF-8')
    log_handler.setFormatter(log_format)
    app_log = logging.getLogger('music_caster')
    app_log.propagate = False  # disable console output
    app_log.setLevel(logging.INFO)
    app_log.addHandler(log_handler)
    # LOGGING
    logging.getLogger('pychromecast.socket_client').addHandler(log_handler)
    logging.getLogger('pychromecast').addHandler(log_handler)
    logging.getLogger('pychromecast').setLevel(logging.INFO)
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    logging.getLogger('werkzeug').addHandler(log_handler)
    app_log.debug(f'Time to import is {TIME_TO_IMPORT:.2f} seconds')

    WELCOME_MSG = t('Thanks for installing Music Caster.') + '\n' + t('Music Caster is running in the tray.')
    uris_to_scan = Queue()
    PRESSED_KEYS = set()
    settings_file_lock = threading.Lock()
    last_play_command = settings_last_modified = 0
    update_last_checked = time.time()  # check every hour
    cast: Chromecast = None  # type: ignore
    all_tracks, all_tracks_sorted = {}, []
    url_metadata: dict(URLMetadata) = {}
    tray_playlists = [t('Playlists Tab')]
    CHECK_MARK = 'âœ“'
    music_folders, device_names = [], [(f'{CHECK_MARK} ' + t('Local device'), 'device:0')]
    music_queue, done_queue, next_queue = deque(), deque(), deque()
    # usage: background_thread sleep(1) if seek_queue, seek_queue.pop(), seek_queue.clear(), call set_pos
    seek_queue = []
    playing_url = deezer_opened = attribute_error_reported = False
    recent_api_plays = {'play': 0, 'queue': 0, 'play_next': 0}
    # seconds but using time()
    playing_status = PlayingStatus()
    track_position = timer = track_end = track_length = track_start = 0

    def get_downloads_folder():
        if platform.system() == 'Windows':
            from knownpaths import sh_get_known_folder_path, FOLDERID
            try:
                possible_path = sh_get_known_folder_path(FOLDERID.Downloads)
                if possible_path is not None:
                    return Path(possible_path)
            except Exception as e:
                handle_exception(e)
        elif platform.system() == 'Linux':
            # XDG counterpart of SHGetKnownFolderPath: the folder is user
            # configurable and localized, so ~/Downloads is only a fallback
            try:
                return linux.get_xdg_user_dir('DOWNLOAD')
            except Exception as e:
                handle_exception(e)
        return Path.home() / 'Downloads'


    def get_installer_path(extension='exe'):
        filename = f'music_caster_installer.{extension}'
        downloads_dir = get_downloads_folder()
        if downloads_dir.exists():
            return str(downloads_dir / filename)
        return filename


    def get_default_music_folder():
        if platform.system() == 'Windows':
            from knownpaths import sh_get_known_folder_path, FOLDERID
            try:
                return sh_get_known_folder_path(FOLDERID.Music)
            except Exception as e:
                handle_exception(e)
        elif platform.system() == 'Linux':
            try:
                return str(linux.get_xdg_user_dir('MUSIC'))
            except Exception as e:
                handle_exception(e)
        return str(Path.home() / 'Music')

    print('Installer path:', get_installer_path())
    default_auto_update = os.path.exists(UNINSTALLER) or os.path.exists('Updater.exe')
    settings: dict = {  # default settings
        'device': None, 'window_locations': {}, 'smart_queue': False, 'skips': {}, 'theme': DEFAULT_THEME.copy(),
        'auto_update': default_auto_update, 'run_on_startup': os.path.exists(UNINSTALLER), 'notifications': True,
        'shuffle': False, 'repeat': None, 'discord_rpc': False, 'save_window_positions': True, 'mini_on_top': True,
        'populate_queue_startup': False, 'persistent_queue': False, 'volume': 20, 'muted': False, 'volume_delta': 5,
        'scrubbing_delta': 5, 'flip_main_window': False, 'show_track_number': False, 'folder_cover_override': True,
        'show_album_art': True, 'folder_context_menu': True, 'vertical_gui': False, 'mini_mode': False,
        'gui_exits_app': False, 'update_check_hours': 1, 'timer_shut_down': False, 'timer_hibernate': False,
        'timer_sleep': False, 'show_queue_index': True, 'queue_library': False, 'lang': '', 'sys_audio_delay': 0,
        'use_last_folder': False, 'upload_pw': '', 'last_folder': get_default_music_folder(), 'scan_folders': True,
        'track_format': '&artist - &title', 'reversed_play_next': False, 'update_message': '', 'important_message': '',
        'music_folders': [get_default_music_folder()], 'playlists': {}, 'queues': {'done': [], 'music': [], 'next': []},
        'position': 0, 'plugged_in_res': None, 'on_battery_res': None, 'experimental_features': False,
        'api_key': secrets.token_urlsafe(16), 'concert_location': 'New York'}
    default_settings = deepcopy(settings)
    indexing_tracks_thread = save_queue_thread = Thread()
    sar = SystemAudioRecorder()
    app = Flask(__name__)

    app.jinja_env.lstrip_blocks = app.jinja_env.trim_blocks = True
    os.environ['WERKZEUG_RUN_MAIN'] = 'true'
    os.environ['FLASK_SKIP_DOTENV'] = '1'
    # if time.time() > SYNC_WITH_CHROMECAST good to sync from chromecast
    SYNC_WITH_CHROMECAST = 0
    CAST_LOCK = threading.Lock()
    OLD_CAST_VOLUME = 0
    OLD_CAST_POS = 0
    LAST_PLAYED = time.time()
    init_db()

    def get_line_number():
        cf = currentframe()
        return cf.f_back.f_lineno


    # ES_CONTINUOUS keeps the state until it is changed again,
    # ES_SYSTEM_REQUIRED stops the machine from going to sleep on its own
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


    def prevent_sleep():
        """ Stop the system from sleeping while audio is playing """
        if platform.system() == 'Windows':
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        elif platform.system() == 'Linux':
            # a systemd-logind inhibitor lock is the SetThreadExecutionState equivalent
            linux.prevent_sleep('Music Caster is playing audio')


    def allow_sleep():
        """ Undo prevent_sleep(): let the system sleep again """
        if platform.system() == 'Windows':
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        elif platform.system() == 'Linux':
            linux.allow_sleep()


    def tray_notify(message, title='Music Caster', context=''):
        """ A wrapper for tray_process_queue.put({ notify: {message: msg, title: title} }) """
        if message == 'update_available':
            message = t('Update $VER is available').replace('$VER', f'v{context}')
        if not USING_TAURI_FRONTEND:
            tray_process_queue.put({'notify': {'message': message, 'title': title}})


    def close_tray():
        if not USING_TAURI_FRONTEND:
            tray_process_queue.put({'close': None})
            tray_process.join()


    def save_settings():
        global settings_last_modified
        # avoid corrupting settings file if the system crashes mid-write by using temporary file + sync + atomic rename
        with settings_file_lock:
            try:
                tmp_file = NamedTemporaryFile(mode='w', encoding='utf-8', prefix=SETTINGS_FILE.name, dir=SETTINGS_FILE.parent, suffix='.tmp', delete=False)
                json.dump(settings, tmp_file, indent=2, escape_forward_slashes=False)
                # send to kernel buffer
                tmp_file.flush()
                # inform OS to write to disk to avoid a situation where the file is replaced but not written to
                if platform.system() == 'Darwin':
                    fcntl.fcntl(tmp_file.fileno(), fcntl.F_FULLFSYNC)
                else:
                    os.fsync(tmp_file.fileno())
                tmp_file.close()
                # this atomic operation ensures that a settings.file will exist if the system crashes before/after the system call
                os.replace(tmp_file.name, SETTINGS_FILE)
                settings_last_modified = os.path.getmtime(SETTINGS_FILE)
            except Exception as e:
                handle_exception(e)
                tray_notify(t('ERROR') + f': {e}')
            except OSError as e:
                if e.errno == errno.ENOSPC:
                    tray_notify(t('ERROR') + ': ' + t('No space left on device to save settings'))
                else:
                    tray_notify(t('ERROR') + f': {e}')


    def is_debug():
        return settings.get('DEBUG', DEBUG)


    def refresh_tray(refresh_devices=False):
        if USING_TAURI_FRONTEND:
            return
        if refresh_devices:
            device_names.clear()
            # account for case where user is connected to device not detectable
            if cast is not None and cast.uuid not in cast_browser.devices:
                cast_browser.devices[cast.uuid] = cast.cast_info
            for device in get_devices():
                device_names.append(device.as_tray_item(settings['device']))
        tray_folders = [t('Select Folder')]
        for i, folder in enumerate(music_folders):
            folder = Path(folder)
            folder = ('../' + '/'.join(folder.parts[-2:])) if len(folder.parts) > 2 else folder.as_posix()
            tray_folders.append((folder, f'PF:{i}'))
        repeat_menu = [t('Repeat All') + f' {CHECK_MARK}' * (settings['repeat'] is False),
                       t('Repeat One') + f' {CHECK_MARK}' * (settings['repeat'] is True),
                       t('Repeat Off') + f' {CHECK_MARK}' * (settings['repeat'] is None)]
        tray_menu_default = [t('Settings'), t('Rescan Library'), t('Refresh Devices'),
                             [t('Select Device'), *device_names], [t('Timer'), t('Set Timer'), t('Cancel Timer')],
                             [t('Play'), t('System Audio'),
                              [t('URL'), t('Play URL'), t('Queue URL'), t('Play URL Next')],
                              [t('Folders'), *tray_folders], [t('Playlists'), *tray_playlists],
                              [t('Select Files'), t('Play Files'), t('Queue Files'), t('Play Files Next')],
                              t('Play All')], (t('Exit'), '__EXIT__')]
        tray_menu_playing = [t('Settings'), t('Rescan Library'), t('Refresh Devices'),
                             [t('Select Device'), *device_names], [t('Timer'), t('Set Timer'), t('Cancel Timer')],
                             [t('Controls'), t('locate track', 1), [t('Repeat Options'), *repeat_menu], t('Stop'),
                              t('previous track', 1), t('next track', 1), t('Pause')],
                             [t('Play'), t('System Audio'),
                              [t('URL'), t('Play URL'), t('Queue URL'), t('Play URL Next')],
                              [t('Folders'), *tray_folders], [t('Playlists'), *tray_playlists],
                              [t('Select Files'), t('Play Files'), t('Queue Files'), t('Play Files Next')],
                              t('Play All')], (t('Exit'), '__EXIT__')]
        tray_menu_paused = [t('Settings'), t('Rescan Library'), t('Refresh Devices'),
                            [t('Select Device'), *device_names], [t('Timer'), t('Set Timer'), t('Cancel Timer')],
                            [t('Controls'), t('locate track', 1), [t('Repeat Options'), *repeat_menu], t('Stop'),
                             t('previous track', 1), t('next track', 1), t('Resume')],
                            [t('Play'), t('System Audio'),
                             [t('URL'), t('Play URL'), t('Queue URL'), t('Play URL Next')],
                             [t('Folders'), *tray_folders],
                             [t('Playlists'), *tray_playlists],
                             [t('Select Files'), t('Play Files'), t('Queue Files'), t('Play Files Next')],
                             t('Play All')], (t('Exit'), '__EXIT__')]
        # refresh playlists
        tray_playlists.clear()
        tray_playlists.append(t('Playlists Tab'))
        tray_playlists.extend([(pl.replace('&', '&&&'), f'PL:{pl}') for pl in settings['playlists']])
        # tell tray process to update
        # icon = FILLED_ICON if playing_status.playing() else UNFILLED_ICON
        icon = {'filled': None} if playing_status.playing() else {'unfilled': None}
        if playing_status.busy():
            menu = tray_menu_playing if playing_status.playing() else tray_menu_paused
            metadata = get_current_metadata()
            title, artists = metadata['title'], metadata['artist']
            _tooltip = f'{get_first_artist(artists)} - {title}'
        else:
            menu, _tooltip = tray_menu_default, 'Music Caster'
        if is_debug():
            _tooltip += ' [DEBUG]'
        tray_process_queue.put({'menu': menu, 'tooltip': _tooltip, **icon})


    def refresh_tray_icon():
        if USING_TAURI_FRONTEND:
            return
        icon = {'filled': None} if playing_status.playing() else {'unfilled': None}
        tray_process_queue.put(icon)


    def update_settings(settings_key, new_value):
        """ returns new value and can be called from non-main thread """
        if settings[settings_key] != new_value:
            settings[settings_key] = new_value
            save_settings()
            if settings_key == 'shuffle':
                shuffle_queue() if new_value else un_shuffle_queue()
        return new_value


    def save_queues():
        global save_queue_thread

        def _save_queue():
            settings['queues']['done'] = tuple(done_queue)
            settings['queues']['music'] = tuple(music_queue)
            settings['queues']['next'] = tuple(next_queue)
            save_settings()

        if settings['persistent_queue'] and not save_queue_thread.is_alive() and not State.installing_update:
            save_queue_thread = Thread(target=_save_queue, name='SaveQueue')
            save_queue_thread.start()


    def update_volume(new_vol, _from=''):
        """
        new_vol: float[0, 100]
        AKA set_volume
        """
        app_log.info(f'set to {new_vol} from {_from}')
        if not isinstance(new_vol, (float, int)):
            new_vol = update_settings('volume', 20)
        new_vol = new_vol / 100
        with suppress(NameError):
            audio_player.set_volume(new_vol)
        if cast is not None:
            # this was threaded because otherwise it would block for over 0.2 seconds
            # exceptions: NotConnected, RequestTimeout, RequestFailed
            set_volume_Thread = Thread(target=cast.set_volume, args=(new_vol,), name='CastSetVolume', daemon=True)
            set_volume_Thread.start()


    def cycle_repeat():
        """ :return: new repeat value """
        # Repeat Off (None) becomes All (False) becomes One (True) becomes Off
        new_repeat_setting = {None: False, True: None, False: True}[settings['repeat']]
        return update_settings('repeat', new_repeat_setting)


    def create_support_email_url():
        try:
            with open(LOG_FILE, encoding='utf-8') as f:
                log_lines = f.read().splitlines()[-10:]  # get last 10 lines of the log
        except FileNotFoundError:
            log_lines = []
        log_lines = '%0D%0A'.join(log_lines)
        email_body = f'body=%0D%0A%23%20Tail%20of%20Log%0D%0A%0D%0A{log_lines}'
        mail_to = f'mailto:{EMAIL}?subject=Regarding%20Music%20Caster%20v{VERSION}&{email_body}'
        return mail_to


    def handle_exception(e: Exception, restart_program=False) -> bool:
        current_time = str(datetime.now())
        trace_back_msg = traceback.format_exc().replace('\\', '/')
        exc_type, exc_tb = sys.exc_info()[0], sys.exc_info()[2]
        playing_uri = 'N/A'
        if music_queue:
            if playing_url:
                playing_uri = music_queue[0]
            elif sar.alive:
                playing_uri = 'system audio'
            elif playing_status.busy():
                playing_uri = music_queue[0]
        try:
            with open(LOG_FILE, encoding='utf-8') as f:
                log_lines = f.read().splitlines(keepends=False)[-10:]  # get last 10 lines of the log
        except FileNotFoundError:
            log_lines = []
        device = 'local' if cast is None else 'cast'
        payload = {'VERSION': VERSION, 'FATAL': restart_program, 'EXCEPTION TYPE': exc_type.__name__,
                   'LINE': exc_tb.tb_lineno, 'TRACEBACK': trace_back_msg, 'LOG': log_lines,
                   'MQ[0]': playing_uri, 'PLAYING_STATUS': str(playing_status), 'DEVICE': device,
                   'CWD': os.getcwd(), 'PORTABLE': not os.path.exists(UNINSTALLER),
                   'MAC': hashlib.md5(get_mac().encode()).hexdigest(), 'OS': platform.platform(), 'TIME': current_time}
        if IS_FROZEN:
            with suppress(requests.RequestException):
                requests.post('https://lenerva.com/telemetry/music-caster/error/', json=payload, timeout=1)
        try:
            with open('error.log', 'r', encoding='utf-8') as _f:
                content = _f.read()
        except (FileNotFoundError, ValueError):
            content = ''
        with open('error.log', 'w', encoding='utf-8') as _f:
            _f.write(pprint.pformat(payload))
            _f.write('\n')
            _f.write(content)
        if restart_program:
            close_tray()
            with suppress(Exception):
                stop('error handling')
            tray_notify(t('An error occurred, restarting now'))
            # minimized = main_window.was_closed()
            if IS_FROZEN:
                startfile('Music Caster')
            else:
                raise e  # raise exception if running in script rather than executable
            sys.exit()
        return False

    def get_current_art() -> bytes:
        if sar.alive:
            return custom_art('SYS')
        if playing_status.busy() and music_queue:
            uri = music_queue[0]
            if uri.startswith('http'):
                with DatabaseConnection() as conn:
                    maybe_url_metadata = URLMetadata.from_db(conn, uri)
                if isinstance(maybe_url_metadata, URLMetadata):
                    return maybe_url_metadata.get_cover_image()
                if isinstance(url_metadata.get(uri), URLMetadata):
                    return url_metadata[uri].get_cover_image()
                if url_metadata.get(uri, {}).get('art') in ('None', None):
                    return custom_art('URL')
                if 'art_data' in url_metadata[uri]:
                    return url_metadata[uri]['art_data']
                # use 'art_data' else download 'art' link and cache to 'art_data'
                url_metadata[uri]['art_data'] = b64encode(requests.get(url_metadata[uri]['art']).content)
                return url_metadata[uri]['art_data']
            return get_album_art(uri, settings['folder_cover_override'])[1]
        return DEFAULT_ART


    def get_metadata_wrapped(file_path: str) -> dict:  # keys: title, artist, album, sort_key
        try:
            if file_path.startswith('http'):
                raise ValueError('expected file not http...')
            m = get_metadata(file_path)
            return m
        except (MutagenError, ValueError):
            try:
                return all_tracks[Path(file_path).as_posix()]
            except KeyError:
                # i forget the reason why we have the time_modified so high
                return {'title': Unknown('Title'), 'artist': Unknown('Artist'), 'explicit': False, 'time_modified': os.path.getmtime(file_path),
                        'album': Unknown('Title'), 'sort_key': get_file_name(file_path), 'track_number': '1'}


    def get_uri_metadata(uri, read_file=True):
        """ Uses cache to get metadata """
        # raises KeyError
        uri = uri.replace('\\', '/')
        if uri.startswith('http'):
            with DatabaseConnection() as conn:
                maybe_url_metadata = URLMetadata.from_db(conn, uri)
                if maybe_url_metadata is not None:
                    return maybe_url_metadata
            if uri in url_metadata:
                return url_metadata[uri]
            return {'title': Unknown('Title'), 'artist': Unknown('Artist'), 'explicit': False,
                    'album': Unknown('Album'), 'sort_key': uri, 'track_number': '1'}
        if uri in all_tracks:
            try:
                ignore_cache = os.path.getmtime(uri) != all_tracks[uri]['time_modified'] if read_file else False
            except FileNotFoundError:
                ignore_cache = False
            if not ignore_cache:
                return all_tracks[uri]
        # uri is probably a file that has not been cached yet
        if read_file:
            metadata = get_metadata_wrapped(uri)
            all_tracks[uri] = metadata
            return metadata
        raise KeyError


    def get_current_metadata() -> dict | URLMetadata:
        if sar.alive:
            return url_metadata['SYSTEM_AUDIO']
        if music_queue and playing_status.busy():
            return get_uri_metadata(music_queue[0])
        return {'artist': '', 'title': t('Nothing Playing'), 'album': ''}


    def get_audio_uris(uris: Iterable, scan_uris=True, ignore_m3u=False, parsed_m3us=None, ignore_dir=False):
        """
        :param uris: A list of URIs (urls, folders, m3u files, files)
        :param scan_uris: whether to add to uris_to_scan
        :param ignore_m3u: whether to ignore .m3u(8) files
        :param parsed_m3us: m3u files that have already been parsed. This is to avoid recursive parsing
        :param ignore_dir: whether to scan uri if it is a dir
        :return: generator of valid audio files
        """
        if parsed_m3us is None:
            parsed_m3us = set()
        if isinstance(uris, str):
            uris = (uris,)
        for uri in uris:
            if isinstance(uri, Iterable) and not isinstance(uri, str):
                yield from get_audio_uris(uri, scan_uris, ignore_m3u, parsed_m3us, ignore_dir)
            elif uri in settings['playlists']:
                yield from get_audio_uris(settings['playlists'][uri], scan_uris=scan_uris, ignore_m3u=ignore_m3u,
                                          parsed_m3us=parsed_m3us)
            elif os.path.isdir(uri) and not ignore_dir:
                # if scanning a folder,
                #  ignore playlist files and folders that are named as files as they aren't audio files
                yield from get_audio_uris(glob.iglob(f'{glob.escape(uri)}/**/*.*', recursive=True), ignore_dir=True,
                                          scan_uris=scan_uris, ignore_m3u=True, parsed_m3us=parsed_m3us)
            elif os.path.isfile(uri):
                uri = Path(uri).absolute().as_posix()
                if not ignore_m3u and (uri.endswith('.m3u') or uri.endswith('.m3u8')) and uri not in parsed_m3us:
                    parsed_m3us.add(uri)
                    yield from get_audio_uris(parse_m3u(uri), parsed_m3us=parsed_m3us)
                elif valid_audio_file(uri):
                    if scan_uris and uri not in all_tracks:
                        uris_to_scan.put(uri)
                    yield uri
            elif uri.startswith('http'):
                if scan_uris and uri not in url_metadata:
                    uris_to_scan.put(uri)
                yield uri


    def index_all_tracks(update_global=True, ignore_files: set | None = None) -> dict:
        """
        returns the music library dict if update_global is False
        starts scanning and building the music library/database if update_global is True
        ignore_files is a list (converted to set) of files to not include in the return value / scan
            usually used with update_global=False (think about it)
        """
        global indexing_tracks_thread, all_tracks
        # make sure ignore_files is a set
        if ignore_files is None:
            ignore_files = set()

        def _index_library():
            """
            Scans folders provided in settings and adds them to a dictionary
            Does not ignore the files that in ignore_files by design
            """
            global all_tracks, all_tracks_sorted
            use_temp = len(all_tracks)  # use temp if all_tracks is not empty
            all_tracks_temp = {}
            dict_to_use = all_tracks_temp if use_temp else all_tracks
            # scan items in queue and library
            file_metadata_list = []
            urls_to_fetch = []
            FileMetadata.cleanup_db_table()
            with DatabaseConnection() as conn:
                cur = conn.cursor()
                for uri in get_audio_uris((settings['queues'].values(), music_folders), scan_uris=False, ignore_m3u=True):
                    if uri.startswith('http'):
                        if not URLMetadata.from_db(conn, uri):
                            urls_to_fetch.append(uri)
                    elif os.path.isfile(uri):
                        m = get_metadata_wrapped(uri)
                        dict_to_use[uri] = m
                        m.update({'file_path': uri})
                        file_metadata_list.append(m)
                FileMetadata.batch_save_to_db(file_metadata_list, cur)

                for url in urls_to_fetch:
                    url_metadata_list = get_url_metadata(url)
                    batch_to_save = []
                    for m in url_metadata_list:
                        batch_to_save.append((url, m))
                        if isinstance(m, URLMetadata):
                            m.save_to_db(cur)
                conn.commit()
            if use_temp:
                all_tracks = all_tracks_temp
            # TODO
            # tracks = cur.execute('SELECT * FROM file_metadata ORDER BY sort_key').fetchall()
            all_tracks_sorted = sorted(all_tracks.items(), key=lambda item: item[1]['sort_key'])
            # scan items in playlists
            for _ in get_audio_uris(settings['playlists'].values(), ignore_m3u=True):
                # the function scans for us
                pass

        if not update_global:
            temp_tracks = all_tracks.copy()
            for ignore_file in ignore_files:
                temp_tracks.pop(ignore_file, None)
            return temp_tracks
        if indexing_tracks_thread is None:
            indexing_tracks_thread = Thread(target=_index_library, daemon=True, name='IndexLibrary')
            indexing_tracks_thread.start()
        elif not indexing_tracks_thread.is_alive():  # force reindex
            indexing_tracks_thread = Thread(target=_index_library, daemon=True, name='IndexLibrary')
            indexing_tracks_thread.start()


    def download(url, outfile):
        # throws ConnectionAbortedError
        r = requests.get(url, stream=True)
        if outfile.endswith('.zip'):
            outfile = outfile.replace('.zip', '')
            z = zipfile.ZipFile(io.BytesIO(r.content))
            z.extractall(outfile)
        else:
            with open(outfile, 'wb') as _f:
                copyfileobj(r.raw, _f)


    def load_settings(first_load=False):  # up to 0.4 seconds
        """
        load (and fix if needed) the settings file
        calls refresh_tray(), index_all_tracks(), save_setting()
        first_load: if true, start indexing all tracks
        """
        global settings, music_folders, settings_last_modified
        _save_settings = False
        with settings_file_lock:
            try:
                attempt = 0
                while True:
                    try:
                        with open(SETTINGS_FILE, encoding='utf-8') as json_file:
                            loaded_settings = json.load(json_file)
                            break
                    except PermissionError:
                        attempt += 1
                        if attempt == 10:
                            raise
            except (FileNotFoundError, ValueError):
                # if file does not exist
                _save_settings = True
                loaded_settings = {}
            for setting_name, setting_value in tuple(loaded_settings.items()):
                loaded_settings[setting_name.replace(' ', '_')] = loaded_settings.pop(setting_name)
            for setting_name, setting_value in settings.items():
                does_not_exist = setting_name not in loaded_settings  # setting DNE
                # use default settings if key/value does not exist
                if does_not_exist and setting_name in default_settings:
                    loaded_settings[setting_name] = setting_value
                    _save_settings = True
                elif setting_name in {'theme', 'queues'}:
                    # for theme key
                    for k, v in setting_value.items():
                        if k not in loaded_settings[setting_name]:
                            loaded_settings[setting_name][k] = v
                            _save_settings = True
            settings = loaded_settings
            # sort playlists by name
            settings['playlists'] = {k: settings['playlists'][k] for k in sorted(settings['playlists'].keys())}
            # if music folders were modified, re-index library
            if music_folders != settings['music_folders'] or first_load:
                music_folders = settings['music_folders']
                if settings['scan_folders']:
                    index_all_tracks()
            refresh_tray()
            theme = settings['theme']
            for k, v in theme.copy().items():
                # validate settings file color codes
                if not valid_color_code(v):
                    _save_settings = True
                    theme[k] = DEFAULT_THEME[k]

            # validate radio settings
            temp = (settings['timer_shut_down'], settings['timer_hibernate'], settings['timer_sleep'])
            if temp.count(True) > 1:  # Only one of the below can be True
                if settings['timer_shut_down']:
                    settings['timer_hibernate'] = False
                settings['timer_sleep'] = False
                _save_settings = True
            if settings['persistent_queue'] and settings['populate_queue_startup']:  # mutually exclusive
                settings['populate_queue_startup'] = False
                _save_settings = True

            # backwards compatible 'previous_device' -> 'device'
            if 'previous_device' in settings:
                settings['device'] = settings.pop('previous_device')
            State.lang = settings['lang']
            State.track_format = settings['track_format']
        if _save_settings:
            save_settings()
        settings_last_modified = os.path.getmtime(SETTINGS_FILE)


    @app.errorhandler(404)
    def page_not_found(_):
        return redirect('/')


    @app.post('/upload/')
    def upload_files():  # web GUI
        if 'files' not in request.files or not request.values.get('password'):
            return redirect('/#more')
        if request.values['password'] == settings['upload_pw']:
            # only save if upload_pw is set
            uploaded_files = request.files.getlist('files')
            for file in uploaded_files:
                if file.filename is not None:
                    file.save(Path.home() / 'Downloads' / file.filename)
        return redirect('/#more')


    def get_request_data():
        try:
            return request.json
        except (BadRequest, UnsupportedMediaType):
            return request.values

    @app.route('/action/<command>', methods=['GET', 'POST'])
    def web_action(command):
        global track_position, SYNC_WITH_CHROMECAST
        request_data = get_request_data()
        # if request_data.get('api_key') != settings['api_key']:
        #     return {'error': 'Unauthorized, api_key=not-provided'}, 401
        match command:
            case 'play':
                if resume('web'):
                    api_msg = 'resumed playback'
                else:
                    if music_queue:
                        play()
                        api_msg = 'started playing first track in queue'
                    else:
                        play_all()
                        api_msg = 'shuffled all and started playing'
            case 'pause':
                pause()  # resume == play
                api_msg = 'pause called'
            case 'next':
                ignore_timestamps = False
                times_to_skip = 1
                if request_data is not None:
                    ignore_timestamps = 'ignore_timestamps' in request_data
                    times_to_skip = int(request_data.get('times', 1))
                next_track(times=times_to_skip, forced=True, ignore_timestamps=ignore_timestamps)
                api_msg = 'next track called'
            case 'prev':
                times_to_skip = 1
                if request_data is not None:
                    times_to_skip = int(request_data.get('times', 1))
                prev_track(times=times_to_skip, forced=True)
                api_msg = 'prev track called'
            case 'repeat':
                cycle_repeat()
                api_msg = 'cycled repeat to ' + {None: 'off', True: 'one', False: 'all'}[settings['repeat']]
            case 'shuffle':
                shuffle_enabled = update_settings('shuffle', not settings['shuffle'])
                api_msg = f'shuffle set to {shuffle_enabled}'
            case 'seek':
                if playing_status.stopped() or not track_length:
                    api_msg = 'seek ignored: nothing playing'
                elif request_data is None or 'position' not in request_data:
                    api_msg = 'seek failed: position required'
                else:
                    track_position = min(max(float(request_data['position']), 0), track_length)
                    # do not debounce when playing locally
                    if cast is None:
                        set_pos(track_position)
                    else:
                        # debounce setting the track position
                        # background_thread will call set_pos
                        seek_queue.append(track_position)
                        SYNC_WITH_CHROMECAST = time.time() + 1
                    api_msg = f'set position to {track_position:.1f}'
            case 'stop':
                stop('web')
                api_msg = 'stopped playback'
            case 'activate':
                daemon_commands.put('__ACTIVATED__')  # tell main thread to show GUI
                api_msg = 'activated main window'
            case _:
                return f'unknown command: {command}'
        return {'message': api_msg} if ('is_api' in request.args or request.method == 'POST') else redirect('/')


    @app.route('/', methods=['GET', 'POST'])
    def web_index():  # web GUI
        request_data = get_request_data()
        if request_data is not None:
            for command in ('play', 'pause', 'next', 'prev', 'repeat', 'shuffle', 'stop', 'activate'):
                if command in request_data:
                    return web_action(command)
        api_key = settings['api_key']
        # if request_data.get('api_key') != api_key:
        #     return jsonify({'error': 'Unauthorized, api_key=not-provided'}), 401
        metadata = get_current_metadata()
        art = get_current_art()
        if isinstance(art, bytes):
            art = art.decode()
        art = f'data:image/png;base64,{art}'
        repeat_option = settings['repeat']
        repeat_enabled = 'repeat-enabled' if settings['repeat'] is not None else ''
        shuffle_enabled = 'shuffle-enabled' if settings['shuffle'] else ''
        # sort by the formatted title
        if all_tracks_sorted:
            sorted_tracks = all_tracks_sorted
        else:
            sorted_tracks = sorted(
                all_tracks.items(), key=lambda item: item[1]['sort_key']
            )
        list_of_tracks = [{'text': format_uri(filename),
                           'filename': pathname2url(filename).strip('/')} for filename, _ in sorted_tracks]
        _queue = create_track_list()
        device_index = 0
        for i, devices in enumerate(device_names):
            if devices[0].startswith(CHECK_MARK):
                device_index = i
                break
        formatted_devices = [('Local device', '0')]
        stream_url, stream_time = None, track_position
        if playing_status.playing() and music_queue:
            metadata = get_current_metadata()
            uri = music_queue[0]
            if os.path.exists(uri):
                file_path = pathname2url(uri).strip('/')
                stream_url = f"/file?path={file_path}&api_key={api_key}"
            else:
                stream_url = metadata.get('audio_url', metadata.get('url'))
        for cast_info in sorted(cast_browser.devices.values(), key=cast_info_sorter):
            formatted_devices.append((cast_info.friendly_name, str(cast_info.uuid)))
        try:
            return render_template('index.html', device_name=platform.node(), shuffle=shuffle_enabled, version=VERSION,
                                   repeat_enabled=repeat_enabled, playing_status=playing_status, metadata=metadata,
                                   settings=settings, list_of_tracks=list_of_tracks, repeat_option=repeat_option, gt=t,
                                   queue=_queue, playing_index=len(done_queue), device_index=device_index, art=art,
                                   devices=formatted_devices, stream_url=stream_url, stream_time=stream_time)
        except TemplateNotFound:
            return redirect('https://github.com/elibroftw/music-caster/releases/latest')


    @app.route('/album-art/')
    def api_get_album_art():
        img_data = get_current_art()
        return send_file(io.BytesIO(b64decode(img_data)), download_name='album_art.png',
                        mimetype='image/png', as_attachment=False, max_age=0)

    @app.route('/status/')
    @app.route('/state/')
    def api_state():
        _metadata = get_current_metadata()
        now_playing = {'status': str(playing_status), 'volume': settings['volume'], 'lang': settings['lang'],
                       'title': str(_metadata['title']), 'artist': str(_metadata['artist']),
                       'album': str(_metadata['album']),
                       'track_position': get_track_position(), 'track_length': track_end - track_start,
                       'queue_length': len(done_queue) + len(music_queue) + len(next_queue),
                       'shuffle': settings['shuffle'],
                       'repeat': {None: 'off', True: 'one', False: 'all'}.get(settings['repeat'], 'off')}
        if USING_TAURI_FRONTEND:
            now_playing["queue"] = get_queue_for_frontend()
            now_playing["file_name"] = music_queue[0] if music_queue else ''
            now_playing["queue_position"] = len(done_queue)
        return jsonify(now_playing)


    # Returns UI strings; The data cannot be processed further
    def get_queue_for_frontend() -> list:
        try:
            tracks = []
            for items in (done_queue, islice(music_queue, 0, 1), next_queue, islice(music_queue, 1, None)):
                for uri in items:
                    formatted_track = format_uri(uri, _for='queue')
                    length = None
                    # uncached tracks have no known length; the frontend just omits it
                    with suppress(KeyError):
                        length = get_uri_metadata(uri, read_file=False).get('length')
                    tracks.append((uri, formatted_track, length))
            return tracks
        except RuntimeError:
            return get_queue_for_frontend()


    @app.route('/play/', methods=['GET', 'POST'])
    def api_play():
        global last_play_command
        merge_plays = time.monotonic() - last_play_command < 0.5
        last_play_command = time.monotonic()

        request_data = get_request_data()
        if request_data is not None:
            queue_only = request_data.get('queue', False)
            if isinstance(queue_only, str):
                queue_only = queue_only.casefold() == 'true'
            play_next = request_data.get('play_next', False)
            if isinstance(play_next, str):
                play_next = play_next.casefold() == 'true'
            device_id = request_data.get('device', None)
            if device_id is not None:
                change_device(device_id)
            # reset recent_api_plays
            if not merge_plays:
                for opt in ('play', 'queue', 'play_next'):
                    recent_api_plays[opt] = 0
            if queue_only:
                opt = 'queue'
            elif play_next:
                opt = 'play_next'
            else:
                opt = 'play'
            merge_plays = recent_api_plays[opt]
            recent_api_plays[opt] += 1
            if 'uris' in request_data:
                uris = request_data['uris'] if isinstance(request_data, dict) else request_data.getlist('uris')
                if uris and uris[0].lower().replace(' ', '').replace('_', '') == 'systemaudio':
                    play_system_audio()
                else:
                    app_log.info(f'called play_uris with opt = {opt} uris len = {len(uris)}')
                    play_uris(uris, queue_uris=queue_only,
                            play_next=play_next, merge_tracks=merge_plays)
                    if not queue_only and not play_next and settings['queue_library'] and merge_plays == 0:
                        queue_all()
            elif 'uri' in request_data:
                if request_data['uri'].lower().replace(' ', '').replace('_', '') == 'systemaudio':
                    play_system_audio()
                else:
                    app_log.info(f"called play_uris with opt = {opt} uri = {request_data['uri']}, merge_tracks = {merge_plays}, queue all? {settings['queue_library']}")
                    play_uris([request_data['uri']], queue_uris=queue_only, play_next=play_next, merge_tracks=merge_plays)
                    if settings['queue_library']:
                        queue_all()
        else:
            recent_api_plays['play'] += 1
            app_log.info('increasing recent_api_plays play counter')
        return redirect('/') if request.method == 'GET' else api_state()


    @app.errorhandler(InternalServerError)
    def handle_500(_e):
        original = getattr(_e, 'original_exception', None)

        if original is None:
            # direct 500 error, such as abort(500)
            handle_exception(_e)
            return t('An Internal Server Error occurred') + f': {_e}'

        # wrapped unhandled error
        handle_exception(original)
        return t('An Internal Server Error occurred') + f': {original}'


    @app.route('/debug/')
    def api_get_debug_info():
        threads = [(thread.name, thread.is_alive()) for thread in threading.enumerate()]
        if is_debug():
            return jsonify({'pressed_keys': list(PRESSED_KEYS),
                            'last_traceback': sys.exc_info(),
                            'threads': threads,
                            'mac': get_mac()})
        return t('set DEBUG = true in `settings.json` to enable this page')


    @app.route('/running/', methods=['GET', 'POST', 'OPTIONS'])
    def api_running():
        response = make_response('true')
        http_origins = ('https://elijahlopez.herokuapp.com', 'http://elijahlopez.herokuapp.com',
                        'https://elijahlopez.ca', 'http://elijahlopez.ca')
        if request.environ.get('HTTP_ORIGIN') in http_origins:
            response.headers.add('Access-Control-Allow-Origin', request.environ['HTTP_ORIGIN'])
        return response


    @app.get('/web-url/')
    def api_get_web_url():
        """
        the URL other devices on the LAN can use to reach the web GUI.
        used by the frontend to render a scannable QR code
        """
        try:
            ipv4 = get_ipv4()
        except Exception:
            ipv4 = '127.0.0.1'
        if ipv4.startswith('127.'):
            # loopback is useless to another device, so report it as unavailable
            return jsonify({'error': 'could not determine a LAN address'}), 503
        return jsonify({'url': f"http://{ipv4}:{State.PORT}/?api_key={settings['api_key']}",
                        'ip': ipv4, 'port': State.PORT})


    @app.route('/exit/', methods=['GET', 'POST'])
    def api_exit():
        daemon_commands.put('__EXIT__')
        return api_state()


    @app.route('/change-setting/', methods=['POST'])
    def api_change_setting():
        with suppress(KeyError, TypeError):
            json_data = request.get_json(force=True, silent=True)
            if json_data is None:
                return 'false'
            setting_key = json_data['setting_name']
            if setting_key in settings or setting_key == 'timer_stop':
                val = json_data['value']
                update_settings(setting_key, val)
                timer_settings = {'timer_hibernate', 'timer_sleep',
                                  'timer_shut_down', 'timer_stop'}
                if val and setting_key in timer_settings:
                    for timer_setting in timer_settings.difference({setting_key, 'timer_stop'}):
                        update_settings(timer_setting, False)
                if setting_key == 'volume':
                    update_volume(0 if settings['muted'] else val, 'api')
                apply_queue_setting_side_effects(setting_key)
            return 'true'
        return 'false'


    @app.route('/refresh-devices/')
    def api_refresh_devices():
        refresh_tray(True)
        return 'true'


    @app.route('/rescan-library/')
    def api_rescan_library():
        index_all_tracks()
        return 'true'


    @app.get('/devices/')
    def api_get_devices():
        request_data = get_request_data()
        if request_data is None or ('friendly' not in request_data):
            devices: dict | list = {'0': 'Local device'}
            for _uuid, cast_info in cast_browser.devices.items():
                devices[str(_uuid)] = cast_info.friendly_name
        else:
            devices: dict | list = ['Local device::0']
            for cast_info in sorted(cast_browser.devices.values(), key=cast_info_sorter):
                devices.append(f'{cast_info.friendly_name}::{cast_info.uuid}')
        return jsonify(devices)


    @app.post('/change-device/<_uuid>')
    def api_change_device(_uuid):
        return str(change_device(_uuid))


    def cancel_timer():
        global timer
        timer = 0
        if settings['notifications']:
            tray_notify(t('Timer cancelled'))

    def set_timer(val):
        # TIMER PARSER
        global timer
        if val == 'cancel':
            cancel_timer()
            return 'timer cancelled'
        elif val.isdigit():
            seconds = abs(float(val)) * 60
        elif val.count(':') == 1:
            # parse out any PM and AM's
            timer_value = val.strip().upper().replace(' ', '').replace('PM', '').replace('AM', '')
            to_stop = datetime.strptime(timer_value + time.strftime(',%Y,%m,%d,%p'), '%H:%M,%Y,%m,%d,%p')
            current_time = datetime.now()
            current_time = current_time.replace(second=0)
            seconds_delta = (to_stop - current_time).total_seconds()
            seconds_delta = seconds_delta % 43200  # add 12 hours
            seconds = seconds_delta
        else:
            raise ValueError('Timer input is invalid')
        timer = time.time() + seconds
        timer_set_to = datetime.now().replace(second=0) + timedelta(seconds=seconds)
        if platform.system() == 'Windows':
            timer_set_to = timer_set_to.strftime('%#I:%M %p')
        else:
            timer_set_to = timer_set_to.strftime('%-I:%M %p')  # Linux
        return timer_set_to


    @app.route('/timer/', methods=['GET', 'POST'])
    def api_set_timer():
        global timer
        if request.method == 'POST':
            val = request.data.decode()
            try:
                return set_timer(val.casefold())
            except ValueError as e:
                return str(e)
        else:  # GET request
            return str(timer)

    @lru_cache(maxsize=12)
    def get_cover_jpg_data(file_path) -> io.BytesIO:
        new_img_data = io.BytesIO()
        mime, img_data = get_album_art(file_path, settings['folder_cover_override'])
        img_data = io.BytesIO(b64decode(img_data))
        if mime.lower().endswith('jpeg'):
            return img_data
        Image.open(img_data).convert('RGB').save(new_img_data, format='JPEG')
        return new_img_data

    @lru_cache()
    def report_album_art_buffer_error(file_path: str):
        msg_1 = f'{Path(file_path).name} has img_data with size 0; returning DEFUALT_ART instead'
        app_log.info(msg_1)
        _raw_album_art_mime, _raw_album_art_data = get_album_art(file_path, settings['folder_cover_override'])
        msg_2 = f'{Path(file_path).name} has album art with mime {_raw_album_art_mime} and data of size {len(_raw_album_art_data)}'
        app_log.info(msg_2)
        handle_exception(ValueError('\n'.join((msg_1, msg_2))))

    @app.route('/file/')
    def api_get_file():
        if 'path' in request.args:
            file_path = request.args['path']
            if os.path.isfile(file_path) and valid_audio_file(file_path) or file_path == 'DEFAULT_ART':
                if request.args.get('thumbnail_only', False) or file_path == 'DEFAULT_ART':
                    jpeg_buffer = get_cover_jpg_data(file_path)
                    jpeg_buffer.seek(0)
                    if (len(jpeg_buffer.getvalue()) == 0):
                        report_album_art_buffer_error(file_path)
                        return send_file(io.BytesIO(DEFAULT_ART), download_name='cover.jpeg',
                                        mimetype='image/jpeg', as_attachment=True, max_age=360000, conditional=True)
                    return send_file(jpeg_buffer, download_name='cover.jpeg',
                                     mimetype='image/jpeg', as_attachment=True, max_age=360000, conditional=True)
                return send_file(file_path, conditional=True, as_attachment=True, max_age=360000)
        return '400'

    @app.route('/dz/')
    def api_get_dz():
        from Cryptodome.Cipher import Blowfish
        if 'url' in request.args:
            # TODO: cache content to prevent extra requests
            url = request.args['url']
            metadata = url_metadata[url]
            file_url = metadata['file_url']
            range_header = {'Range': request.headers.get('Range', 'bytes=0-')}
            r = requests.get(file_url, headers=range_header, stream=True)
            start_bytes = int(range_header['Range'].split('=', 1)[1].split('-', 1)[0])
            blowfish_key = metadata['bf_key']
            iv = b'\x00\x01\x02\x03\x04\x05\x06\x07'

            def generate():
                nonlocal start_bytes
                # if start_bytes is not a multiple of 2048, first yield will be < 2048 to fix the chunks
                extra_bytes = start_bytes % 2048
                if extra_bytes != 0:
                    extra_bytes = 2048 - extra_bytes
                    chunk = next(r.iter_content(extra_bytes))
                    if start_bytes // 2048 == 0:
                        chunk = Blowfish.new(blowfish_key, Blowfish.MODE_CBC, iv).decrypt(chunk)
                    yield chunk
                    start_bytes += extra_bytes
                for i, chunk in enumerate(r.iter_content(2048), start_bytes // 2048):
                    if (i % 3) == 0 and len(chunk) == 2048:
                        chunk = Blowfish.new(blowfish_key, Blowfish.MODE_CBC, iv).decrypt(chunk)
                    yield chunk

            content_type = r.headers['Content-Type']
            rv = Response(generate(), 206, mimetype=content_type, content_type=content_type)
            rv.headers['Content-Range'] = r.headers['Content-Range']
            return rv
        return '400'


    @app.route('/system-audio/')
    @app.route('/system-audio/<get_thumb>')
    def api_system_audio(get_thumb=''):
        """
        send system audio to chromecast
        """
        if get_thumb:
            return send_file(io.BytesIO(b64decode(custom_art('SYS'))), download_name='thumbnail.png',
                             mimetype='image/png', as_attachment=True, max_age=360000, conditional=True)
        return Response(sar.get_audio_data(settings['sys_audio_delay']))


    @app.post('/modify-queue/')
    def api_modify_queue():
        if request.headers.get('x-api-key') != settings['api_key']:
            return {'error': 'Unauthorized, api_key=not-provided'}, 401
        data = request.get_json(force=True, silent=True)
        if not isinstance(data, dict):
            return '', 400
        # clear ignores indices, so let callers omit them
        indices = data.get('indices', [] if data.get('action') == 'clear' else None)
        action = data.get('action')
        if not isinstance(indices, list) or not all(isinstance(i, int) and i >= 0 for i in indices):
            return '', 400
        if action == 'next_up':
            move_to_next_up(indices)
        elif action == 'remove':
            remove_from_queue(indices)
        elif action == 'clear':
            clear_queue()
        else:
            return '', 400
        return '', 204

    def move_to_next_up(indices):
        indices.sort()
        for i, index_to_move in enumerate(indices, 1):
            dq_len = len(done_queue)
            nq_len = len(next_queue)
            if index_to_move < dq_len:
                track = done_queue[index_to_move]
                del done_queue[index_to_move]
                if settings['reversed_play_next']:
                    next_queue.appendleft(track)
                else:
                    next_queue.append(track)
                if i == len(indices):  # update gui after the last swap
                    save_queues()
            elif index_to_move > dq_len + nq_len:
                track = music_queue[index_to_move - dq_len - nq_len]
                del music_queue[index_to_move - dq_len - nq_len]
                if settings['reversed_play_next']:
                    next_queue.appendleft(track)
                else:
                    next_queue.append(track)
                if i == len(indices):  # update gui after the last swap
                    save_queues()

    def remove_from_queue(indices):
        indices.sort(reverse=True)
        for i, index_to_remove in enumerate(indices, 1):
            dq_len, nq_len, mq_len = len(done_queue), len(next_queue), len(music_queue)
            if index_to_remove < dq_len:
                del done_queue[index_to_remove]
            elif index_to_remove == dq_len:
                with suppress(IndexError):
                    # remove the "0. XXX" track that could be playing right now
                    music_queue.popleft()
                    if next_queue:
                        music_queue.appendleft(next_queue.popleft())
                    # if queue is empty but repeat is all AND there are tracks in the done_queue
                    if not music_queue and settings['repeat'] is False and done_queue:
                        music_queue.extend(done_queue)
                        done_queue.clear()
                    # start playing new track if a track was being played
                    if not sar.alive:
                        if music_queue and playing_status.busy():
                            play()
                        else:
                            stop('remove_track')
            elif index_to_remove <= nq_len + dq_len:
                del next_queue[index_to_remove - dq_len - 1]
            elif index_to_remove < nq_len + mq_len + dq_len:
                del music_queue[index_to_remove - dq_len - nq_len]

    def apply_queue_setting_side_effects(setting_key):
        """
        Side effects the queue settings need no matter which frontend toggled them.
        Call after update_settings() has stored the new value.
        """
        if setting_key == 'persistent_queue':
            if settings['persistent_queue']:
                save_queues()
            else:
                update_settings('queues', {'done': [], 'music': [], 'next': []})
            # persistent_queue and populate_queue_startup are mutually exclusive
            update_settings('populate_queue_startup', False)
        elif setting_key == 'populate_queue_startup':
            update_settings('persistent_queue', False)

    def clear_queue():
        if playing_status.busy():
            stop('clear_queue')
        music_queue.clear()
        next_queue.clear()
        done_queue.clear()
        save_queues()

    def cast_try_reconnect(switch_twice=False):
        global cast_browser, zconf
        if switch_twice and cast is not None:
            app_log.info('try changing devices to local and then back to cast')
            cast_uuid = cast.uuid
            if not playing_status.playing():
                change_device()
                change_device(cast_uuid)
            app_log.info('try changing devices to local and then back to cast')
        app_log.info('stop discovery')
        cast_browser.stop_discovery()
        zconf = zeroconf.Zeroconf()
        cast_browser = pychromecast.discovery.CastBrowser(MyCastListener(), zconf)
        cast_browser.start_discovery()
        wait_until = time.monotonic() + WAIT_TIMEOUT
        while cast is None and time.monotonic() < wait_until:
            time.sleep(0.2)
        if cast is None:
            app_log.error('could not reconnect to cast')
        return cast is not None


    @cmp_to_key
    def cast_info_sorter(ci1: CastInfo, ci2: CastInfo):
        # sort by groups, then by name, then by UUID
        if ci1.cast_type == 'group' and ci2.cast_type != 'group':
            return -1
        if ci1.cast_type != 'group' and ci2.cast_type == 'group':
            return 1
        if ci1.friendly_name < ci2.friendly_name:
            return -1
        if ci1.friendly_name > ci2.friendly_name:
            return 1
        if str(ci1.uuid) > str(ci2.uuid):
            return 1
        return -1


    def get_devices():
        lo_cis = sorted(cast_browser.devices.values(), key=cast_info_sorter)
        lo_devices = [Device()]
        lo_devices.extend((Device(cast_info) for cast_info in lo_cis))
        return lo_devices


    class NoUpdateFound(Exception):
        pass


    class StatusCastListener(CastStatusListener):
        """Cast status listener"""

        def __init__(self, _cast):
            self.cast = _cast
            self.name = _cast.name

        def new_cast_status(self, status):
            pass


    class MediaCastListener(MediaStatusListener):
        def __init__(self, _cast):
            self.cast = _cast
            self.name = _cast.name

        def new_media_status(self, status):
            pass

        def load_media_failed(self, item, error_code):
            pass

    class MyCastListener(pychromecast.discovery.AbstractCastListener):

        def add_cast(self, uuid, _service: str):
            """Called when a new cast has been discovered."""
            global cast
            cast_info = cast_browser.devices[uuid]
            if str(cast_info.uuid) == settings['device']:
                # if currently connected to local device or another cast, change device
                if cast is None or cast.uuid != cast_info.uuid:
                    change_device(cast_info.uuid)
                else:
                    # otherwise, update the cast variable
                    cast = pychromecast.get_chromecast_from_cast_info(cast_info, zconf=zconf)
                    try:
                        if cast.is_idle:
                            cast.wait(30)
                    except Exception as e:
                        app_log.exception('could not wait on cast')
                        handle_exception(e)
                    # cast.register_status_listener(StatusCastListener(cast))
                    # cast.media_controller.register_status_listener(MediaCastListener(cast))
            refresh_tray(True)

        def remove_cast(self, uuid, _service: str, cast_info):
            """Called when a cast has been lost (MDNS info expired or host down)."""
            global cast
            if cast is not None and cast.uuid == uuid:
                # lost connection to connected device
                app_log.info(f'Lost connection to {cast.name} ({uuid}), switching to local device')
            refresh_tray(True)

        def update_cast(self, uuid, _service: str):
            """Called when a cast has been updated (MDNS info renewed or changed)."""
            global cast
            # not entirely sure what to do if this function is called
            # due to recent connection errors, let's experiment
            # if we should update the cast variable?
            if cast is not None and cast.uuid == uuid:
                cast_info = cast_browser.devices[uuid]
                cast_2 = pychromecast.get_chromecast_from_cast_info(cast_info, zconf=zconf)
                try:
                    assert cast_2 == cast
                except AssertionError as e:
                    handle_exception(e)
                cast = cast_2
            refresh_tray(True)


    def get_device(device_uuid):
        # UnboundLocalError is possible
        return pychromecast.get_chromecast_from_cast_info(cast_browser.devices[device_uuid], zconf)


    def change_device(new_uuid='local', unresponsive_cast=False):
        """switch_device
        if new_uuid is invalid, then the local device is selected
        """
        global cast
        app_log.info(f'change_device({new_uuid})')
        try:
            if not isinstance(new_uuid, UUID):
                new_uuid = UUID(hex=new_uuid)
            try:
                if cast.uuid == new_uuid:
                    app_log.info('noop because we are already connected to device wanting to change to')
                    return True
                app_log.info(f'changing device from {cast.cast_info.friendly_name} ({cast.uuid})')
            except AttributeError:
                app_log.info('changing device from local')
            if new_uuid not in cast_browser.devices:
                return False
            new_device = get_device(new_uuid)
            app_log.info(f'new device name: {new_device.cast_info.friendly_name}')
        except (ValueError, TypeError):
            # local device selected (any non uuid string)
            new_device = None
        except UnboundLocalError:
            app_log.exception('Could not connect to cast device')
            tray_notify(t('ERROR') + ': ' + t('Could not connect to cast device'))
            return False
        if cast == new_device:
            # do not change device if local device is selected again
            return True
        # cache information
        current_pos = 0
        if cast is not None and cast.app_id == APP_MEDIA_RECEIVER:
            if not unresponsive_cast and playing_status.busy():
                mc = cast.media_controller
                with suppress(PyChromecastError, AssertionError):
                    mc.update_status()  # Switch device without playback loss
                    current_pos = mc.status.adjusted_current_time
                    if mc.status.player_is_playing or mc.status.player_is_paused:
                        mc.stop()
            with suppress(PyChromecastError, AssertionError):
                cast.quit_app(10)
        elif cast is None and 'audio_player' in globals() and audio_player.is_busy():
            current_pos = audio_player.stop()
        autoplay = playing_status.playing()
        was_busy = playing_status.busy()
        playing_status.stop()
        cast = new_device
        update_settings('device', None if cast is None else str(cast.uuid))
        refresh_tray(True)
        if was_busy and (music_queue or sar.alive):
            app_log.info('continuing playback on new device')
            if sar.alive:
                play_system_audio(switching_device=True)
            else:
                play(position=current_pos, autoplay=autoplay, switching_device=True, show_error=True)
        else:
            if cast is not None:
                with suppress(PyChromecastError):
                    cast.quit_app(30)
                try:
                    cast.wait(timeout=WAIT_TIMEOUT)
                except RequestTimeout:
                    tray_notify(t('ERROR') + ': ' + t('Could not connect to cast device'))
            update_volume(0 if settings['muted'] else settings['volume'], 'change_device')
        return True


    def un_shuffle_queue():
        """
        To be called when shuffle is toggled off
            sorts files by natural key...
            splits at current playing
        Does not affect next_queue
        Keeps currently playing the same
        """
        global music_queue, done_queue
        if music_queue:
            # keep current playing track the same
            track = music_queue[0]
            temp_list = list(music_queue) + list(done_queue)
            temp_list.sort(key=natural_key_file)
            split_queue_at = temp_list.index(track)
            done_queue = deque(temp_list[:split_queue_at])
            music_queue = deque(temp_list[split_queue_at:])
        elif done_queue:
            # sort and set queue to first item
            music_queue = deque(sorted(done_queue, key=natural_key_file))
            done_queue.clear()
        save_queues()


    def shuffle_queue():
        """
        To be called when shuffle is toggled  on
            extends the music_queue with done_queue
            and then shuffles it
        Does not affect next_queue
        Keeps currently playing the same
        """
        global music_queue
        # keep track the same if in the process of playing something
        first_index = 1 if playing_status.busy() and music_queue else 0
        music_queue.extend(done_queue)
        done_queue.clear()
        # shuffle is slow for a deque so use a list
        temp_list = list(music_queue)
        better_shuffle(temp_list, first=first_index)
        music_queue = deque(temp_list)
        save_queues()


    def format_pl_lb(tracks):
        """Return (list of formatted tracks, readable playlist time length) for playlist listbox"""
        formatted_tracks = []
        pl_length = 0
        for i, track in enumerate(tracks):
            formatted_tracks.append(f"{i + 1}. {format_uri(track, _for='pl')}")
            with suppress(KeyError):
                metadata = get_uri_metadata(track, read_file=False)
                length = metadata.get('length')
                if length is not None:
                    pl_length += length
        friendly_length = ''
        if pl_length > 3600:
            hours = pl_length // 3600
            friendly_length = f'{hours:.0f}h '
            pl_length -= hours * 3600
        if pl_length > 60:
            minutes = pl_length // 60
            friendly_length += f'{minutes:.0f}m '
            pl_length -= minutes * 60
        friendly_length += f'{pl_length:.0f}s'
        if friendly_length == '0s':
            friendly_length = ''
        return formatted_tracks, friendly_length


    def format_uri(uri: str, use_basename=False, _for=''):
        try:
            if use_basename:
                raise TypeError
            metadata = get_uri_metadata(uri, read_file=False)
            title, artist, album = metadata['title'], metadata['artist'], metadata['album']
            if title == Unknown('Title'):
                title = os.path.splitext(os.path.basename(uri))[0]
                if '-' in title:
                    artist, title = title.split('-', maxsplit=1)
                    artist, title = artist.strip(), title.strip()
            else:
                assert not isinstance(title, Unknown)
            if uri in url_metadata and '-' in title:
                artist, title = title.split('-', maxsplit=1)
                artist, title = artist.strip(), title.strip()
            formatted = settings['track_format'].replace('&artist', str(artist)).replace('&title', title)
            formatted = formatted.replace('&alb', str(album))
            number = metadata.get('track_number', '0').zfill(2)
            if '&trck' in formatted:
                formatted = formatted.replace('&trck', str(number))
            elif settings['show_track_number'] and number != '':
                formatted = f'[{number}] {formatted}'
            if not _for:
                return formatted
            # at > ?, we need to cut characters
            if (cut_out := len(formatted) - {'queue': 70, 'pl': 50}[_for]) > 0:
                cut_out = (cut_out + 3) // 2  # for 3 dots
                middle = len(formatted) // 2
                ro = middle + cut_out
                lo = middle - cut_out
                formatted = formatted[:lo] + '...' + formatted[ro:]
            return formatted
        except (TypeError, KeyError):
            if uri.startswith('http'):
                return uri
            return os.path.splitext(os.path.basename(uri))[0]


    def create_track_list():
        """Return usable list for queue listbox """
        try:
            max_digits = int(log10(max(len(music_queue) - 1 + len(next_queue), len(done_queue) * 10))) + 2
        except ValueError:
            max_digits = 0
        i = -len(done_queue)
        tracks = []
        # format: Index | Artists - Title
        try:
            for items in (done_queue, islice(music_queue, 0, 1), next_queue, islice(music_queue, 1, None)):
                for uri in items:
                    formatted_track = format_uri(uri, _for='queue')
                    if settings['show_queue_index']:
                        if i < 0:
                            pre = f'\u2012{abs(i)} '.center(max_digits, '\u2000')
                        else:
                            pre = f'{i} '.center(max_digits, '\u2000')
                        formatted_track = f'\u2004{pre}|\u2000{formatted_track}'
                        i += 1
                    tracks.append(formatted_track)
            return tracks
        except RuntimeError:
            # deque mutated during iteration
            return create_track_list()


    def after_play(title, artists: str, album, autoplay, switching_device):
        app_log.info(f'autoplay={autoplay}, switching_device={switching_device}')
        # prevent the system from going to sleep
        if autoplay:
            prevent_sleep()
            playing_status.play()
            # system_media_controls.set_playing()
        else:
            playing_status.pause()
            # system_media_controls.set_paused()
        refresh_tray()
        save_queues()
        DiscordPresence.update(t('By') + f': {artists}', title, t('Listening'), confirm_connect=settings['discord_rpc'])
        # update metadata of the player
        # if platform.system() == 'Windows':
            # bg = settings['theme']['background']
            # # base64
            # try:
            #     album_art_data = resize_img(get_current_art(), bg, COVER_NORMAL, default_art=DEFAULT_ART)
            # except OSError as e:
            #     handle_exception(e)
            #     album_art_data = resize_img(DEFAULT_ART, bg, COVER_NORMAL)
            # img_data = io.BytesIO(b64decode(album_art_data))
            # album_art: Image.Image = Image.open(img_data)
            # thumb_path = Path('thumb.jpg').absolute()
            # TODO: convert to mode RGB in case RGBA
            # album_art.save(thumb_path)
            # system_media_controls.set_metadata(title, artists, album, thumb_path.as_uri())
            # system_media_controls.update_time()
        return True


    def play_system_audio(switching_device=False, show_error=False):
        global track_position, track_start, track_end, track_length
        if cast is None:
            tray_notify(t('ERROR') + ': ' + t('Not connected to a cast device'))
            sar.alive = False
            return False
        try:
            cast.wait(timeout=WAIT_TIMEOUT)
            cast.set_volume(0 if settings['muted'] else settings['volume'] / 100)
            mc = cast.media_controller
            if mc.status.player_is_playing or mc.status.player_is_paused:
                mc.stop()
                mc.block_until_active(WAIT_TIMEOUT)
            title = 'System Audio'
            artist = platform.node()
            album = 'Music Caster'
            metadata = {'metadataType': 3, 'albumName': album, 'title': title, 'artist': artist}
            url_metadata['SYSTEM_AUDIO'] = {'artist': artist, 'title': title, 'album': album}
            # start recording system audio BEFORE the first request for data
            if not sar.start():
                tray_notify(t('ERROR') + ': ' + t('Could not find an output device to record'))
                return False
            api_key = settings['api_key']
            url = f'http://{get_ipv4()}:{State.PORT}/system-audio/?api_key={api_key}'
            mc.play_media(url, 'audio/wav', metadata=metadata, thumb=f'{url}/thumb', stream_type='LIVE')
            mc.block_until_active(WAIT_TIMEOUT + 1)
            stream_start_time = time.monotonic()
            block_until = time.monotonic() + WAIT_TIMEOUT
            while not mc.status.player_is_playing and time.monotonic() < block_until:
                time.sleep(0.05)
            mc.play()
            sar.lag = time.monotonic() - stream_start_time  # ~1 second
            playing_status.play_system_audio()
            track_length = None
            track_position = 0
            track_start = time.monotonic()
            after_play(title, artist, album, True, switching_device)
            return True
        except OSError:
            tray_notify(t('ERROR') + ': ' + t('Could not find an output device to record'))
        except PyChromecastError as e:
            app_log.exception('play_sys_audio failed to cast')
            if show_error:
                tray_notify(t('ERROR') + ': ' + t('Could not connect to cast device') + ' (psa)')
                change_device(unresponsive_cast=True)
                return handle_exception(e)
            cast_try_reconnect()
            return play_system_audio(switching_device=switching_device, show_error=True)
        except Exception as e:
            handle_exception(e)
            tray_notify('ERROR: Something went wrong')
        return False

    def url_expired(uri):
        """ Returns if URI is a URL that has expired """
        expiry_time = url_metadata.get(uri, {}).get('expiry', 0)
        # if expiry_time is None, url does not have an expiry
        if expiry_time is None:
            return False
        return expiry_time < time.time()

    def get_url_metadata(url, fetch_art=True) -> list[dict | URLMetadata]:
        # TODO: cache in the database for persistence
        # TODO: move to utils.py and add parameter url_metadata_cache
        """
        Tries to parse url and set url_metadata[url] to parsed metadata
        Supports: YouTube, Soundcloud, any url ending with a valid audio extension
        """
        from yt_dlp.utils import YoutubeDLError
        global deezer_opened, attribute_error_reported
        ytsearch = 'ytsearch1'
        metadata_list = []
        app_log.info('get_url_metadata: ' + url)
        with DatabaseConnection() as conn:
            maybe_metadata = URLMetadata.from_db(conn, url)
            if maybe_metadata and not maybe_metadata.is_expired:
                return [maybe_metadata]
        if url in url_metadata and not url_expired(url):
            return [url_metadata[url]]
        if url.startswith('www'):
            url = f'http://{url}'
        # short-circuit
        if not url.startswith('http') and not url.startswith(ytsearch):
            return metadata_list
        if url.startswith('http') and valid_audio_file(url):  # source url e.g. http://...radio.mp3
            ext = url[::-1].split('.', 1)[0][::-1]
            url_frags = urlsplit(url)
            title, artist, album = url_frags.path.split('/')[-1], url_frags.netloc, url_frags.path[1:]
            url_metadata[url] = metadata = {'title': title, 'artist': artist, 'length': None, 'album': album,
                                            'src': url, 'url': url, 'ext': ext, 'expiry': None}  # never expires
            metadata_list.append(metadata)
        elif 'twitch.tv' in url:
            with suppress(StopIteration, IOError):
                r = ydl_extract_info(url, quiet=not is_debug())
                audio_url = max(r['formats'], key=lambda item: item['tbr'] * (item['vcodec'] == 'none'))['url']
                # for now, expire immediately
                metadata = {'title': r['description'], 'artist': r['uploader'], 'ext': r['ext'],
                            'expiry': 0, 'album': 'Twitch', 'length': None,
                            'art': r['thumbnail'], 'url': r['url'], 'audio_url': audio_url, 'src': url}
                url_metadata[url] = metadata
                metadata_list.append(metadata)
        elif 'soundcloud.com' in url:
            with suppress(StopIteration, IOError):
                r = ydl_extract_info(url, quiet=not is_debug())
                if 'entries' in r:
                    for entry in r['entries']:
                        parsed_url = parse_qs(urlparse(entry['url']).query)['Policy'][0].replace('_', '=')
                        policy = b64decode(parsed_url).decode()
                        expiry_time = json.loads(policy)['Statement'][0]['Condition']['DateLessThan']['AWS:EpochTime']
                        album = entry.get('album', r.get('title', 'SoundCloud'))
                        metadata = {'title': entry['title'], 'artist': entry['uploader'], 'album': album,
                                    'length': entry['duration'], 'art': entry['thumbnail'], 'src': entry['webpage_url'],
                                    'url': entry['url'], 'ext': entry['ext'],
                                    'expiry': expiry_time}
                        url_metadata[entry['webpage_url']] = metadata
                        metadata_list.append(metadata)
                else:
                    url_policy_b64 = parse_qs(urlparse(r['url']).query)['Policy'][0].replace('_', '=')
                    policy = b64decode(url_policy_b64).decode()
                    expiry_time = json.loads(policy)['Statement'][0]['Condition']['DateLessThan']['AWS:EpochTime']
                    url_metadata[url] = metadata = {'title': r['title'], 'artist': r['uploader'], 'album': 'SoundCloud',
                                                    'src': url, 'ext': r['ext'], 'expiry': expiry_time,
                                                    'length': r['duration'], 'art': r['thumbnail'], 'url': r['url']}
                    metadata_list.append(metadata)
        # youtube
        elif (ytid := get_yt_id(url)) is not None or url.startswith(f'{ytsearch}:'):
            install_deno()
            # lazily get videos in the playlist
            if ytid is not None and ytid.startswith('PL'):
                videos = scrapetube.get_playlist(ytid)
                for i, video in enumerate(videos):
                    _url = f'https://www.youtube.com/watch?v={video["videoId"]}'
                    src_url = f'{_url}&list={ytid}'
                    # fetch first most URL of playlist so that play_url does not break
                    if not metadata_list:
                        if m_lst := get_url_metadata(_url):
                            m = m_lst[0]
                            m['pl_src'] = src_url
                            metadata_list.extend(m_lst)
                    else:
                        metadata = URLMetadata(
                            src=_url,
                            url_type='YouTube',
                            title=video['title']['runs'][0]['text'],
                            artist=video['shortBylineText']['runs'][0]['text'],
                            album='YouTube',
                            id= video['videoId'],
                            playlist_url=src_url,
                            expiry=0,
                            album_cover_url=f'https://img.youtube.com/vi/{ytid}/maxresdefault.jpg'
                        )
                        url_metadata[_url] = metadata
                        metadata_list.append(metadata)
            else:
                # type error in case video was deleted or unavailable
                try:
                    r = ydl_extract_info(url, quiet=not is_debug())
                    if 'entries' in r:
                        for entry in r['entries']:
                            metadata = ydl_get_metadata(entry, duration_helper=False)
                            metadata['ytid'] = entry['id']
                            # if duration > 10 minutes, try to parse out timestamps for track from comment section
                            if entry.get('duration', 0) > 600:
                                metadata['timestamps'] = get_video_timestamps(entry)
                            for webpage_url in get_yt_urls(entry['id']):
                                url_metadata[webpage_url] = metadata
                            metadata_list.append(metadata)
                    else:
                        # single video
                        metadata = ydl_get_metadata(r, duration_helper=False)
                        metadata['ytid'] = r['id']
                        # if duration > 10 minutes, try to parse out timestamps for track from comment section
                        if r.get('duration', 0) > 600:
                            metadata['timestamps'] = get_video_timestamps(r)
                        for webpage_url in get_yt_urls(r['id']):
                            url_metadata[webpage_url] = metadata
                        url_metadata[url] = metadata
                        metadata_list.append(metadata)
                except (IOError, TypeError) as e:
                    print('error', e)
                except AttributeError as e:
                    app_log.error(f'yt-dlp failed to extract {url}')
                    trace_back_msg = traceback.format_exc().replace('\\', '/')
                    if not attribute_error_reported:
                        if 'PhantomJS' in trace_back_msg:
                            try:
                                install_phantomjs(PHANTOMJS_DIR)
                                add_to_path(PHANTOMJS_DIR / 'bin')
                            except Exception:
                                open_in_browser('https://phantomjs.org/download.html')
                        if 'blocked it on copyright grounds' not in trace_back_msg:
                            attribute_error_reported = True
                            handle_exception(e)
        # Spotify restricted web API access
        elif url.startswith('https://open.spotify.com') and False:
            # spotify metadata has already been fetched, so just get youtube metadata
            if url in url_metadata and isinstance(url_metadata[url], dict):
                metadata = url_metadata[url]
                if 'ytid' in metadata:
                    youtube_metadata = get_url_metadata(f"https://www.youtube.com/watch?v={metadata['ytid']}", False)
                else:
                    query = f"{get_first_artist(metadata['artist'])} - {metadata['title']}"
                    youtube_metadata = get_url_metadata(f'{ytsearch}:{query}', False)
                    if metadata['src'] == '':
                        metadata['src'] = youtube_metadata['src']
                if youtube_metadata:
                    youtube_metadata = youtube_metadata[0]
                    # these are the only fields we need to update since they actually expire
                    for key in ('expiry', 'url', 'audio_url', 'ext', 'ytid', 'length'):
                        metadata[key] = youtube_metadata[key]
                    url_metadata[metadata['src']] = url_metadata[youtube_metadata['src']] = metadata
                    metadata_list.append(metadata)
                else:
                    error_msg = t('ERROR') + ': ' + t('Could not fetch audio for $URL').replace('$URL', url) + ' :('
                    tray_notify(error_msg)
            else:
                # get a list of spotify tracks from the track/album/playlist Spotify URL
                try:
                    spotify_tracks = get_spotify_tracks(url)
                except AttributeError:
                    spotify_tracks = []
                except Exception as e:
                    handle_exception(e)
                    spotify_tracks = []
                if spotify_tracks:
                    metadata = spotify_tracks[0]
                    query = f"{get_first_artist(metadata['artist'])} - {metadata['title']}"
                    youtube_metadata = get_url_metadata(f'{ytsearch}:{query}', False)
                    if youtube_metadata:
                        youtube_metadata = youtube_metadata[0]
                        # expiry, url, and audio_url are not overwritten here
                        metadata = {**youtube_metadata, **metadata}
                        if metadata['src'] == '':
                            metadata['src'] = youtube_metadata['src']
                        url_metadata[metadata['src']] = url_metadata[youtube_metadata['src']] = metadata
                        # if url is a spotify track, set its metadata
                        if len(spotify_tracks) == 1:
                            url_metadata[url] = metadata
                        metadata_list.append(metadata)
                        for spotify_track in islice(spotify_tracks, 1, None):
                            url_metadata[spotify_track['src']] = spotify_track
                            uris_to_scan.put(spotify_track['src'])
                            metadata_list.append(spotify_track)
        elif url.startswith('https://deezer.page.link') or url.startswith('https://www.deezer.com'):
            try:
                for metadata in get_deezer_tracks(url):
                    url_metadata[metadata['src']] = metadata
                    metadata_list.append(metadata)
            except LookupError:
                # login cookie not found
                # first time open the browser
                if not deezer_opened:
                    open_in_browser('https://www.deezer.com/login')
                    tray_notify(t('ERROR') + ': ' + t('Not logged into deezer.com'))
                    deezer_opened = True
                # fallback to deezer -> youtube
                if url in url_metadata:
                    metadata = url_metadata[url]
                    query = f"{get_first_artist(metadata['artist'])} - {metadata['title']}"
                    youtube_metadata = get_url_metadata(f'{ytsearch}:{query}', False)[0]
                    metadata = {**youtube_metadata, **metadata}
                    url_metadata[metadata['src']] = url_metadata[youtube_metadata['src']] = metadata
                    metadata_list.append(metadata)
                else:
                    deezer_tracks = get_deezer_tracks(url, login=False)
                    if deezer_tracks:
                        metadata = deezer_tracks[0]
                        query = f"{get_first_artist(metadata['artist'])} - {metadata['title']}"
                        youtube_metadata = get_url_metadata(f'{ytsearch}:{query}', False)[0]
                        metadata = {**youtube_metadata, **metadata}
                        url_metadata[metadata['src']] = url_metadata[youtube_metadata['src']] = metadata
                        metadata_list.append(metadata)
                        for deezer_track in islice(deezer_tracks, 1, None):
                            url_metadata[deezer_track['src']] = deezer_track
                            uris_to_scan.put(deezer_track['src'])
                            metadata_list.append(deezer_track)
        else:
            with suppress(IOError, TypeError, AttributeError, YoutubeDLError):
                r = ydl_extract_info(url, quiet=not is_debug())
                if 'entries' in r:
                    for entry in r['entries']:
                        url_metadata[entry['webpage_url']] = metadata = ydl_get_metadata(entry)
                        metadata_list.append(metadata)
                else:
                    url_metadata[url] = url_metadata[r['webpage_url']] = metadata = ydl_get_metadata(r)
                    metadata_list.append(metadata)
        if metadata_list and fetch_art:
            # fetch and cache artwork for first url
            metadata = metadata_list[0]
            if metadata.get('art') is not None and 'art_data' not in metadata:
                art_url = metadata['art']
                try:
                    url_metadata[metadata['src']]['art_data'] = b64encode(requests.get(art_url).content)
                except requests.RequestException as e:
                    app_log.info(f'Could not fetch art url {art_url}')
                    handle_exception(e)
        return metadata_list


    def play_url(position=0, autoplay=True, switching_device=False, show_error=False) -> bool:
        global cast, playing_url, track_length, track_start, track_end, track_position
        url = music_queue[0]
        if not url.startswith('http') and not url.startswith('www') and not url.startswith('//'):
            return False
        metadata_list = get_url_metadata(url)
        if not metadata_list:
            app_log.error('Could not play URL')
            if settings['notifications']:
                tray_notify(
                    t('ERROR') + ': ' + t('Could not play $URL').replace('$URL', url)
                )
            return False
        if len(metadata_list) > 1:
            # url was for multiple sources
            with suppress(IndexError):
                music_queue.popleft()
            music_queue.extendleft((metadata['src'] for metadata in reversed(metadata_list)))
        metadata = metadata_list[0]
        title, artist, album = metadata['title'], metadata['artist'], metadata['album']
        ext = metadata['ext']
        url = metadata['audio_url'] if cast is None and 'audio_url' in metadata else metadata['url']
        api_key = settings['api_key']
        thumbnail = metadata['art'] if 'art' in metadata else f'{get_ipv4()}/file?path=DEFAULT_ART&api_key={api_key}'
        # can be None
        track_length = metadata['length']
        try:
            app_log.info(f'cast.socket_client.is_alive(): {cast.socket_client.is_alive()}')
            cast.wait(timeout=WAIT_TIMEOUT)
            cast.set_volume(0 if settings['muted'] else settings['volume'] / 100)
            mc = cast.media_controller
            _metadata = {'metadataType': 3, 'albumName': album, 'title': title, 'artist': artist}
            stream_type = 'LIVE' if track_length is None else 'BUFFERED'
            mc.play_media(url, f'video/{ext}', metadata=_metadata, thumb=thumbnail,
                            current_time=position, autoplay=autoplay, stream_type=stream_type)
            mc.block_until_active(WAIT_TIMEOUT)
            if track_length is None:
                mc.play()
        except AttributeError:
            # cast is None, so play on local
            volume = 0 if settings['muted'] else settings['volume'] / 100
            if autoplay or not metadata.get('is_live', False):
                audio_player.play(
                    url, start_playing=autoplay, start_from=position, volume=volume
                )
        except NotConnected:
            app_log.error('play_url failed to cast because cast was not connected')
            tray_notify(
                t('ERROR')
                + ': '
                + t('Could not connect to cast device')
                + ' (play_url)'
            )
            change_device(unresponsive_cast=True)
            return False
        except (PyChromecastError, OSError) as e:
            app_log.exception('play_url failed to cast')
            if show_error:
                tray_notify(
                    t('ERROR')
                    + ': '
                    + t('Could not connect to cast device')
                    + ' (play_url)'
                )
                return handle_exception(e)
            cast_try_reconnect()
            return play_url(position, autoplay, switching_device, show_error=True)
        playing_status.play_uri(position, track_length, cast is None)
        track_position = position
        track_start = time.monotonic() - track_position
        if track_length is not None:
            track_end = track_start + track_length
        playing_url = True
        after_play(title, artist, album, autoplay, switching_device)
        return True

    # up to 4 seconds!
    def play(position=0, autoplay=True, switching_device=False, show_error=False, from_set_pos=False):
        global cast, track_start, track_end, track_length, track_position, music_queue, playing_url, cast_browser, zconf, LAST_PLAYED
        uri = music_queue[0]
        while not os.path.exists(uri):
            if play_url(position, autoplay, switching_device):
                return
            app_log.info(f'{uri} does not exist or is unplayable')
            # it's possible that these queues are empty
            with suppress(IndexError):
                done_queue.append(music_queue.popleft())
            with suppress(IndexError):
                music_queue.appendleft(next_queue.popleft())
            try:
                uri, position = music_queue[0], 0
            except IndexError:
                return
        uri_path = Path(uri)
        uri = uri_path.as_posix()
        playing_url = sar.alive = False
        app_log.info(f'{uri_path.name} @{position}, autoplay={autoplay}, switching_device={switching_device}')
        try:
            track_length = get_audio_length(uri)
        except InvalidAudioFile:
            done_queue.append(music_queue.popleft())
            msg = t('ERROR') + ': ' + t('Invalid audio file $FILE').replace('$FILE', uri)
            tray_notify(msg)
            if music_queue:
                play()
            return
        metadata = get_metadata_wrapped(uri)
        # update metadata of track in case something changed
        all_tracks[uri] = metadata
        volume = 0 if settings['muted'] else settings['volume'] / 100
        if cast is None:  # play locally
            audio_player.play(uri, volume=volume, start_playing=autoplay, start_from=position)
            playing_status.play_uri(position, track_length, True)
        else:
            # track_end = time.monotonic() + WAIT_TIMEOUT * 2 + 1
            try:
                url_args = urllib.parse.urlencode({'path': uri, 'api_key': settings['api_key']})
                url = f'http://{get_ipv4()}:{State.PORT}/file?{url_args}'
                app_log.info(f'calling cast.wait on device {cast.cast_info.friendly_name} / {cast.uuid}')
                app_log.info(f'cast.media_controller player state: {cast.media_controller.status.player_state}')
                cast.wait(timeout=15 if show_error else WAIT_TIMEOUT)
                if not from_set_pos:
                    app_log.info(f'try: cast.set_volume({volume})')
                    with suppress(RequestTimeout):
                        cast.set_volume(volume)
                mc = cast.media_controller
                # https://developers.google.com/cast/docs/reference/web_receiver/cast.framework.messages#.MetadataType
                metadata = {'title': str(metadata['title']), 'artist': str(metadata['artist']),
                            'albumName': str(metadata['album']), 'metadataType': 3}
                ext = uri.split('.')[-1]
                # pychromecast.error.NotConnected: Chromecast unknown:8009 is connecting..
                mc.play_media(url, f'audio/{ext}', current_time=position,
                              metadata=metadata, thumb=f'{url}&thumbnail_only=true', autoplay=autoplay)
                mc.block_until_active(WAIT_TIMEOUT)
                playing_status.play_uri(position, track_length, False)
                app_log.info(f'mc.status.player_state={mc.status.player_state}')
            except (NotConnected, AttributeError) as e:
                app_log.exception('cast device is not connected')
                app_log.info(f'cast.media_controller player state: {cast.media_controller.status.player_state}')
                r"""
                2022-03-09 10:52:40,920 ERROR (396): [Computer room(192.168.1.9):8009]
                Failed to connect to service HostServiceInfo(type='mdns',
                data='Google-Home-Mini-$HASH._googlecast._tcp.local.'), retrying in 5.0s
                Traceback (most recent call last):
                  File "music_caster.py", line 1733, in play
                  File "pychromecast/controllers/receiver.py", line 181, in set_volume
                  File "pychromecast/controllers/__init__.py", line 95, in send_message
                  File "pychromecast/controllers/__init__.py", line 99, in send_message_nocheck
                  File "pychromecast/socket_client.py", line 930, in send_platform_message
                  File "pychromecast/socket_client.py", line 924, in send_message
                pychromecast.error.NotConnected: Chromecast 192.168.1.9:8009 is connecting...
                """
                if not IS_FROZEN or is_debug():
                    print(e)
                if show_error:
                    tray_notify(t('ERROR') + ': ' + t('Could not connect to cast device') + ' (play)')
                    change_device(unresponsive_cast=True)
                    return False
                return play(position=position, autoplay=autoplay, switching_device=switching_device, show_error=True)
            except (PyChromecastError, OSError, RuntimeError, AssertionError) as e:
                r"""
                Traceback (most recent call last):
                File "music_caster.py", line 2137, in play
                File "pychromecast\__init__.py", line 505, in wait
                pychromecast.error.RequestTimeout: Execution of wait timed out after 5 s.
                """
                app_log.exception('play failed to cast')
                app_log.info(f'cast.media_controller player state: {cast.media_controller.status.player_state}')
                app_log.info('falling back to playing on local device')
                if not show_error:
                    try_reconnecting = True
                    if cast.media_controller.status.player_state == 'UNKNOWN':
                        try:
                            cast.media_controller.stop()
                            cast.quit_app(15)
                            cast.wait(15)
                            try_reconnecting = False
                        except PyChromecastError as e:
                            app_log.exception('failed to stop, quit, or wait on cast device')
                            handle_exception(e)
                    if try_reconnecting and not cast_try_reconnect():
                        show_error = True
                if show_error:
                    tray_notify(t('ERROR') + ': ' + t('Could not connect to cast device') + ' (play)')
                    change_device(unresponsive_cast=True)
                    handle_exception(e)
                    switching_device=True
                return play(position=position, autoplay=autoplay, switching_device=switching_device, show_error=True)
        track_position = position
        track_start = time.monotonic() - track_position
        track_end = track_start + track_length
        app_log.info(f'track_end = {track_end:.2f}, track_start = {track_start:.2f}, track_length = {track_length:.2f}')
        LAST_PLAYED = time.time()
        return after_play(metadata['title'], metadata['artist'], metadata.get('album'), autoplay, switching_device)


    def metadata_key(filename, album_sort=True):
        """ Sort by (artist, album, track number, title) """
        m = get_uri_metadata(filename)
        try:
            tn = int(m.get('track_number'))
        except (ValueError, TypeError):
            tn = 1
        return (m['album'].casefold() if album_sort else ''), tn, m['artist'].casefold(), m['title'].casefold()


    def play_uris(uris: Iterable, return_if_empty=True, queue_uris=False,
                  play_next=False, merge_tracks=0, natural_sort=True):
        """
        TODO: make thread safe
        Appends all music files in the provided uris (playlist names, folders, files, urls) to a temp list,
            which is shuffled if shuffled is enabled in settings, and then extends music_queue.
            Note: valid filesystem paths take precedence over playlist names
        If queue_only is false, the music queue and done queue are cleared,
            before files are added to the music_queue
        play_next has priority over queue_uris
        merge_tracks indicates the number of tracks that were already propogated but need to be merged
        If sort is False, shuffle being off does not sort items
        """
        temp_queue, albums_found = [], set()
        for track in get_audio_uris(uris):
            album_name = get_uri_metadata(track)['album']
            if not isinstance(album_name, Unknown):
                albums_found.add(album_name)
            elif album_name != Unknown('Album'):
                # NOTE: debugging purpose
                # TODO: remove condition
                handle_exception(Exception(f'found incorrect {album_name} instead of Unknown("Album")'))
            temp_queue.append(track)
        if not temp_queue and return_if_empty:
            return False
        # fresh play condition
        if not queue_uris and not play_next and merge_tracks == 0:
            music_queue.clear()
            done_queue.clear()
        # handle merge_tracks case
        if merge_tracks > 0:
            with suppress(IndexError):
                if play_next:
                    if settings['reversed_play_next']:
                        for _ in range(merge_tracks):
                            temp_queue.append(next_queue.popleft())
                    else:
                        for _ in range(merge_tracks):
                            temp_queue.append(next_queue.pop())
                elif queue_uris:
                    for _ in range(merge_tracks):
                        temp_queue.append(music_queue.pop())
                else:  # to play
                    for _ in range(merge_tracks):
                        temp_queue.append(music_queue.popleft())
        # shuffle or sort
        if settings['shuffle']:
            shuffle(temp_queue)
        elif natural_sort:
            temp_queue.sort(key=natural_key_file)
        else:
            # do custom sort only if possible album was queued
            try:
                temp_queue.sort(key=lambda filename: metadata_key(filename, album_sort=len(albums_found) > 1))
            except Exception as e:
                app_log.exception('could not sort temp_queue')
                handle_exception(e)
        # add to next queue condition
        if play_next:
            if settings['reversed_play_next']:
                next_queue.extendleft(reversed(temp_queue))
            else:
                next_queue.extend(temp_queue)
            save_queues()
            return True
        # extend only if merge_tracks == 0 or we are queueing the tracks
        if queue_uris or merge_tracks == 0:
            music_queue.extend(temp_queue)
        else:  # API play command with history (merge_tracks > 0)
            music_queue.extendleft(reversed(temp_queue))
        if not queue_uris:
            if music_queue:
                play()
                return True
            elif next_queue:
                playing_status.play()
                next_track()
                return True
        save_queues()
        return True


    def play_all(starting_files: Iterable = None, queue_only=False):
        """
        Clears done queue, music queue, adds starting files to music queue.
        Shuffles and queues files in the library without duplication
        """
        if starting_files is None:
            starting_files = []
        if not queue_only:
            music_queue.clear()
            done_queue.clear()
        music_queue.extend(starting_files)
        ignore_files = set(starting_files).union(music_queue).union(done_queue).union(next_queue)
        if indexing_tracks_thread is not None and indexing_tracks_thread.is_alive() and settings['notifications']:
            info = t('INFO')
            tray_notify(f'{info}: ' + t('Library indexing incomplete, only scanned files have been added'))
        start_shuffle_from = len(music_queue)
        music_queue.extend(index_all_tracks(False, ignore_files).keys())
        better_shuffle(music_queue, start_shuffle_from)
        if not queue_only:
            if not music_queue and next_queue:
                music_queue.append(next_queue.popleft())
            if music_queue:
                play()
        save_queues()


    def queue_all():
        if not any(filter(lambda thread: thread.name == 'PlayAll', threading.enumerate())):
            Thread(target=play_all, kwargs={'queue_only': True}, daemon=True, name='PlayAll').start()

    def open_dialog(title, for_dir=False, filetypes=None, single_file=False):
        if settings['use_last_folder']:
            prev_folder = initial_folder = settings['last_folder']
            while not os.path.exists(initial_folder):
                initial_folder = Path(initial_folder).parent.absolute()
                if prev_folder == initial_folder:  # prevent infinite loop
                    initial_folder = get_default_music_folder()
                    break
        else:
            initial_folder = get_default_music_folder()
        return []


    def file_action(action='pf'):
        """
        action = {'pf': 'Play Files', 'pfn': 'Play Files Next', 'qf': 'Queue Files'}
        :param action: one of {'pf': 'Play Files', 'pfn': 'Play Files Next', 'qf': 'Queue Files'}
        :return:
        """
        paths = open_dialog(t('Select Audio Files'), filetypes=AUDIO_FILE_TYPES)
        if paths:
            natural_sort = len(paths) > 20
            update_settings('last_folder', os.path.dirname(paths[-1]))
            app_log.info(f'file_action(action={action}), len(lst) is {len(paths)}')
            if action in {t('Play'), 'pf'}:
                if settings['queue_library']:
                    return play_all(starting_files=paths)
                return play_uris(paths, natural_sort=natural_sort)
            if action in {t('Queue'), 'qf'}:
                return play_uris(paths, queue_uris=True, natural_sort=natural_sort)
            if action in {t('Play Next'), 'pfn'}:
                return play_uris(paths, play_next=True, natural_sort=natural_sort)


    def folder_action(action='pf'):
        """
        :param action: one of {'pf': 'Play Folder', 'qf': 'Queue Folder', 'pfn': 'Play Folder Next'}
        """
        directory = open_dialog(t('Select Folder'), for_dir=True)
        if directory:
            update_settings('last_folder', directory)
            app_log.info(f'folder_action: action={action}')
            if action in {t('Play'), 'pf'}:
                res = play_uris(directory, natural_sort=False)
            elif action in {t('Play Next'), 'pfn'}:
                res = play_uris(directory, play_next=True, natural_sort=False)
            elif action in {t('Queue'), 'qf'}:
                res = play_uris(directory, queue_uris=True, natural_sort=False)
            else:
                res = False
            if res:
                save_queues()
            elif settings['notifications']:
                tray_notify(t('ERROR') + ': ' + t('Folder does not contain audio files'))

    def get_track_position():
        global track_position
        if playing_status.busy():
            if cast is not None:
                if playing_status.playing():
                    track_position = time.monotonic() - track_start
            else:
                track_position = audio_player.get_pos()
        return track_position

    def pause(source=''):
        """
        Returns true if player was playing
        Returns false if player was not playing
        can be called from a non-main thread
        """
        global track_position, LAST_PLAYED
        app_log.info(f'pause({source}), playing status = {playing_status}')
        if playing_status.playing():
            allow_sleep()
            try:
                if cast is None:
                    track_position = time.monotonic() - track_start
                    if get_current_metadata().get('is_live', False):
                        audio_player.stop()
                    else:
                        audio_player.pause()
                    app_log.info('paused local audio player')
                else:
                    mc = cast.media_controller
                    try:
                        mc.pause()
                    except (RequestTimeout, RequestFailed):
                        try:
                            cast.wait(30)
                            cast.media_controller.pause()
                        except (RequestTimeout, RequestFailed):
                            app_log.exception('failed to pause cast device')
                            return False
                    block_until = time.monotonic() + 5
                    while not mc.status.player_is_paused and time.monotonic() < block_until:
                        time.sleep(0.1)
                    if mc.status.adjusted_current_time is not None:
                        track_position = mc.status.adjusted_current_time
                    app_log.info('paused cast device')
                playing_status.pause()
                if music_queue or sar.alive:
                    metadata = get_current_metadata()
                    title, artist = metadata['title'], metadata['artist']
                    DiscordPresence.update(t('By') + f': {artist}', title, 'Paused', confirm_connect=settings['discord_rpc'])
            except UnsupportedNamespace:
                stop('pause')
            refresh_tray()
            LAST_PLAYED = time.time()
            return True
        return False


    def resume(source=''):
        global track_end, track_position, track_start
        app_log.info(f'resume(source = {source}), playing status = {playing_status}')
        if playing_status.paused():
            if music_queue and not os.path.exists(music_queue[0]) and url_expired(music_queue[0]):
                app_log.info('url expired, hard playing')
                # check if the url has expired before resuming in case it has been a long time
                play(position=track_position, autoplay=False)
            try:
                if cast is None:
                    if get_current_metadata().get('is_live', False):
                        play()
                    else:
                        audio_player.resume()
                        app_log.info('resumed local audio player')
                else:
                    mc = cast.media_controller
                    mc.update_status()
                    mc.play()
                    mc.block_until_active(WAIT_TIMEOUT)
                    if mc.status.adjusted_current_time is not None:
                        track_position = mc.status.adjusted_current_time
                track_start = time.monotonic() - track_position
                if track_length is not None:
                    track_end = track_start + track_length
                playing_status.play()
                metadata = get_current_metadata()
                title, artist = metadata['title'], get_first_artist(metadata['artist'])
                DiscordPresence.update(t('By') + f': {artist}',title, t('Listening'), confirm_connect=settings['discord_rpc'])
                prevent_sleep()
                refresh_tray()
            except (PyChromecastError, AssertionError) as e:
                print('error', e)
                if music_queue:
                    return play(position=track_position)
            return True
        return False


    def stop(stopped_from: str, stop_cast=True):
        """
        can be called from a non-main thread
        does not check if playing_status is busy
        """
        global track_start, track_end, track_position, track_length, playing_url
        app_log.info(f'stopped from {stopped_from}, stop_cast={stop_cast}')
        # allow the system to go to sleep
        # system_media_controls.set_stopped()
        allow_sleep()
        playing_status.stop()
        sar.alive = playing_url = False
        DiscordPresence.clear(settings['discord_rpc'])
        if cast is None:
            audio_player.stop()
        elif cast.app_id == APP_MEDIA_RECEIVER and stop_cast:
            mc = cast.media_controller
            with suppress(PyChromecastError):
                mc.stop()
                block_until = time.monotonic() + 5  # 5 seconds
                status = mc.status
                while (
                    status.player_is_playing or status.player_is_paused
                ) and time.monotonic() > block_until:
                    time.sleep(0.1)
                if status.player_is_playing or status.player_is_paused:
                    try:
                        cast.quit_app(30)
                    except PyChromecastError as e:
                        app_log.exception('cast.quit_app failed')
                        handle_exception(e)
        track_start = track_position = track_end = track_length = 0
        refresh_tray()


    def set_pos(new_position: int):
        """
        AKA: seeking
        sets position of audio player or cast to new_position
        """
        global track_position, track_start, track_end, SYNC_WITH_CHROMECAST
        app_log.info('acquiring CAST_LOCK')
        with CAST_LOCK:
            t1 = time.time()
            app_log.info('trying to set playback position')
            if cast is not None:
                SYNC_WITH_CHROMECAST = time.time() + 1
                try:
                    pass
                    # cast.media_controller.update_status()
                except (PyChromecastError, AssertionError):
                    #   File "C:\Users\maste\Documents\GitHub\music-caster\.venv\Lib\site-packages\pychromecast\socket_client.py", line 891, in send_message
                    #     assert self.socket is not None
                    # AssertionError
                    app_log.info('trying to wait on cast')
                    cast.wait(WAIT_TIMEOUT)
                    app_log.info(f'cast.wait took {time.time() - t1:.2f} seconds')
                if cast.media_controller.status.player_is_idle and music_queue:
                    app_log.info('called play instead')
                    return play(position=new_position, autoplay=playing_status.playing(), from_set_pos=True)
                else:
                    for _ in range(2):
                        try:
                            # seek is unstable. use play instead
                            app_log.info('call play with new position')
                            return play(position=new_position, autoplay=playing_status.playing(), from_set_pos=True)
                            # cast.media_controller.seek(new_position)
                            if playing_status.paused():
                                cast.media_controller.pause()
                            break
                        except (RequestFailed, RequestTimeout) as e:
                            app_log.exception('seek "failed"')
                            if not IS_FROZEN or is_debug():
                                print(f'encountered error while seeking: {type(e)} {e}')
                            # seeking is broken, prefer play instead
                            return play(position=new_position, autoplay=playing_status.playing(), from_set_pos=True)
                            break
                        except (NotConnected):
                            app_log.exception('seek failed')
                            cast.wait(WAIT_TIMEOUT)
                SYNC_WITH_CHROMECAST = time.time() + 0.5
            else:
                audio_player.set_pos(new_position)
            track_position = new_position
            track_start = time.monotonic() - track_position
            track_end = track_start + track_length


    def next_track(from_timeout=False, times=1, forced=False, ignore_timestamps=False):
        """
        :param from_timeout: whether next track is due to the currently playing audio ending
        :param times: number of tracks ahead
        :param forced: if True, ignore current playing status
        :param ignore_timestamps: whether to ignore timestamps for a track
        :return:
        """
        app_log.info(f'from_timeout={from_timeout}')
        if music_queue:
            app_log.info(f'current track = {Path(music_queue[0]).name}')
        if cast is not None and cast.app_id != APP_MEDIA_RECEIVER and cast.app_id is not None and not forced:
            # clicked next track when connected to cast and the app is not the media receiver app
            if cast is None:
                app_log.info('stopping internal playing_status because cast is None')
            if cast.app_id != APP_MEDIA_RECEIVER and not forced:
                app_log.info(f'stopping internal playing_status because cast present app id ({cast.app_id}) does not equal to APP_MEDIA_RECEIVER ({APP_MEDIA_RECEIVER})')
            playing_status.stop()
        elif (next_queue or music_queue) and (forced or playing_status.busy() and not sar.alive):
            # 1. there is something to play next
            # 2. we are already playing a track (or are forcing)
            with suppress(IndexError):
                if track_length is not None and track_length > 600 and not ignore_timestamps:
                    if url_metadata.get(music_queue[0], {}).get('timestamps'):
                        # smart next track if playing a long URL with multiple tracks
                        timestamps = url_metadata[music_queue[0]]['timestamps']
                        new_position = next(filter(lambda seconds: seconds > get_track_position(), timestamps), 0)
                        if new_position:
                            return set_pos(new_position)
            # keep track of skips (used by smart queue feature)
            if music_queue and track_position < 5 and not from_timeout and playing_status.busy() and not forced:
                settings['skips'][music_queue[0]] = settings['skips'].get(music_queue[0], 0) + 1
                # save queue...
                save_settings()
            # if repeat all or repeat is off or empty queue or manual next
            if settings['repeat'] in {False, None} or not music_queue or not from_timeout:
                if settings['repeat']:
                    update_settings('repeat', False)
                app_log.info(f'will move the next {times} tracks from music_queue and then next_queue into the done queue')
                for _ in range(times):
                    if music_queue:
                        done_queue.append(music_queue.popleft())
                    if next_queue:
                        music_queue.appendleft(next_queue.popleft())
                    # if queue is empty but repeat is all AND there are tracks in the done_queue
                    # move tracks from done_queue to music_queue
                    if not music_queue and settings['repeat'] is False and done_queue:
                        music_queue.extend(done_queue)
                        done_queue.clear()
            if music_queue:
                if settings['smart_queue'] and from_timeout:
                    # in the rare case all tracks will be skipped, avoid infinite loop
                    max_skips = len(music_queue) + len(done_queue) + len(next_queue)
                    # auto skip tracks that have been skipped a lot previously
                    while music_queue and settings['skips'].get(music_queue[0], 0) > 5 and max_skips > 0:
                        done_queue.append(music_queue.popleft())
                        if next_queue:
                            music_queue.appendleft(next_queue.popleft())
                        # if queue is empty but repeat is all, move tracks from done_queue to music_queue
                        if not music_queue and settings['repeat'] is False:
                            music_queue.extend(done_queue)
                            done_queue.clear()
                        max_skips -= 1
                elif times > 1:  # reset skip counter because user explicitly selected the track to play
                    settings['skips'].pop(music_queue[0], None)
                    save_settings()
                return play()
            # repeat is off (from timeout) or skip resulted in exhaustion of queue
            stop('next track queue exhaustion', stop_cast=not from_timeout)


    def prev_track(times=1, forced=False, ignore_timestamps=False):
        app_log.info('')
        if not forced and cast is not None and cast.app_id != APP_MEDIA_RECEIVER:
            playing_status.stop()
        elif forced or playing_status.busy() and not sar.alive:
            with suppress(IndexError, TypeError):  # TypeError:  if track_length is None
                timestamps = url_metadata.get(music_queue[0], {}).get('timestamps', [])
                if track_length > 600 and timestamps and not ignore_timestamps:
                    # smart next track if playing a long URL with multiple tracks
                    _track_position = get_track_position()
                    new_position = next(filter(lambda secs: secs < _track_position - 5, reversed(timestamps)), -1)
                    if new_position != -1:
                        return set_pos(new_position)
            if done_queue:
                for _ in range(times):
                    if settings['repeat']:
                        update_settings('repeat', False)
                    track = done_queue.pop()
                    # if there's a next queue, move mq[0] to top of next_queue
                    if music_queue and next_queue:
                        next_queue.appendleft(music_queue.popleft())
                    music_queue.appendleft(track)
            with suppress(IndexError):
                settings['skips'].pop(music_queue[0], None)  # reset skip counter
                play()

    class UpdateChecker(threading.Timer):
        latest_release = None
        latest_version = VERSION
        check_immediately = False

        def __init__(self):
            # check for an update every 30 minutes
            super().__init__(1800, self.check_for_updates)
            self.daemon = True
            if not USING_TAURI_FRONTEND:
                self.start()

        def run(self):
            while not self.finished.wait(self.interval):
                self.function(*self.args, **self.kwargs)

        def check_for_updates(self):
            if USING_TAURI_FRONTEND:
                return
            # avoid showing a notification for the same latest version
            release = get_latest_release(self.latest_version, VERSION)
            if release:
                self.latest_release = release
                self.latest_version = release['version']
                State.update_available = True
                if settings['notifications']:
                    tray_notify('update_available', context=self.latest_version)

        def auto_update(self, install_update=True, from_gui=False):
            """ auto_start should be True when checking for updates at startup up,
                false when checking for updates before exiting """
            if USING_TAURI_FRONTEND:
                return
            app_log.info('IS_FROZEN=%s, install_update=%s, from_gui=%s', IS_FROZEN, install_update, from_gui)
            try:
                State.installing_update = True
                release = self.latest_release
                if release is None:
                    # since the Linux version is script, we want to force only in debug
                    release = get_latest_release(VERSION, VERSION, force=is_debug())
                if not release:
                    raise NoUpdateFound
                State.update_available = True
                if not install_update:
                    State.installing_update = False
                    return release
                latest_ver = release['version']
                setup_dl_link = release['setup']
                installer_dl_link = release['msi']
                has_portable = release['portable']
                download_link = installer_dl_link or setup_dl_link
                app_log.info(f'Update found: v{latest_ver}')
                print('Installer Link:', download_link)
                if is_debug() or not download_link:
                    app_log.info('not updating because; DEBUG=%s, setup=%s, installer_dl_link=%s, download_link=%s', DEBUG, setup_dl_link, installer_dl_link, download_link)
                    State.update_available = False
                    raise NoUpdateFound
                if IS_FROZEN:
                    if platform.system() in {'Linux', 'Darwin'}:
                        tray_notify('update_available', context=latest_ver)
                    elif os.path.exists(UNINSTALLER):
                        download_update = t('Downloading update $VER').replace('$VER', latest_ver)
                        if latest_ver.startswith('5'):
                            # legacy (pre-v6) Inno Setup installer flow
                            installer_path = get_installer_path()
                            # only show message on startup to not confuse the user
                            cmd = [installer_path, '/VERYSILENT', '/FORCECLOSEAPPLICATIONS',
                                    '/MERGETASKS="!desktopicon"', '&&', 'Music Caster.exe']
                            if not from_gui:
                                cmd.extend(
                                    filter(
                                        lambda arg: arg not in {'-m', '--minimized'},
                                        sys.argv[1:],
                                    )
                                )
                            tray_notify(download_update)
                            tray_process_queue.put({'tooltip': download_update})
                            try:
                                # download setup, close tray, run setup, and exit
                                download(setup_dl_link, installer_path)
                                tray_notify(t('Downloaded $VER. Relaunching...').replace('$VER', latest_ver))
                                time.sleep(0.3)
                                Popen(cmd, shell=True)
                                daemon_commands.put('__EXIT__')  # tell main thread to exit
                            except OSError as e:
                                if e.errno == errno.ENOSPC:
                                    tray_notify(t('ERROR') + ': ' + t('No space left on device to auto-update'))
                            except Exception:
                                tray_notify('update_available', context=latest_ver)
                        else:
                            installer_path = get_installer_path(extension='msi' if 'msi' in release else 'exe')
                            tray_notify(download_update)
                            tray_process_queue.put({'tooltip': download_update})
                            try:
                                download(installer_dl_link, installer_path)
                                tray_notify(t('Downloaded $VER. Relaunching...').replace('$VER', latest_ver))
                                time.sleep(0.3)
                                p_installer = Path(installer_path)
                                install_cmd =  f'msiexec /i "{installer_path}"' if p_installer.stem == 'msi' else f'"{installer_path}'
                                Popen(f'"{UNINSTALLER}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART && {install_cmd}', shell=True)
                                daemon_commands.put('__EXIT__')  # tell main thread to exit
                            except OSError as e:
                                if e.errno == errno.ENOSPC:
                                    tray_notify(t('ERROR') + ': ' + t('No space left on device to auto-update'))
                            except Exception:
                                tray_notify('update_available', context=latest_ver)
                    elif os.path.exists('Updater.exe'):
                        # portable installation
                        if not has_portable:
                            # v6+ has no Portable build; do not run the old Updater.exe
                            # (it would download a Portable.zip that no longer exists)
                            tray_notify(t('The new Music Caster has arrived, however a Portable version is not available'))
                        else:
                            try:
                                startfile('Updater')
                                daemon_commands.put('__EXIT__')  # tell main thread to exit
                            except OSError as e:
                                if e == errno.ECANCELED:
                                    # user cancelled update, don't try auto-updating again
                                    # inform user what we were trying to do though
                                    update_settings('auto_update', False)
                                    tray_notify('update_available', context=latest_ver)
                    else:
                        # unins000.exe or updater.exe was deleted; better to inform user there is an update available
                        tray_notify('update_available', context=latest_ver)
            except (requests.RequestException, NoUpdateFound):
                pass
            except Exception:
                app_log.exception('update check failed')
            State.installing_update = False

    def background_thread():
        """
        Startup tasks:
        - try to auto update
        - sends info
        - creates/removes shortcut
        - starts keyboard listener
        - connect Discord presence
        While True tasks:
        - scans files
        """
        global SYNC_WITH_CHROMECAST

        global track_position, track_start, track_end
        app_log.info('start')

        # check if update needs to be installed
        # check for update and update if no must-run arguments were provided or if the update flag was used
        limited_args = len(sys.argv) == 1 or ['-m'] == sys.argv[1:]
        install_update = (
            limited_args and settings['auto_update'] or args.update
        ) and not args.nupdate
        update_checker.auto_update(install_update=install_update)
        State.installing_update = False
        # Media key / global shortcut handling is now done by the Tauri frontend,
        # which forwards actions to the daemon via the HTTP API (see /action/<command>).
        while True:
            scanned = 0
            while not uris_to_scan.empty():
                file_path = uris_to_scan.get()
                if file_path.startswith('http'):
                    get_url_metadata(file_path)
                else:
                    file_path = Path(file_path).as_posix()
                    with suppress(FileNotFoundError):
                        all_tracks[file_path] = get_metadata_wrapped(file_path)
                uris_to_scan.task_done()
                scanned += 1
                if scanned >= 50:
                    scanned = 0

            if seek_queue and time.time() > SYNC_WITH_CHROMECAST:
                time_to_seek = seek_queue.pop()
                seek_queue.clear()
                set_pos_thread = Thread(target=set_pos, args=(time_to_seek,), name='SetPos', daemon=False)
                set_pos_thread.start()
            time.sleep(0.1)

    # SystemMediaTransportControls.ButtonPressed
    def on_smtc_btn_press(event: SystemMediaTransportControlsButton):
        match event:
            case SystemMediaTransportControlsButton.PLAY:
                print('play')
            case SystemMediaTransportControlsButton.PAUSE:
                print('pause')
            case SystemMediaTransportControlsButton.NEXT:
                print('next')
            case SystemMediaTransportControlsButton.PREVIOUS:
                print('previous')

    def get_window_location():
        if not settings['save_window_positions']:
            return None, None
        if settings['mini_mode']:
            return settings['window_locations'].get('main_mini_mode', (None, None))
        key = 'main_vertical' if settings['vertical_gui'] else 'main'
        w, h = settings['window_locations'].get(key, (None, None))
        if w is None or h is None:
            return None, None
        # clamp window position to the virtual screen spanning all monitors
        if platform.system() == 'Windows':
            from win32api import GetSystemMetrics
            # SM_CXVIRTUALSCREEN / SM_CYVIRTUALSCREEN
            virtual_size = (GetSystemMetrics(78), GetSystemMetrics(79))
        elif platform.system() == 'Linux':
            virtual_size = linux.get_virtual_screen_size()
        else:
            virtual_size = None
        if virtual_size is not None and all(virtual_size):
            w = max(0, min(w, virtual_size[0] - 500))
            h = max(0, min(h, virtual_size[1] - 500))
        return w, h


    def metadata_process_file(file: None | os.PathLike, callback_source):
        if file is None:
            handle_exception(TypeError(f'metadata_process_file recevied file = None. Called from {callback_source}'))
            return False
        if not os.path.isfile(file):
            return False
        try:
            return True
        except InvalidAudioFile:
            return False


    def add_music_folder(folders):
        added_folders = set(music_folders)
        for folder in folders:
            folder = folder.replace('\\', '/')
            if os.path.isdir(folder) and folder not in added_folders:
                music_folders.append(folder)
                added_folders.add(folder)
        refresh_tray()
        save_settings()
        if settings['scan_folders']:
            index_all_tracks()


    def uri_at_idx(idx=0, offset=None):
        # converts listbox idx to uri
        # raises IndexError
        if idx < len(done_queue):
            uri = done_queue[idx]
        elif idx == len(done_queue):
            uri = music_queue[0]
        elif idx <= len(next_queue) + len(done_queue):
            uri = next_queue[idx - 1 - len(done_queue)]
        else:
            uri = music_queue[idx - len(next_queue) - len(done_queue)]
        return uri

    def locate_uri(selected_track_index=None, uri=None):
        with suppress(IndexError):
            if uri is None:
                if selected_track_index is None:
                    raise IndexError
                uri = uri_at_idx(idx=selected_track_index)
            if uri.startswith('http'):
                if uri in url_metadata:
                    # if source is from playlist...
                    uri = url_metadata[uri].get('pl_src', uri)
                open_in_browser(uri)
                return True
            if os.path.exists(uri):
                if platform.system() == 'Windows':
                    Popen(f'explorer /select,"{fix_path(uri)}"')
                elif platform.system() == 'Linux':
                    # freedesktop FileManager1 selects the file like explorer
                    # /select, and falls back to opening the parent directory
                    linux.show_in_file_manager(uri)
                else:
                    startfile(Path(uri).parent)
                return True
        # tray_notify(gt('ERROR') + ':' + gt('Could not locate URI'))
        return False


    def exit_program(quick_exit=False):
        close_tray()
        # stop any active scanning
        with suppress(NameError, asyncio.TimeoutError, concurrent.futures.TimeoutError):
            cast_browser.stop_discovery()
        with suppress(PyChromecastError):
            if cast is None:
                stop('exit program')
            elif cast is not None and cast.app_id == APP_MEDIA_RECEIVER and playing_status.busy():
                try:
                    cast.quit_app(30)
                except PyChromecastError as e:
                    app_log.exception('could not cast.quit_app')
                    handle_exception(e)
        DiscordPresence.close()
        if settings['persistent_queue'] and not quick_exit:
            save_queues()
            with suppress(RuntimeError):
                save_queue_thread.join()
        try:
            portalocker.unlock(lock_file)
        except Exception as e:
            # TODO: remove if errors are no longer raised
            handle_exception(e)
        sys.exit()


    def playlist_action(playlist_name, action='play'):
        if playlist_name in settings['playlists'] and settings['playlists'][playlist_name]:
            if action == 'next':
                next_queue.extend(get_audio_uris(playlist_name))
            else:  # if action == 'play' or action == 'queue'
                is_play = action == 'play'
                if is_play:
                    done_queue.clear()
                    music_queue.clear()
                shuffle_from = len(music_queue)
                music_queue.extend(get_audio_uris(playlist_name))
                if settings['shuffle']:
                    better_shuffle(music_queue, shuffle_from)
                if music_queue and (is_play or shuffle_from == 0):
                    play()

    def other_tray_actions(_tray_item):
        if _tray_item.startswith('device:'):
            device_uuid = _tray_item[7:]
            with suppress(ValueError):
                change_device(device_uuid)
        elif _tray_item.startswith('PL:'):  # playlist
            playlist_action(_tray_item[3:])
        elif _tray_item == t('Select Folder'):
            folder_action()
        elif _tray_item.startswith('PF:'):  # play folder
            folder_index = int(re.search(r'\d+', _tray_item).group())
            Thread(target=play_uris, name='PlayFolder', daemon=True, args=[[music_folders[folder_index]]]).start()

    def start_on_login_modifications():
        """ Run platform specific implementation of startup modification """
        if platform.system() == 'Windows':
            app_log.info('removing old startup shortcuts')
            rm_old_startup_shortcuts()
            app_log.info('removed old startup shortcuts')
            app_log.info('creating/removing startup registry entry')
            start_on_login_win32(working_dir, settings['run_on_startup'])
            app_log.info('created/removed startup registry entry')
        else:
            print('TODO: start_on_login_modifications not implemented for', platform.system())


    def cast_monitor(sent: bool = True, msg: dict | None = None, is_callback=True):
        global track_position, track_start, track_end, OLD_CAST_VOLUME, OLD_CAST_POS
        if cast is None:
            return
        # assume this code can raise exceptions
        #   since I did remove it from that try-catch block
        try:
            if msg is None and playing_status.busy():
                # block/monitor in background thread
                if is_callback:
                    # avoid recursion error
                    if playing_status.playing():
                        raise NotConnected
                    return
                return cast.media_controller.update_status(callback_function=cast_monitor)
        except AttributeError:
            # don't need to monitor if device switched randomly
            return
        except (NotConnected, UnsupportedNamespace):
            app_log.info(f'cast.media_controller player state: {cast.media_controller.status.player_state}')
            # we might care if not connected
            with suppress(RequestTimeout):
                cast.wait(3)
            return
        except Exception as e:
            handle_exception(e)
            return
        try:
            CAST_LOCK.acquire()
            if cast.app_id == APP_MEDIA_RECEIVER and time.time() > SYNC_WITH_CHROMECAST:
                media_controller = cast.media_controller
                is_stopped = media_controller.status.player_is_idle
                is_live = track_length is None
                if not is_stopped and playing_status.busy():
                    # sync track position with chromecast, also allows scrubbing from external apps
                    with suppress(IndexError):  # music_queue may be mutated
                        buffer = 2 if music_queue[0].startswith('http') else 0.6
                        current_time = media_controller.status.adjusted_current_time
                        if current_time is not None and abs(current_time - OLD_CAST_POS) > buffer:
                            if current_time < OLD_CAST_POS:
                                app_log.info(f'cast.media_controller player state: {media_controller.status.player_state}')
                                app_log.info(f'updating OLD_CAST_POS from {OLD_CAST_POS} to {current_time}')
                            OLD_CAST_POS = current_time
                            # update track position only if out of buffer position
                            if abs(current_time - get_track_position()) > buffer:
                                if current_time < track_position and track_position - current_time > 2:
                                    app_log.info(f'updating track position from {track_position:.2f} to {current_time:.2f}')
                                track_start = time.monotonic() - track_position
                                if track_length is not None:
                                    track_end = track_start + track_length
                if media_controller.status.player_is_paused and playing_status.playing():
                    pause('cast_monitor')
                elif media_controller.status.player_is_playing and playing_status.paused():
                    resume('cast_monitor')
                elif (is_stopped and playing_status.busy() and not is_live and time.monotonic() - track_end > 1):
                    # if cast says nothing is playing, only stop if we are not at the end of the track
                    #  this will prevent false positives
                    stop('cast_monitor', False)
                if cast.status is not None:
                    cast_volume = round(cast.status.volume_level * 100, 1)
                    # volume sync
                    if settings['volume'] != cast_volume:
                        if not settings['muted'] and (not isinstance(settings['volume'], (float, int)) or
                                                        abs(settings['volume'] - cast_volume) > 0.05):
                            # if volume was changed via Google Home App
                            OLD_CAST_VOLUME = cast_volume
                            if update_settings('volume', cast_volume) and settings['muted']:
                                update_settings('muted', False)
            elif playing_status.playing() and cast.media_controller.status.player_is_idle and time.time() - LAST_PLAYED > 300:
                # paused for more than 5 minutes
                stop('cast_monitor. app was not running')
        except (NotConnected, AttributeError):  # don't care
            pass
        except UnsupportedNamespace:  # known error
            # File "pychromecast/controllers/media.py", line 359, in update_status
            # File "pychromecast/controllers/init.py", line 91, in send_message
            # pychromecast.error.UnsupportedNamespace:
            #  Namespace urn:x-cast:com.google.cast.media is not supported by running application.
            pass
        except Exception as e:
            handle_exception(e)
        finally:
            with suppress(RuntimeError):
                CAST_LOCK.release()


    def handle_action(action):
        actions = {
            '__EXIT__': exit_program,
            # from tray menu
            t('Exit'): exit_program,
            t('Rescan Library'): index_all_tracks,
            t('Refresh Devices'): lambda: refresh_tray(True),
            # isdigit should be an if statement
            # PL should be an if statement
            t('Cancel Timer'): cancel_timer,
            t('System Audio'): play_system_audio,
            t('Play Files'): file_action,
            t('Queue Files'): lambda: file_action('qf'),
            t('Play Files Next'): lambda: file_action('pfn'),
            t('Play All'): play_all,
            t('Pause'): pause,
            t('Resume'): resume,
            t('next track', 1): next_track,
            t('previous track', 1): prev_track,
            t('Stop'): lambda: stop('tray'),
            t('Repeat One'): lambda: update_settings('repeat', True),
            t('Repeat All'): lambda: update_settings('repeat', False),
            t('Repeat Off'): lambda: update_settings('repeat', None),
            t('locate track', 1): locate_uri
        }
        actions.get(action, lambda: other_tray_actions(action))()
    update_checker = UpdateChecker()
    try:
        start_time = time.monotonic()
        load_settings(True)  # starts indexing all tracks
        if settings['important_message'] != IMPORTANT_INFORMATION and IMPORTANT_INFORMATION:
            two_lined_info = []
            for line in IMPORTANT_INFORMATION.splitlines(keepends=True):
                two_lined_info.append(line)
                if len(two_lined_info) == 2:
                    tray_notify(''.join(two_lined_info), title='Music Caster - Important Information')
                    two_lined_info.clear()
            tray_notify(''.join(two_lined_info), title='Music Caster - Important Information')
            update_settings('important_message', IMPORTANT_INFORMATION)
        if settings['update_message'] == '':
            tray_notify(WELCOME_MSG)
        elif settings['update_message'] != UPDATE_MESSAGE and settings['notifications']:
            tray_notify(UPDATE_MESSAGE)
        # show important information regardless of notification settings
        update_settings('update_message', UPDATE_MESSAGE)

        # file type and URL protocol handlers are registered by the Tauri installer

        # remove any existing installer file we might've already run (exe and msi variants)
        for _installer in (get_installer_path(), get_installer_path(extension='msi')):
            with suppress(FileNotFoundError, OSError):
                os.remove(_installer)

        rmtree('Update', ignore_errors=True)
        Thread(target=background_thread, daemon=True, name='BackgroundTasks').start()
        zconf = zeroconf.Zeroconf()
        cast_browser = pychromecast.discovery.CastBrowser(MyCastListener(), zconf)
        cast_browser.start_discovery()
        try:
            audio_player = AudioPlayer()
        except Exception as exception:
            tray_notify(t('WARNING: Failed to start audio player. Do not play on local device.'))
            handle_exception(exception)
        # system_media_controls = SystemMediaControls(on_smtc_btn_press)
        # find a port that we can actually bind to
        # Linux auto-maps ipv4 to ipv6 however Windows keeps them separate
        bind_tests = [(socket.AF_INET6, '::')]
        if platform.system() == 'Windows':
            bind_tests.append((socket.AF_INET, '0.0.0.0'))
        while State.PORT <= 65535:
            # a connection check is not enough: the bind itself can fail (e.g.
            # WinError 10013 when the port is in a reserved port range), and waitress
            # binds inside its own thread where we cannot catch the error, so verify
            # that binding works here before starting the server
            test_sockets = []
            try:
                for family, host in bind_tests:
                    s = socket.socket(family, socket.SOCK_STREAM)
                    test_sockets.append(s)
                    # mimic the socket options waitress uses
                    if family == socket.AF_INET6:
                        with suppress(AttributeError, OSError):
                            s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                    with suppress(OSError):
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.bind((host, State.PORT))
            except OSError:
                State.PORT += 1  # port in use or binding not permitted, try the next one
            else:
                break
            finally:
                for s in test_sockets:
                    s.close()
        else:
            raise OSError('Could not find a port to bind the server to')
        # start the server on the verified port
        if platform.system() == 'Windows':
            server_kwargs = {'host': '0.0.0.0', 'port': State.PORT}
            Thread(target=waitress.serve, name='WaitressServe', daemon=True, args=(app,), kwargs=server_kwargs).start()
        server_kwargs = {'host': '::', 'port': State.PORT}
        Thread(target=waitress.serve, name='WaitressServe', daemon=True, args=(app,), kwargs=server_kwargs).start()
        with suppress(PermissionError):
            if is_debug:
                # only want to store PID of original instance
                lock_file.read()
            create_pid_file(port=State.PORT)
        if not USING_TAURI_FRONTEND:
            tray_process = mp.Process(target=system_tray, name='Music Caster Tray',
                                      args=(daemon_commands, tray_process_queue), daemon=True)
            tray_process.start()
        api_key = settings['api_key']
        print(f'Running on http://127.0.0.1:{State.PORT}/?api_key={api_key}')
        print(f'Running on http://[::1]:{State.PORT}/?api_key={api_key}')
        app_log.info(f'LAN IPV4: {get_ipv4()}:{State.PORT}/')
        try:
            app_log.info(f'LAN IPV6: {get_ipv6()}:{State.PORT}/')
        except StopIteration:
            app_log.info('Could not get LAN IPV6 address')
        DiscordPresence.connect(settings['discord_rpc'])
        if PHANTOMJS_DIR.is_dir() and not cmd_exists('phantomjs'):
            add_to_path(PHANTOMJS_DIR / 'bin')
        if args.device is not None:
            end_time = time.monotonic() + WAIT_TIMEOUT
            while not change_device(args.device) and time.monotonic() < end_time:
                time.sleep(0.3)
        if args.uris or args.start_playing:
            # wait until previous device has been found or cannot be found
            end_time = time.monotonic() + WAIT_TIMEOUT
            while not change_device(settings['device']) and time.monotonic() < end_time:
                time.sleep(0.3)
        if args.uris:
            if args.uris[0].lower().replace(' ', '').replace('_', '') == 'systemaudio':
                play_system_audio()
            else:
                play_uris(args.uris, queue_uris=args.queue, play_next=args.playnext)
        elif settings['persistent_queue']:
            # load saved queues from settings.json
            for queue_name in {'done', 'music', 'next'}:
                queue = {'done': done_queue, 'music': music_queue, 'next': next_queue}[queue_name]
                for file_or_url in settings['queues'].get(queue_name, []):
                    if valid_audio_file(file_or_url) or file_or_url.startswith('http'):
                        queue.append(file_or_url)
                        uris_to_scan.put(file_or_url)
            # position = args.position || previous session's position
            track_position = args.position
            if track_position == 0 and settings['position'] > 0:
                track_position = settings['position']
            if args.start_playing:
                if not music_queue:
                    if next_queue:
                        music_queue.append(next_queue.popleft())
                    elif done_queue:
                        music_queue.extend(done_queue)
                        done_queue.clear()
                if music_queue:
                    play(position=track_position, autoplay=not args.queue)
            elif track_position and music_queue:
                # restore position
                play(position=track_position, autoplay=False)
        elif settings['populate_queue_startup'] or args.start_playing:
            try:
                indexing_tracks_thread.join()
                play_all(queue_only=not args.start_playing or args.queue)
            except RuntimeError:
                tray_notify(t('ERROR') + ':' + t('Could not populate queue because library scan is disabled'))
        TIME_TO_START = time.monotonic() - start_time
        app_log.info('--------------------------------')
        app_log.info(f'Music Caster Version: {VERSION}')
        app_log.debug(f'Time to start (excluding imports) is {TIME_TO_START:.2f} seconds')
        app_log.debug(f'Time to start (including imports) is {TIME_TO_START + TIME_TO_IMPORT:.2f} seconds')
        last_position_save = time.monotonic()
        # how often to re-check whether the display mode should follow the power source
        RES_CHECK_INTERVAL = 2
        next_res_check = 0

        # health check
        if is_debug():
            api_key = settings['api_key']
            r = requests.get(f'http://127.0.0.1:{State.PORT}/?api_key={api_key}')
            assert r.ok

        while True:
            while not daemon_commands.empty():
                handle_action(daemon_commands.get())
            if playing_status.playing() and track_length is not None and time.monotonic() > track_end:
                app_log.info('calling next track because monotonic time is greater than track_end')
                next_track(from_timeout=time.monotonic() > track_end)
            elif timer and time.time() > timer:
                stop('timer')
                timer = 0
                # use lock to prevent corrupting settings
                with settings_file_lock:
                    # systemd/logind is the Linux counterpart of shutdown /p /f
                    # and rundll32 powrprof.dll,SetSuspendState
                    if settings['timer_shut_down']:  # shutdown computer
                        if platform.system() == 'Windows':
                            os.system('shutdown /p /f')
                        elif platform.system() == 'Linux':
                            linux.shut_down()
                        else:
                            os.system('shutdown -h now')
                    elif settings['timer_hibernate']:  # hibernate computer
                        if platform.system() == 'Windows':
                            os.system(
                                r'rundll32.exe powrprof.dll,SetSuspendState Hibernate'
                            )
                        elif platform.system() == 'Linux':
                            linux.hibernate()
                    elif settings['timer_sleep']:  # sleep computer
                        if platform.system() == 'Windows':
                            os.system('rundll32.exe powrprof.dll,SetSuspendState 0,1,0')
                        elif platform.system() == 'Linux':
                            linux.sleep_computer()
            # if settings.json was updated outside of Music Caster, reload settings
            try:
                if os.path.getmtime(SETTINGS_FILE) != settings_last_modified:
                    load_settings()
            except FileNotFoundError:
                load_settings(first_load=True)
            if settings['persistent_queue'] and time.monotonic() - last_position_save > 2.5:
                update_settings('position', get_track_position())
                last_position_save = time.monotonic()
            # Linux resolution switching only works under X11 (xrandr); on Wayland
            # get_all_resolutions() is empty and this block is skipped entirely
            if (platform.system() in {'Windows', 'Linux'}
                    and time.monotonic() > next_res_check
                    and None not in (settings['on_battery_res'], settings['plugged_in_res'])):
                # reading the current mode costs an xrandr call on Linux, so poll
                # on a timer rather than on every iteration of this loop
                next_res_check = time.monotonic() + RES_CHECK_INTERVAL
                res_map = get_all_resolutions()
                # an empty map means the platform gives us no mode control
                if res_map and settings['on_battery_res'] != settings['plugged_in_res']:
                    try:
                        current_width = get_current_res()[0]
                        refresh_rate = None
                        if is_plugged_in(throw_error=False):
                            res_info = res_map[fmt_res(*settings['plugged_in_res'])]
                            # check if res differs from desireed res
                            if current_width * res_info['dpi_scale'] != settings['plugged_in_res'][0]:
                                refresh_rate = max(get_all_refresh_rates())
                        else:  # on battery
                            res_info = res_map[fmt_res(*settings['on_battery_res'])]
                            # check if res differs from desireed res
                            if current_width * res_info['dpi_scale'] != settings['on_battery_res'][0]:
                                refresh_rate = 60 if 60 in get_all_refresh_rates() else min(get_all_refresh_rates())
                        # res differs from desired res
                        if refresh_rate is not None:
                            set_resolution(res_info['w'], res_info['h'], res_info['dpi_scale'], refresh_rate=refresh_rate)
                            refresh_tray_icon()
                    except (KeyError, TypeError, ValueError):
                        update_settings('plugged_in_res', get_initial_res())
                        update_settings('on_battery_res', get_initial_res())
                        tray_notify(t('ERROR') + ': ' + t('Could not set resolution'))
            if cast is not None:
                cast_monitor(is_callback=False)
            time.sleep(0.3)
    except KeyboardInterrupt:
        exit_program()
    except Exception as exception:
        app_log.exception('FATAL exception detected')
        # try to auto-update before exiting
        if not settings.get('DEBUG', False):
            update_checker.auto_update()
        handle_exception(exception, True)
