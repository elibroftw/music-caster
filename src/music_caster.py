from meta import *
import time
from resolution_switcher import get_all_refresh_rates, get_initial_res, is_plugged_in
start_time = time.monotonic()
# noinspection PyUnresolvedReferences
from contextlib import suppress
from itertools import islice
# noinspection PyUnresolvedReferences
import io
import multiprocessing as mp
import os
# noinspection PyUnresolvedReferences
import platform
import threading
# noinspection PyUnresolvedReferences
from subprocess import Popen, PIPE, DEVNULL
# noinspection PyUnresolvedReferences
import re
import sys


def get_running_processes(look_for='', pid=None, add_exe=True):
    if platform.system() == 'Windows':
        cmd = f'tasklist /NH'
        if look_for:
            if not look_for.endswith('.exe') and add_exe:
                look_for += '.exe'
            cmd += f' /FI "IMAGENAME eq {look_for}"'
        if pid is not None:
            cmd += f' /FI "PID eq {pid}"'
        p = Popen(cmd, shell=True, stdout=PIPE, stdin=DEVNULL, stderr=DEVNULL, text=True, encoding='iso8859-2')
        p.stdout.readline()
        for task in iter(lambda: p.stdout.readline().strip(), ''):
            m = re.match(r'(.+?) +(\d+) (.+?) +(\d+) +(\d+.* K).*', task)
            if m is not None:
                yield {'name': m.group(1), 'pid': int(m.group(2)), 'session_name': m.group(3),
                       'session_num': m.group(4), 'mem_usage': m.group(5)}
    elif platform.system() == 'Linux':
        cmd = ['ps', 'h']
        if look_for:
            cmd.extend(('-C', look_for))
        p = Popen(cmd, stdout=PIPE, stdin=PIPE, stderr=DEVNULL, text=True)
        for task in iter(lambda: p.stdout.readline().strip(), ''):
            m = task.split(maxsplit=4)
            yield {'name': m[-1], 'pid': int(m[0])}


def is_already_running(look_for='Music Caster', threshold=1, pid=None) -> bool:
    """
    Returns True if more processes than `threshold` were found
    # TODO: threshold feature for Linux
    """
    if platform.system() == 'Windows':
        for _ in get_running_processes(look_for=look_for, pid=pid):
            threshold -= 1
            if threshold < 0:
                return True
    else:  # Linux
        p = Popen(['ps', 'h', '-C', look_for, '-o', 'comm'], stdout=PIPE, stdin=PIPE, stderr=DEVNULL, text=True)
        return p.stdout.readline().strip() != ''
    return False


def create_pid_file(port=None):
    with open(PID_FILENAME, 'w', encoding='utf-8') as f:
        f.write(str(os.getpid()))
        if port is not None:
            f.write(f'\n{port}')


def parse_pid_file() -> (int, int):
    with suppress(FileNotFoundError):
        with open(PID_FILENAME, encoding='utf-8') as f:
            pid = int(f.readline().strip())
            try:
                port = int(f.readline().strip())
            except ValueError:
                port = 2001
            return pid, port
    return None, 2001


def ensure_single_instance(debugging=False):
    file = open(LOCK_FILENAME, 'w+', encoding='utf-8')
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
                activate_instance(port=port, timeout=5)
                sys.exit()
        else:
            print('instance not found, lock broken?', repr(e))
    return file


def system_tray(main_queue: mp.Queue, child_queue: mp.Queue):
    from b64_images import FILLED_ICON, UNFILLED_ICON, b64decode
    if platform.system() == 'Linux':
        os.environ['PYSTRAY_BACKEND'] = 'appindicator'
    import pystray
    from PIL import Image
    filled_icon = Image.open(io.BytesIO(b64decode(FILLED_ICON)))
    unfilled_icon = Image.open(io.BytesIO(b64decode(UNFILLED_ICON)))

    def create_menu(lst, root=True):
        # e.g. ['Item 1', ('Item 2 Display', 'item_2_key'), ['Sub Menu Title', ('Sub Menu Item 1 Display', 'KEY')]]
        items = []
        if root: items.append(pystray.MenuItem('', get_tray_action('__ACTIVATED__'), default=True, visible=False))
        for element in lst:
            if type(element) == list:
                items.append(pystray.MenuItem(element[0], create_menu(islice(element, 1, None), root=False)))
            elif type(element) == tuple and len(element) == 2:
                element, key = element
                items.append(pystray.MenuItem(element, get_tray_action(element, key)))
            else:
                items.append(pystray.MenuItem(element, get_tray_action(element)))
        return pystray.Menu(*items)

    def get_tray_action(string, key=''):

        def tray_action():
            try:
                main_queue.put(key) if key else main_queue.put(string)
                if key == '__EXIT__':
                    child_queue.put({'close': None})
            except ValueError:
                child_queue.put({'close': None})

        return tray_action

    def background():
        while True:
            while not child_queue.empty():
                for parent_cmd, arguments in child_queue.get().items():
                    if parent_cmd == 'tooltip':
                        tray.title = arguments
                    elif parent_cmd == 'menu':  # set icon to unfilled
                        if tray.HAS_MENU:
                            tray.menu = create_menu(arguments)
                            tray.update_menu()
                        else:
                            print('pystray: menu not supported')
                    elif parent_cmd == 'filled':  # set icon to filled
                        tray.icon = filled_icon
                    elif parent_cmd == 'unfilled':  # set icon to unfilled
                        tray.icon = unfilled_icon
                    elif parent_cmd == 'notify':
                        if tray.HAS_NOTIFICATION:
                            tray.notify(arguments['message'], title=arguments.get('title'))  # msg, title
                        else:
                            print('pystray: notify not supported')
                    elif parent_cmd == 'hide':
                        tray.visible = False
                    elif parent_cmd in {'close', 'exit', '__EXIT__'}:
                        tray.stop()
                        sys.exit()
            time.sleep(0.1)

    tray = pystray.Icon('Music Caster SystemTray', unfilled_icon, title='Music Caster [LOADING]')
    threading.Thread(target=background, daemon=True).start()
    tray.run()


if __name__ == '__main__':
    mp.freeze_support()
    import argparse
    from inspect import currentframe
    from pathlib import Path
    from urllib.request import pathname2url, urlopen, Request
    from urllib.parse import urlencode
    from urllib.error import URLError

    import portalocker
    from portalocker.exceptions import LockException

    parser = argparse.ArgumentParser(description='Music Caster')
    parser.add_argument('--debug', '-d', default=False, action='store_true', help='allows > 1 instance + no info sent')
    parser.add_argument('--start-playing', default=False, action='store_true', help='resume or shuffle play all')
    parser.add_argument('--queue', '-q', default=False, action='store_true', help='uris are queued not played')
    parser.add_argument('--playnext', '-n', default=False, action='store_true', help='paths are added to next up')
    parser.add_argument('--urlprotocol', '-p', default=False, action='store_true', help='launched using uri protocol')
    parser.add_argument('--update', '-u', default=False, action='store_true', help='update MC even if --args provided')
    parser.add_argument('--nupdate', default=False, action='store_true', help='start without auto-update')
    parser.add_argument('--exit', '-x', default=False, action='store_true',
                        help='exits any existing instance (including self)')
    parser.add_argument('--minimized', '-m', default=False, action='store_true', help='start minimized to tray')
    parser.add_argument('--version', '-v', default=False, action='store_true', help='returns the version')
    parser.add_argument('uris', nargs='*', default=[], help='list of files/dirs/playlists/urls to play/queue')
    parser.add_argument('--position', default=0, help='position to start at if resume_playing')
    parser.add_argument('--shell', default=False, action='store_true', help='if from shell/explorer')
    parser.add_argument('--device', action='store', help='device to use', default=None)
    # freeze_support() adds the following
    parser.add_argument('--multiprocessing-fork', default=False, action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    # if from url protocol, re-parse arguments
    if args.urlprotocol:
        new_args = args.uris[0].replace('music-caster://', '', 1).replace('music-caster:', '')
        if new_args: new_args = new_args.split(';')
        args = parser.parse_args(new_args)
    if args.version:
        print(VERSION)
        sys.exit()
    DEBUG = args.debug
    IS_FROZEN = getattr(sys, 'frozen', False)
    working_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    os.chdir(working_dir)


    def activate_instance(port=2001, timeout=0.5, to_port=2004):
        # by default activates if running already
        r, local_ipv6, local_ipv4 = '', 'http://[::1]:', 'http://127.0.0.1:'
        while port < to_port and r == '':
            for localhost in (local_ipv4, local_ipv6):
                with suppress(URLError):
                    if args.exit:  # --exit argument
                        r = urlopen(Request(f'{localhost}{port}/exit/', method='POST'), timeout=timeout).read()
                    elif args.uris:  # MC was supplied at least one path to a folder/file
                        data = {'uris': args.uris, 'queue': args.queue, 'play_next': args.playnext}
                        data = urlencode(data, doseq=True).encode()
                        r = urlopen(Request(f'{localhost}{port}/play/', data=data), timeout=timeout + 0.5).read()
                    else:  # neither --exit nor paths was supplied
                        r = urlopen(Request(f'{localhost}{port}/?activate', method='POST'), timeout=timeout).read()
                if r:
                    return True
            port += 1
        return False

    lock_file = ensure_single_instance(debugging=DEBUG)
    daemon_commands, tray_process_queue = mp.Queue(), mp.Queue()
    auto_updating = True

    if args.exit: sys.exit()
    from collections import deque
    from collections.abc import Iterable
    # noinspection PyUnresolvedReferences
    import encodings.idna  # DO NOT REMOVE
    from functools import cmp_to_key
    import hashlib
    from copy import deepcopy
    from datetime import datetime, timedelta
    import errno
    from logging.handlers import RotatingFileHandler
    from math import log10
    import pprint
    from random import shuffle
    from shutil import copyfileobj, rmtree
    from queue import Queue
    import tkinter
    from tkinter import filedialog as fd
    from tkinter import TclError
    import traceback
    import urllib.parse
    from urllib.parse import urlsplit
    from uuid import UUID
    import webbrowser
    import zipfile

    from audio_player import AudioPlayer
    from helpers import *
    from resolution_switcher import set_resolution

    # 3rd party imports take 0.22 seconds to import
    # flask takes 0.14 seconds
    from flask import Flask, jsonify, render_template, request, redirect, send_file, Response, make_response
    from jinja2.exceptions import TemplateNotFound
    from werkzeug.exceptions import InternalServerError
    from PIL import Image
    import pychromecast.controllers.media
    from pychromecast.error import PyChromecastError, UnsupportedNamespace, NotConnected
    from pychromecast.config import APP_MEDIA_RECEIVER
    from pychromecast import Chromecast
    from pychromecast.models import CastInfo
    import pyperclip
    import requests
    import scrapetube
    try:
        from TkinterDnD2 import DND_FILES, DND_ALL
    except ImportError:
        # what about tkinterdnd2
        import tkinterDnD
    import ujson as json
    import zeroconf
    TIME_TO_IMPORT = time.monotonic() - start_time

    # LOGS
    log_format = logging.Formatter('%(asctime)s %(levelname)s (%(lineno)d): %(message)s')
    log_handler = RotatingFileHandler('music_caster.log', maxBytes=5242880, backupCount=1, encoding='UTF-8')
    log_handler.setFormatter(log_format)
    app_log = logging.getLogger('music_caster')
    app_log.propagate = False  # disable console output
    app_log.setLevel(logging.INFO)
    app_log.addHandler(log_handler)
    logging.getLogger('pychromecast.socket_client').addHandler(log_handler)
    logging.getLogger('pychromecast').addHandler(log_handler)
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    logging.getLogger('werkzeug').addHandler(log_handler)
    app_log.info(f'Time to import is {TIME_TO_IMPORT:.2f} seconds')

    gui_window = Sg.Window('', metadata={})
    gui_window.close()

    WELCOME_MSG = t('Thanks for installing Music Caster.') + '\n' + t('Music Caster is running in the tray.')
    uris_to_scan = Queue()
    SETTINGS_FILE = Path('settings.json').absolute()
    PRESSED_KEYS = set()
    settings_file_lock = threading.Lock()
    last_play_command = settings_last_modified = 0
    update_last_checked = time.time()  # check every hour
    # noinspection PyTypeChecker
    cast: Chromecast = None
    all_tracks, url_metadata, all_tracks_sorted = {}, {}, []
    tray_playlists = [t('Playlists Tab')]
    CHECK_MARK = '✓'
    music_folders, device_names = [], [(f'{CHECK_MARK} ' + t('Local device'), 'device:0')]
    music_queue, done_queue, next_queue = deque(), deque(), deque()
    playing_url = deezer_opened = False
    recent_api_plays = {'play': 0, 'queue': 0, 'play_next': 0}
    # seconds but using time()
    track_position = timer = track_end = track_length = track_start = 0
    DEFAULT_FOLDER = home_music_folder = (Path.home() / 'Music').as_posix()
    default_auto_update = os.path.exists(UNINSTALLER) or os.path.exists('Updater.exe')
    settings: dict = {  # default settings
        'device': None, 'window_locations': {}, 'smart_queue': False, 'skips': {}, 'theme': DEFAULT_THEME.copy(),
        'auto_update': default_auto_update, 'run_on_startup': os.path.exists(UNINSTALLER), 'notifications': True,
        'shuffle': False, 'repeat': None, 'discord_rpc': False, 'save_window_positions': True, 'mini_on_top': True,
        'populate_queue_startup': False, 'persistent_queue': False, 'volume': 20, 'muted': False, 'volume_delta': 5,
        'scrubbing_delta': 5, 'flip_main_window': False, 'show_track_number': False, 'folder_cover_override': False,
        'show_album_art': True, 'folder_context_menu': True, 'vertical_gui': False, 'mini_mode': False,
        'gui_exits_app': False, 'update_check_hours': 1, 'timer_shut_down': False, 'timer_hibernate': False,
        'timer_sleep': False, 'show_queue_index': True, 'queue_library': False, 'lang': '', 'sys_audio_delay': 0,
        'use_last_folder': False, 'upload_pw': '', 'last_folder': DEFAULT_FOLDER, 'scan_folders': True,
        'track_format': '&artist - &title', 'reversed_play_next': False, 'update_message': '', 'important_message': '',
        'music_folders': [DEFAULT_FOLDER], 'playlists': {}, 'queues': {'done': [], 'music': [], 'next': []},
        'position': 0, 'plugged_in_res': get_initial_res(), 'on_battery_res': get_initial_res()}
    default_settings = deepcopy(settings)
    indexing_tracks_thread = save_queue_thread = Thread()
    playing_status = PlayingStatus()
    sar = SystemAudioRecorder()
    app = Flask(__name__)
    app.jinja_env.lstrip_blocks = app.jinja_env.trim_blocks = True
    os.environ['WERKZEUG_RUN_MAIN'] = 'true'
    os.environ['FLASK_SKIP_DOTENV'] = '1'
    cast_monitor_lock = threading.Lock()


    def get_line_number():
        cf = currentframe()
        return cf.f_back.f_lineno


    def tray_notify(message, title='Music Caster', context=''):
        """ A wrapper for tray_process_queue.put({ notify: {message: msg, title: title} }) """
        if message == 'update_available':
            message = t('Update $VER is available').replace('$VER', f'v{context}')
        tray_process_queue.put({'notify': {'message': message, 'title': title}})


    def close_tray():
        tray_process_queue.put({'close': None})
        tray_process.join()


    def save_settings():
        global settings_last_modified
        with settings_file_lock:
            try:
                with open(SETTINGS_FILE, 'w', encoding='utf-8') as outfile:
                    json.dump(settings, outfile, indent=2, escape_forward_slashes=False)
                settings_last_modified = os.path.getmtime(SETTINGS_FILE)
            except OSError as e:
                if e.errno == errno.ENOSPC:
                    tray_notify(t('ERROR') + ': ' + t('No space left on device to save settings'))
                else:
                    tray_notify(t('ERROR') + f': {e}')


    def is_debug():
        return settings.get('DEBUG', DEBUG)


    def refresh_tray(refresh_devices=False):
        if refresh_devices:
            device_names.clear()
            # account for case where user is connected to device not detectable
            if cast is not None and cast.uuid not in cast_browser.devices:
                cast_browser.devices[cast.uuid] = cast.cast_info
            for device in get_devices():
                device_names.append(device.as_tray_item(settings['device']))
            daemon_commands.put('__UPDATE_GUI__')
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
        if platform.system() == 'Linux':
            # more so for applicationindicator
            for menu in tray_menu_default, tray_menu_paused, tray_menu_playing:
                menu.append((t('Open'), '__ACTIVATED__'))
        # refresh playlists
        tray_playlists.clear()
        tray_playlists.append(t('Playlists Tab'))
        tray_playlists.extend([(f'{pl}'.replace('&', '&&&'), f'PL:{pl}') for pl in settings['playlists']])
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
        if is_debug(): _tooltip += ' [DEBUG]'
        tray_process_queue.put({'menu': menu, 'tooltip': _tooltip, **icon})


    def refresh_tray_icon():
        icon = {'filled': None} if playing_status.playing() else {'unfilled': None}
        tray_process_queue.put(icon)


    def update_settings(settings_key, new_value):
        """ can be called from non-main thread """
        if settings[settings_key] != new_value:
            settings[settings_key] = new_value
            save_settings()
            if settings_key == 'repeat':
                daemon_commands.put('__UPDATE_GUI__')
                refresh_tray()
            elif settings_key == 'shuffle':
                if not gui_window.was_closed(): daemon_commands.put('__UPDATE_GUI__')
                shuffle_queue() if new_value else un_shuffle_queue()
        return new_value


    def save_queues():
        global save_queue_thread

        def _save_queue():
            settings['queues']['done'] = tuple(done_queue)
            settings['queues']['music'] = tuple(music_queue)
            settings['queues']['next'] = tuple(next_queue)
            save_settings()

        if settings['persistent_queue'] and not save_queue_thread.is_alive() and not auto_updating:
            save_queue_thread = Thread(target=_save_queue, name='SaveQueue')
            save_queue_thread.start()


    def update_volume(new_vol, _from=''):
        """new_vol: float[0, 100]"""
        app_log.info(f'update_volume: {new_vol} {_from}')
        gui_window.metadata['update_volume_slider'] = True
        if not isinstance(new_vol, (float, int)):
            new_vol = update_settings('volume', 20)
        new_vol = new_vol / 100
        with suppress(NameError):
            audio_player.set_volume(new_vol)
        if cast is not None:
            with suppress(NotConnected): cast.set_volume(new_vol)


    def cycle_repeat():
        """ :return: new repeat value """
        # Repeat Off (None) becomes All (False) becomes One (True) becomes Off
        new_repeat_setting = {None: False, True: None, False: True}[settings['repeat']]
        return update_settings('repeat', new_repeat_setting)


    def create_email_url():
        try:
            with open('music_caster.log', encoding='utf-8') as f:
                log_lines = f.read().splitlines()[-10:]  # get last 10 lines of the log
        except FileNotFoundError:
            log_lines = []
        log_lines = '%0D%0A'.join(log_lines)
        email_body = f'body=%0D%0A%23%20Tail%20of%20Log%0D%0A%0D%0A{log_lines}'
        mail_to = f'mailto:{EMAIL}?subject=Regarding%20Music%20Caster%20v{VERSION}&{email_body}'
        return mail_to


    def handle_exception(e: Exception, restart_program=False) -> False:
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
            with open('music_caster.log', encoding='utf-8') as f:
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
                requests.post('https://dc19f29a6822522162e00f0b4bee7632.m.pipedream.net', json=payload, timeout=0.5)
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
            with suppress(Exception): stop('error handling')
            tray_notify(t('An error occurred, restarting now'))
            # minimized = main_window.was_closed()
            if IS_FROZEN: startfile('Music Caster')
            else: raise e  # raise exception if running in script rather than executable
            sys.exit()
        return False

    def get_current_art():
        if sar.alive: return custom_art('SYS')
        if playing_status.busy() and music_queue:
            uri = music_queue[0]
            if uri.startswith('http'):
                if url_metadata.get(uri, {}).get('art') in ('None', None): return custom_art('URL')
                if 'art_data' in url_metadata[uri]: return url_metadata[uri]['art_data']
                # use 'art_data' else download 'art' link and cache to 'art_data'
                url_metadata[uri]['art_data'] = base64.b64encode(requests.get(url_metadata[uri]['art']).content)
                return url_metadata[uri]['art_data']
            return get_album_art(uri, settings['folder_cover_override'])[1]
        return DEFAULT_ART


    def get_metadata_wrapped(file_path: str) -> dict:  # keys: title, artist, album, sort_key
        try:
            if file_path.startswith('http'):
                raise ValueError('expected file not http...')
            m = get_metadata(file_path)
            return m
        except (mutagen.MutagenError, ValueError):
            try:
                return all_tracks[Path(file_path).as_posix()]
            except KeyError:
                return {'title': Unknown('Title'), 'artist': Unknown('Artist'), 'explicit': False,
                        'album': Unknown('Title'), 'sort_key': get_file_name(file_path), 'track_number': '1'}


    def get_uri_metadata(uri, read_file=True):
        """ Uses cache to get metadata """
        # raises KeyError
        uri = uri.replace('\\', '/')
        if uri.startswith('http'):
            if uri in url_metadata:
                return url_metadata[uri]
            return {'title': Unknown('Title'), 'artist': Unknown('Artist'), 'explicit': False,
                    'album': Unknown('Album'), 'sort_key': uri, 'track_number': '1'}
        if uri in all_tracks:
            return all_tracks[uri]
        # uri is probably a file that has not been cached yet
        if read_file:
            metadata = get_metadata_wrapped(uri)
            all_tracks[uri] = metadata
            return metadata
        raise KeyError


    def get_current_metadata() -> dict:
        if sar.alive: return url_metadata['SYSTEM_AUDIO']
        if music_queue and playing_status.busy(): return get_uri_metadata(music_queue[0])
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
        if parsed_m3us is None: parsed_m3us = set()
        if isinstance(uris, str): uris = (uris,)
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
                uri = uri.replace('\\', '/')
                if not ignore_m3u and (uri.endswith('.m3u') or uri.endswith('.m3u8')) and uri not in parsed_m3us:
                    parsed_m3us.add(uri)
                    yield from get_audio_uris(parse_m3u(uri), parsed_m3us=parsed_m3us)
                elif valid_audio_file(uri):
                    if scan_uris and uri not in all_tracks: uris_to_scan.put(uri)
                    yield uri
            elif uri.startswith('http'):
                if scan_uris and uri not in url_metadata: uris_to_scan.put(uri)
                yield uri


    def index_all_tracks(update_global=True, ignore_files: set = None) -> dict:
        """
        returns the music library dict if update_global is False
        starts scanning and building the music library/database if update_global is True
        ignore_files is a list (converted to set) of files to not include in the return value / scan
            usually used with update_global=False (think about it)
        """
        global indexing_tracks_thread, all_tracks
        # make sure ignore_files is a set
        try: ignore_files = set(ignore_files)
        except TypeError: ignore_files = set()

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
            for uri in get_audio_uris((settings['queues'].values(), music_folders), scan_uris=False, ignore_m3u=True):
                if uri.startswith('http'):
                    get_url_metadata(uri)
                else:
                    dict_to_use[uri] = get_metadata_wrapped(uri)
            if use_temp: all_tracks = all_tracks_temp
            gui_window.metadata['update_listboxes'] = True
            all_tracks_sorted = sorted(all_tracks.items(), key=lambda item: item[1]['sort_key'])
            # scan items in playlists
            for _ in get_audio_uris(settings['playlists'].values(), ignore_m3u=True):
                # the function scans for us
                pass

        if not update_global:
            temp_tracks = all_tracks.copy()
            for ignore_file in ignore_files: temp_tracks.pop(ignore_file, None)
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
        global settings, music_folders, settings_last_modified, DEFAULT_FOLDER
        _save_settings = False
        with settings_file_lock:
            try:
                with open(SETTINGS_FILE, encoding='utf-8') as json_file:
                    loaded_settings = json.load(json_file)
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
                if settings['scan_folders']: index_all_tracks()
            refresh_tray()
            DEFAULT_FOLDER = music_folders[0] if music_folders else home_music_folder
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
            Shared.lang = settings['lang']
            Shared.track_format = settings['track_format']
            fg, bg, accent = theme['text'], theme['background'], theme['accent']
            Sg.set_options(text_color=fg, element_text_color=fg, input_text_color=fg,
                           button_color=(bg, accent), element_background_color=bg, scrollbar_color=bg,
                           text_element_background_color=bg, background_color=bg,
                           input_elements_background_color=bg, progress_meter_color=accent,
                           titlebar_background_color=bg, titlebar_text_color=fg,
                           # progress_meter_style=
                           border_width=0, slider_border_width=1, progress_meter_border_depth=0, font=FONT_NORMAL)
        if _save_settings: save_settings()
        settings_last_modified = os.path.getmtime(SETTINGS_FILE)


    @app.errorhandler(404)
    def page_not_found(_):
        return redirect('/')


    @app.post('/upload/')
    def upload_files():  # web GUI
        if 'files' not in request.files or not request.values.get('password'): return redirect('/#more')
        if request.values['password'] == settings['upload_pw']:
            # only save if upload_pw is set
            uploaded_files = request.files.getlist('files')
            for file in uploaded_files:
                file.save(Path.home() / 'Downloads' / file.filename)
        return redirect('/#more')

    @app.route('/', methods=['GET', 'POST'])
    def web_index():  # web GUI
        if request.values:
            if 'play' in request.values:
                if resume('web'):
                    api_msg = 'resumed playback'
                else:
                    if music_queue:
                        play()
                        api_msg = 'started playing first track in queue'
                    else:
                        play_all()
                        api_msg = 'shuffled all and started playing'
            elif 'pause' in request.values:
                pause()  # resume == play
                api_msg = 'pause called'
            elif 'next' in request.values:
                ignore_timestamps = 'ignore_timestamps' in request.values
                next_track(times=int(request.values.get('times', 1)), forced=True, ignore_timestamps=ignore_timestamps)
                api_msg = 'next track called'
            elif 'prev' in request.values:
                prev_track(times=int(request.values.get('times', 1)), forced=True)
                api_msg = 'prev track called'
            elif 'repeat' in request.values:
                cycle_repeat()
                api_msg = 'cycled repeat to ' + {None: 'off', True: 'one', False: 'all'}[settings['repeat']]
            elif 'shuffle' in request.values:
                shuffle_enabled = update_settings('shuffle', not settings['shuffle'])
                api_msg = f'shuffle set to {shuffle_enabled}'
            elif 'activate' in request.values:
                daemon_commands.put('__ACTIVATED__')  # tell main thread to show GUI
                api_msg = 'activated main window'
            else: api_msg = 'invalid command'
            return api_msg if ('is_api' in request.args or request.method == 'POST') else redirect('/')
        metadata = get_current_metadata()
        art = get_current_art()
        if type(art) == bytes: art = art.decode()
        art = f'data:image/png;base64,{art}'
        repeat_option = settings['repeat']
        repeat_enabled = 'repeat-enabled' if settings['repeat'] is not None else ''
        shuffle_enabled = 'shuffle-enabled' if settings['shuffle'] else ''
        # sort by the formatted title
        if all_tracks_sorted: sorted_tracks = all_tracks_sorted
        else: sorted_tracks = sorted(all_tracks.items(), key=lambda item: item[1]['sort_key'])
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
                stream_url = f'/file?path={file_path}'
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


    @app.route('/status/')
    @app.route('/state/')
    def api_state():
        _metadata = get_current_metadata()
        now_playing = {'status': str(playing_status), 'volume': settings['volume'], 'lang': settings['lang'],
                       'title': str(_metadata['title']), 'artist': str(_metadata['artist']),
                       'album': str(_metadata['album']), 'gui_open': not gui_window.was_closed(),
                       'track_position': get_track_position(), 'track_length': track_end - track_start,
                       'queue_length': len(done_queue) + len(music_queue) + len(next_queue)}
        return jsonify(now_playing)


    @app.route('/play/', methods=['GET', 'POST'])
    def api_play():
        global last_play_command
        queue_only = request.values.get('queue', '').casefold() == 'true'
        play_next = request.values.get('play_next', '').casefold() == 'true'
        merge_plays = time.monotonic() - last_play_command < 0.5
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
        last_play_command = time.monotonic()
        if 'uris' in request.values:
            play_uris(request.values.getlist('uris'), queue_uris=queue_only,
                      play_next=play_next, merge_tracks=merge_plays)
            if not queue_only and not play_next and settings['queue_library'] and merge_plays == 0:
                queue_all()
        elif 'uri' in request.values:
            play_uris([request.values['uri']], queue_uris=queue_only, play_next=play_next, merge_tracks=merge_plays)
            if settings['queue_library']: queue_all()
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


    @app.route('/exit/', methods=['GET', 'POST'])
    def api_exit():
        daemon_commands.put('__EXIT__')
        return api_state()


    @app.route('/change-setting/', methods=['POST'])
    def api_change_setting():
        with suppress(KeyError, TypeError):
            json_data = request.get_json(force=True, silent=True)
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
        friendly = 'friendly' in request.values
        if not friendly:
            devices = {'0': 'Local device'}
            for _uuid, cast_info in cast_browser.devices.items():
                devices[str(_uuid)] = cast_info.friendly_name
        else:
            devices = ['Local device::0']
            for cast_info in sorted(cast_browser.devices.values(), key=cast_info_sorter):
                devices.append(f'{cast_info.friendly_name}::{cast_info.uuid}')
        return jsonify(devices)


    @app.post('/change-device/<_uuid>')
    def api_change_device(_uuid):
        return str(change_device(_uuid))


    def cancel_timer():
        global timer
        timer = 0
        if settings['notifications']: tray_notify(t('Timer cancelled'))


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


    @app.route('/file/')
    def api_get_file():
        if 'path' in request.args:
            file_path = request.args['path']
            if os.path.isfile(file_path) and valid_audio_file(file_path) or file_path == 'DEFAULT_ART':
                if request.args.get('thumbnail_only', False) or file_path == 'DEFAULT_ART':
                    mime_type, img_data = get_album_art(file_path, settings['folder_cover_override'])
                    img_data = base64.b64decode(img_data)
                    try:
                        ext = mime_type.rsplit('/', 1)[1]
                    except IndexError:
                        ext = 'png'
                    return send_file(io.BytesIO(img_data), download_name=f'cover.{ext}',
                                     mimetype=mime_type, as_attachment=True, max_age=360000, conditional=True)
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
            # noinspection PyProtectedMember
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
            return send_file(io.BytesIO(base64.b64decode(custom_art('SYS'))), download_name=f'thumbnail.png',
                             mimetype='image/png', as_attachment=True, max_age=360000, conditional=True)
        return Response(sar.get_audio_data(settings['sys_audio_delay']))


    def cast_try_reconnect():
        app_log.info('cast_try_reconnect() started')
        global cast_browser, zconf
        cast_browser.stop_discovery()
        zconf = zeroconf.Zeroconf()
        cast_browser = pychromecast.discovery.CastBrowser(MyCastListener(), zconf)
        cast_browser.start_discovery()
        wait_until = time.monotonic() + WAIT_TIMEOUT
        while cast is None and time.monotonic() < wait_until:
            time.sleep(0.2)
        app_log.info('cast_try_reconnect() finished')


    @cmp_to_key
    def cast_info_sorter(ci1: CastInfo, ci2: CastInfo):
        # sort by groups, then by name, then by UUID
        if ci1.cast_type == 'group' and ci2.cast_type != 'group': return -1
        if ci1.cast_type != 'group' and ci2.cast_type == 'group': return 1
        if ci1.friendly_name < ci2.friendly_name: return -1
        if ci1.friendly_name > ci2.friendly_name: return 1
        if str(ci1.uuid) > str(ci2.uuid): return 1
        return -1


    def get_devices():
        lo_cis = sorted(cast_browser.devices.values(), key=cast_info_sorter)
        lo_devices = [Device()]
        lo_devices.extend((Device(cast_info) for cast_info in lo_cis))
        return lo_devices


    class MyCastListener(pychromecast.discovery.AbstractCastListener):

        def add_cast(self, uuid, _service):
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
                    cast.wait()
            refresh_tray(True)

        def remove_cast(self, uuid, _service, cast_info):
            """Called when a cast has been lost (MDNS info expired or host down)."""
            global cast
            if cast is not None and cast.uuid == uuid:
                # lost connection to connected device
                app_log.info(f'Lost connection to {cast.name} ({uuid}), switching to local device')
            refresh_tray(True)

        def update_cast(self, uuid, _service):
            """Called when a cast has been updated (MDNS info renewed or changed)."""
            refresh_tray(True)


    @time_cache(max_age=60)
    def get_device(device_uuid):
        # UnboundLocalError is possible
        return pychromecast.get_chromecast_from_cast_info(cast_browser.devices[device_uuid], zconf)

    def change_device(new_uuid='local'):
        """switch_device
        if new_uuid is invalid, then the local device is selected
        """
        global cast
        app_log.info(f'change_device({new_uuid})')
        try:
            if not isinstance(new_uuid, UUID):
                new_uuid = UUID(hex=new_uuid)
            with suppress(AttributeError):
                if cast.uuid == new_uuid:
                    # do not change device if same cast is selected
                    return True
            if new_uuid not in cast_browser.devices:
                return False
            # cast_info = cast_browser.devices[new_uuid]
            # new_device = pychromecast.get_chromecast_from_cast_info(cast_info, zconf)
            new_device = get_device(new_uuid)
        except (ValueError, TypeError):
            # local device selected (any non uuid string)
            new_device = None
        except UnboundLocalError as e:
            app_log.error('Could not connect to cast device', exc_info=e)
            tray_notify(t('ERROR') + ': ' + t('Could not connect to cast device') + ' (cd)')
            return False
        if cast == new_device:
            # do not change device if local device is selected again
            return True
        # cache information
        current_pos = 0
        if cast is not None and cast.app_id == APP_MEDIA_RECEIVER:
            if playing_status.busy():
                mc = cast.media_controller
                with suppress(UnsupportedNamespace, NotConnected):
                    mc.update_status()  # Switch device without playback loss
                    current_pos = mc.status.adjusted_current_time
                    if mc.is_playing or mc.is_paused: mc.stop()
            with suppress(NotConnected):
                cast.quit_app()
        elif cast is None and 'audio_player' in globals() and audio_player.is_busy():
            current_pos = audio_player.stop()
        autoplay = playing_status.playing()
        was_busy = playing_status.busy()
        playing_status.stop()
        cast = new_device
        update_settings('device', None if cast is None else str(cast.uuid))
        refresh_tray(True)
        if was_busy and (music_queue or sar.alive):
            if not sar.alive:
                play(position=current_pos, autoplay=autoplay, switching_device=True)
            else:
                play_system_audio(switching_device=True)
        else:
            if cast is not None:
                cast.wait(timeout=WAIT_TIMEOUT)
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
        gui_window.metadata['update_listboxes'] = True


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
        gui_window.metadata['update_listboxes'] = True


    def format_pl_lb(tracks):
        """Return usable list for playlist listbox"""
        return [f"{i + 1}. {format_uri(track, _for='pl')}" for i, track in enumerate(tracks)]


    def format_uri(uri: str, use_basename=False, _for=''):
        try:
            if use_basename: raise TypeError
            metadata = get_uri_metadata(uri, read_file=False)
            title, artist = metadata['title'], metadata['artist']
            if artist == Unknown('Artist') or title == Unknown('Title'): raise KeyError
            formatted = settings['track_format'].replace('&artist', artist).replace('&title', title)
            formatted = formatted.replace('&alb', metadata['album'])
            number = metadata.get('track_number', '')
            if '&trck' in formatted:
                formatted = formatted.replace('&trck', number)
            elif settings['show_track_number'] and number:
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
            if uri.startswith('http'): return uri
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
                        if i < 0: pre = f'\u2012{abs(i)} '.center(max_digits, '\u2000')
                        else: pre = f'{i} '.center(max_digits, '\u2000')
                        formatted_track = f'\u2004{pre}|\u2000{formatted_track}'
                        i += 1
                    tracks.append(formatted_track)
            return tracks
        except RuntimeError:
            # deque mutated during iteration
            return create_track_list()


    def update_gui():
        if gui_window.was_closed():
            return
        try:
            if playing_status.stopped():
                gui_window['progress_bar'].update(0, disabled=True)
            else:
                value, range_max = (1, 1) if track_length is None else (floor(track_position), track_length)
                gui_window['progress_bar'].update(value, range=(0, range_max), disabled=track_length is None)
            metadata = get_current_metadata()
            title, artist, album = metadata['title'], get_first_artist(metadata['artist']), metadata['album']
            if playing_status.busy() and music_queue and not sar.alive:
                if settings['show_track_number']:
                    with suppress(KeyError):
                        track_number = metadata['track_number']
                        title = f'{track_number}. {title}'
            if settings['mini_mode']: title = truncate_title(title)
            else:
                default_device = None if cast is None else cast.cast_info
                gui_window['devices'].update(value=Device(default_device), values=get_devices())
                gui_window['album'].update(album)
            gui_window['title'].update(title)
            gui_window['artist'].update(artist)
            image_data = PAUSE_BUTTON_IMG if playing_status.playing() else PLAY_BUTTON_IMG
            gui_window['pause/resume'].update(image_data=image_data)
            if settings['show_album_art']:
                size = COVER_MINI if settings['mini_mode'] else COVER_NORMAL
                bg = settings['theme']['background']
                try:
                    album_art_data = resize_img(get_current_art(), bg, size, default_art=DEFAULT_ART)
                except OSError as e:
                    handle_exception(e)
                    album_art_data = resize_img(DEFAULT_ART, bg, size)
                gui_window['artwork'].update(data=album_art_data)
            repeat_button: Sg.Button = gui_window['repeat']
            repeat_img, new_tooltip = repeat_img_tooltip(settings['repeat'])
            repeat_button.metadata = settings['repeat']
            repeat_button.update(image_data=repeat_img)
            repeat_button.set_tooltip(new_tooltip)
            shuffle_image_data = SHUFFLE_ON if settings['shuffle'] else SHUFFLE_OFF
            gui_window['shuffle'].update(image_data=shuffle_image_data)
        except TclError as e:
            app_log.info(f'gui_window.was_closed() = {gui_window.was_closed()}')
            handle_exception(e)


    def after_play(title, artists: str, autoplay, switching_device):
        app_log.info(f'after_play: autoplay={autoplay}, switching_device={switching_device}')
        # prevent Windows from going to sleep
        if autoplay:
            if platform.system() == 'Windows':
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
            if settings['notifications'] and not switching_device and gui_window.was_closed():
                # artists is comma separated string
                tray_notify(t('Playing') + f': {get_first_artist(artists)} - {title}')
            playing_status.play()
        else:
            playing_status.pause()
        refresh_tray()
        save_queues()
        DiscordPresence.update(settings['discord_rpc'], state=t('By') + f': {artists}', details=title,
                               large_text=t('Listening'))
        if not gui_window.was_closed():
            gui_window.metadata['update_listboxes'] = True
            daemon_commands.put('__UPDATE_GUI__')
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
            sar.start()  # start recording system audio BEFORE the first request for data
            url = f'http://{get_ipv4()}:{Shared.PORT}/system-audio/'
            mc.play_media(url, 'audio/wav', metadata=metadata, thumb=f'{url}/thumb', stream_type='LIVE')
            mc.block_until_active(WAIT_TIMEOUT + 1)
            stream_start_time = time.monotonic()
            block_until = time.monotonic() + WAIT_TIMEOUT
            while not mc.status.player_is_playing and time.monotonic() < block_until:
                time.sleep(0.05)
            mc.play()
            sar.lag = time.monotonic() - stream_start_time  # ~1 second
            track_length = None
            track_position = 0
            track_start = time.monotonic() - track_position
            after_play(title, artist, True, switching_device)
            return True
        except OSError:
            tray_notify(t('ERROR') + ': ' + t('Could not find an output device to record'))
        except PyChromecastError as e:
            app_log.error(f'play_sys_audio failed to cast {repr(e)}')
            if show_error:
                tray_notify(t('ERROR') + f': ' + t('Could not connect to cast device') + ' (psa)')
                change_device()
                return handle_exception(e)
            cast_try_reconnect()
            return play_system_audio(switching_device=switching_device, show_error=True)
        except Exception as e:
            handle_exception(e)
            tray_notify('ERROR: Something went wrong')
        return False

    def url_expired(uri, default=False):
        """ Returns if URI is a URL that has expired """
        default_expiry_time = time.time() + 3 if default else 0
        expiry_time = url_metadata.get(uri, {}).get('expiry', default_expiry_time)
        return expiry_time < time.time()


    def tbr_audio_key(item):
        return (item.get('tbr', 0) or 0) * (item.get('vcodec', 'none') == 'none')

    def tbr_video_key(item):
        return (item.get('height', 0) or 0), (item.get('tbr', 0) or 0)

    def ydl_get_metadata(item, duration_helper=True):
        if 'formats' in item:
            audio_url = max(item['formats'], key=tbr_audio_key)['url']
            try:
                formats = [_f for _f in item['formats'] if _f.get('acodec') != 'none' and _f.get('vcodec') != 'none']
                selected_format = max(formats, key=tbr_video_key)
                ext, _url = selected_format['ext'], selected_format['url']
            except ValueError:
                # url is audio only
                ext, _url = item['ext'] if item['ext'] != 'unknown_video' else item['format_id'], audio_url
        else:
            ext = item['ext']
            _url = audio_url = item['url']
        if item.get('is_live', False) and 'duration' not in item and duration_helper:
            helper_ap = AudioPlayer()
            helper_ap.play(audio_url, False)
            item['duration'] = helper_ap.get_length()
        expiry_time = time.time() + max(1800, item.get('duration', 0))
        length = item['duration'] if item.get('duration', 0) else None
        src_url = item['webpage_url']
        split_url = src_url.rsplit('/', 2)
        backup_artist = split_url[-1] if split_url[-1] != '' else split_url[-2]
        artist = item.get('artist', item.get('uploader', backup_artist))
        album = item.get('album', item.get('playlist'))
        if album is None:
            album = item['extractor_key']
        metadata = {'title': item.get('track', item['title']), 'artist': artist, 'url': _url,
                    'expiry': expiry_time, 'id': item['id'], 'ext': ext, 'audio_url': audio_url, 'src': src_url,
                    'album': album, 'length': length, 'is_live': item.get('is_live', False)}
        if 'thumbnail' in item:
            metadata['art'] = item['thumbnail']
        return metadata

    # noinspection PyTypeChecker
    def get_url_metadata(url, fetch_art=True) -> list:
        # TODO: move to helpers.py and add parameter url_metadata_cache
        """
        Tries to parse url and set url_metadata[url] to parsed metadata
        Supports: YouTube, Soundcloud, any url ending with a valid audio extension
        """
        global deezer_opened
        metadata_list = []
        app_log.info('get_url_metadata: ' + url)
        if url in url_metadata and not url_expired(url): return [url_metadata[url]]
        if url.startswith('www'):
            url = f'http://{url}'
        if url.startswith('http') and valid_audio_file(url):  # source url e.g. http://...radio.mp3
            ext = url[::-1].split('.', 1)[0][::-1]
            url_frags = urlsplit(url)
            title, artist, album = url_frags.path.split('/')[-1], url_frags.netloc, url_frags.path[1:]
            url_metadata[url] = metadata = {'title': title, 'artist': artist, 'length': None, 'album': album,
                                            'src': url, 'url': url, 'ext': ext}  # never expires
            metadata_list.append(metadata)
        elif 'twitch.tv' in url:
            with suppress(StopIteration, IOError):
                r = ydl_extract_info(url, quiet=not is_debug())
                audio_url = max(r['formats'], key=lambda item: item['tbr'] * (item['vcodec'] == 'none'))['url']
                metadata = {'title': r['description'], 'artist': r['uploader'], 'ext': r['ext'],
                            'expiry': time.time(), 'album': 'Twitch', 'length': None,
                            'art': r['thumbnail'], 'url': r['url'], 'audio_url': audio_url, 'src': url}
                url_metadata[url] = metadata
                metadata_list.append(metadata)
        elif 'soundcloud.com' in url:
            with suppress(StopIteration, IOError):
                r = ydl_extract_info(url, quiet=not is_debug())
                if 'entries' in r:
                    for entry in r['entries']:
                        parsed_url = parse_qs(urlparse(entry['url']).query)['Policy'][0].replace('_', '=')
                        policy = base64.b64decode(parsed_url).decode()
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
                    policy = base64.b64decode(url_policy_b64).decode()
                    expiry_time = json.loads(policy)['Statement'][0]['Condition']['DateLessThan']['AWS:EpochTime']
                    url_metadata[url] = metadata = {'title': r['title'], 'artist': r['uploader'], 'album': 'SoundCloud',
                                                    'src': url, 'ext': r['ext'], 'expiry': expiry_time,
                                                    'length': r['duration'], 'art': r['thumbnail'], 'url': r['url']}
                    metadata_list.append(metadata)
        # youtube
        elif (ytid := get_yt_id(url)) is not None or url.startswith('ytsearch:'):
            # lazily get videos in the playlist
            if ytid is not None and ytid.startswith('PL'):
                videos = scrapetube.get_playlist(ytid)
                for i, video in enumerate(videos):
                    _url = f'https://www.youtube.com/watch?v={video["videoId"]}'
                    src_url = f'{_url}&list={ytid}'
                    if i == 0:
                        m_lst = get_url_metadata(_url)
                        if m_lst:
                            m = m_lst[0]
                            m['pl_src'] = src_url
                            metadata_list.extend(m_lst)
                    else:
                        metadata = {'title': video['title']['runs'][0]['text'],
                                    'artist': video['shortBylineText']['runs'][0]['text'], 'album': 'YouTube',
                                    'id': video['videoId'], 'src': _url, 'pl_src': src_url,
                                    'art': f'https://img.youtube.com/vi/{ytid}/maxresdefault.jpg'}
                        url_metadata[_url] = metadata
                        metadata_list.append(metadata)
            else:
                # type error in case video was deleted or unavailable
                with suppress(IOError, TypeError):
                    r = ydl_extract_info(url, quiet=not is_debug())
                    if 'entries' in r:
                        for entry in r['entries']:
                            metadata = ydl_get_metadata(entry, duration_helper=False)
                            metadata['ytid'] = entry['id']
                            # if duration > 10 minutes, try to parse out timestamps for track from comment section
                            if entry.get('duration', 0) > 600: metadata['timestamps'] = get_video_timestamps(entry)
                            for webpage_url in get_yt_urls(entry['id']): url_metadata[webpage_url] = metadata
                            metadata_list.append(metadata)
                    else:
                        # single video
                        metadata = ydl_get_metadata(r, duration_helper=False)
                        metadata['ytid'] = r['id']
                        # if duration > 10 minutes, try to parse out timestamps for track from comment section
                        if r.get('duration', 0) > 600: metadata['timestamps'] = get_video_timestamps(r)
                        for webpage_url in get_yt_urls(r['id']): url_metadata[webpage_url] = metadata
                        url_metadata[url] = metadata
                        metadata_list.append(metadata)
        elif url.startswith('https://open.spotify.com'):
            # spotify metadata has already been fetched, so just get youtube metadata
            if url in url_metadata and isinstance(url_metadata[url], dict):
                metadata = url_metadata[url]
                if 'ytid' in metadata:
                    youtube_metadata = get_url_metadata(f"https://www.youtube.com/watch?v={metadata['ytid']}", False)
                else:
                    query = f"{get_first_artist(metadata['artist'])} - {metadata['title']}"
                    youtube_metadata = get_url_metadata(f'ytsearch:{query}', False)
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
                    youtube_metadata = get_url_metadata(f'ytsearch:{query}', False)
                    if youtube_metadata:
                        youtube_metadata = youtube_metadata[0]
                        # expiry, url, and audio_url are not overwritten here
                        metadata = {**youtube_metadata, **metadata}
                        if metadata['src'] == '':
                            metadata['src'] = youtube_metadata['src']
                        url_metadata[metadata['src']] = url_metadata[youtube_metadata['src']] = metadata
                        # if url is a spotify track, set its metadata
                        if len(spotify_tracks) == 1: url_metadata[url] = metadata
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
                    Thread(target=webbrowser.open, daemon=True, args=('https://www.deezer.com/login',)).start()
                    tray_notify(t('ERROR') + ': ' + t('Not logged into deezer.com'))
                    deezer_opened = True
                # fallback to deezer -> youtube
                if url in url_metadata:
                    metadata = url_metadata[url]
                    query = f"{get_first_artist(metadata['artist'])} - {metadata['title']}"
                    youtube_metadata = get_url_metadata(f'ytsearch:{query}', False)[0]
                    metadata = {**youtube_metadata, **metadata}
                    url_metadata[metadata['src']] = url_metadata[youtube_metadata['src']] = metadata
                    metadata_list.append(metadata)
                else:
                    deezer_tracks = get_deezer_tracks(url, login=False)
                    if deezer_tracks:
                        metadata = deezer_tracks[0]
                        query = f"{get_first_artist(metadata['artist'])} - {metadata['title']}"
                        youtube_metadata = get_url_metadata(f'ytsearch:{query}', False)[0]
                        metadata = {**youtube_metadata, **metadata}
                        url_metadata[metadata['src']] = url_metadata[youtube_metadata['src']] = metadata
                        metadata_list.append(metadata)
                        for deezer_track in islice(deezer_tracks, 1, None):
                            url_metadata[deezer_track['src']] = deezer_track
                            uris_to_scan.put(deezer_track['src'])
                            metadata_list.append(deezer_track)
        else:
            with suppress(IOError, TypeError):
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
                    url_metadata[metadata['src']]['art_data'] = base64.b64encode(requests.get(art_url).content)
                except requests.RequestException as e:
                    app_log.info(f'Could not fetch art url {art_url}')
                    handle_exception(e)
        return metadata_list


    def play_url(position=0, autoplay=True, switching_device=False, show_error=False) -> bool:
        global cast, playing_url, track_length, track_start, track_end, track_position
        url = music_queue[0]
        metadata_list = get_url_metadata(url)
        if metadata_list:
            if len(metadata_list) > 1:
                # url was for multiple sources
                with suppress(IndexError):
                    music_queue.popleft()
                music_queue.extendleft((metadata['src'] for metadata in reversed(metadata_list)))
            metadata = metadata_list[0]
            title, artist, album = metadata['title'], metadata['artist'], metadata['album']
            ext = metadata['ext']
            url = metadata['audio_url'] if cast is None and 'audio_url' in metadata else metadata['url']
            thumbnail = metadata['art'] if 'art' in metadata else f'{get_ipv4()}/file?path=DEFAULT_ART'
            track_length = metadata['length']
            if cast is None:
                volume = 0 if settings['muted'] else settings['volume'] / 100
                if autoplay or not metadata.get('is_live', False):
                    audio_player.play(url, start_playing=autoplay, start_from=position, volume=volume)
            else:
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
                    if track_length is None: mc.play()
                except NotConnected:
                    app_log.error('play_url failed to cast because cast was not connected')
                    tray_notify(t('ERROR') + ': ' + t('Could not connect to cast device') + ' (play_url)')
                    change_device()
                    return False
                except (PyChromecastError, OSError) as e:
                    app_log.error(f'play_url failed to cast {repr(e)}')
                    if show_error:
                        tray_notify(t('ERROR') + ': ' + t('Could not connect to cast device') + ' (play_url)')
                        return handle_exception(e)
                    cast_try_reconnect()
                    return play_url(position, autoplay, switching_device, show_error=True)
            track_position = position
            track_start = time.monotonic() - track_position
            if track_length is not None:
                track_end = track_start + track_length
            playing_url = True
            after_play(title, artist, autoplay, switching_device)
            return True
        if settings['notifications']: tray_notify(t('ERROR') + ': ' + t('Could not play $URL').replace('$URL', url))
        return False

    def play(position=0, autoplay=True, switching_device=False, show_error=False):
        global cast, track_start, track_end, track_length, track_position, music_queue, playing_url, cast_browser, zconf
        uri = music_queue[0]
        while not os.path.exists(uri):
            if play_url(position, autoplay, switching_device): return
            done_queue.append(music_queue.popleft())
            if not music_queue: return
            uri, position = music_queue[0], 0
        uri = Path(uri).as_posix()
        playing_url = sar.alive = False
        shortened_uri = '$FILE.' + uri.rsplit('.')[-1]
        app_log.info(f'Playing {shortened_uri} @{position}, autoplay={autoplay}, switching_device={switching_device})')
        try:
            track_length = get_length(uri)
        except InvalidAudioFile:
            done_queue.append(music_queue.popleft())
            msg = t('ERROR') + ': ' + t('Invalid audio file $FILE').replace('$FILE', uri)
            tray_notify(msg)
            if music_queue: play()
            return
        metadata = get_metadata_wrapped(uri)
        # update metadata of track in case something changed
        all_tracks[uri] = metadata
        volume = 0 if settings['muted'] else settings['volume'] / 100
        if cast is None:  # play locally
            audio_player.play(uri, volume=volume, start_playing=autoplay, start_from=position)
        else:
            try:
                url_args = urllib.parse.urlencode({'path': uri})
                url = f'http://{get_ipv4()}:{Shared.PORT}/file?{url_args}'
                cast.wait(timeout=WAIT_TIMEOUT)
                cast.set_volume(volume)
                mc = cast.media_controller
                metadata = {'title': metadata['title'], 'artist': metadata['artist'],
                            'albumName': metadata['album'], 'metadataType': 3}
                ext = uri.split('.')[-1]
                mc.play_media(url, f'audio/{ext}', current_time=position,
                              metadata=metadata, thumb=url + '&thumbnail_only=true', autoplay=autoplay)
                app_log.info(f'play: mc.status.player_state={mc.status.player_state}')
            except (NotConnected, AttributeError):
                app_log.error('play could not cast because cast is not connected')
                """
                2022-03-09 10:52:40,920 ERROR (396): [Computer room(192.168.1.9):8009]
                Failed to connect to service ServiceInfo(type='mdns',
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
                tray_notify(t('ERROR') + f': ' + t('Could not connect to cast device') + ' (play)')
                change_device()
                return False
            except (PyChromecastError, OSError, RuntimeError) as e:
                app_log.error(f'play failed to cast {repr(e)}')
                if show_error:
                    tray_notify(t('ERROR') + f': ' + t('Could not connect to cast device') + ' (play)')
                    change_device()
                    return handle_exception(e)
                cast_try_reconnect()
                return play(position=position, autoplay=autoplay, switching_device=switching_device, show_error=True)
        track_position = position
        track_start = time.monotonic() - track_position
        track_end = track_start + track_length
        return after_play(metadata['title'], metadata['artist'], autoplay, switching_device)


    def metadata_key(filename):
        """ Sort by (artist, album, trck num, title) """
        m = get_uri_metadata(filename)
        try:
            tn = int(m.get('track_number'))
        except (ValueError, TypeError):
            tn = 1
        return m['album'].casefold(), tn , m['artist'].casefold(), m['title'].casefold()


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
        temp_queue = list(get_audio_uris(uris))
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
            # do custom sort only if dir and not natural
            temp_queue.sort(key=metadata_key)
        # add to next queue condition
        if play_next:
            if settings['reversed_play_next']:
                next_queue.extendleft(reversed(temp_queue))
            else:
                next_queue.extend(temp_queue)
            gui_window.metadata['update_listboxes'] = True
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
        gui_window.metadata['update_listboxes'] = True
        save_queues()
        return True


    def play_all(starting_files: Iterable = None, queue_only=False):
        """
        Clears done queue, music queue, adds starting files to music queue.
        Shuffles and queues files in the library without duplication
        """
        if starting_files is None: starting_files = []
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
            if music_queue:
                play()
            elif next_queue:
                next_track(forced=True)
        gui_window.metadata['update_listboxes'] = True


    def queue_all():
        if not any(filter(lambda t: t.name == 'PlayAll', threading.enumerate())):
            Thread(target=play_all, kwargs={'queue_only': True}, daemon=True, name='PlayAll').start()


    def open_dialog(title, for_dir=False, filetypes=None):
        if settings['use_last_folder'] and os.path.exists(settings['last_folder']):
            initial_folder = settings['last_folder']
        else:
            initial_folder = DEFAULT_FOLDER
        _root = tkinter.Tk()
        _root.withdraw()
        if platform.system() != 'Linux':
            _root.iconbitmap(WINDOW_ICON)
        if for_dir:
            paths = fd.askdirectory(title=title, initialdir=initial_folder, parent=_root)
        else:
            paths = fd.askopenfilenames(title=title, parent=_root, initialdir=initial_folder,
                                        filetypes=filetypes)
        _root.destroy()
        return paths


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
            gui_window.metadata['last_event'] = 'file_action'


    def folder_action(action='pf'):
        """
        :param action: one of {'pf': 'Play Folder', 'qf': 'Queue Folder', 'pfn': 'Play Folder Next'}
        """
        directory = open_dialog(t('Select Folder'), for_dir=True)
        if directory:
            gui_window.metadata['last_event'] = Sg.TIMEOUT_KEY
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
                gui_window.metadata['update_listboxes'] = True
                save_queues()
            elif settings['notifications']:
                tray_notify(t('ERROR') + ': ' + t('Folder does not contain audio files'))
        else: gui_window.metadata['last_event'] = 'folder_action'


    def get_track_position():
        global track_position
        if playing_status.busy():
            if cast is not None:
                if playing_status.playing(): track_position = time.monotonic() - track_start
            else: track_position = audio_player.get_pos()
        return track_position


    def pause(source=''):
        """
        Returns true if player was playing
        Returns false if player was not playing
        can be called from a non-main thread
        """
        global track_position
        app_log.info(f'pause({source}), playing status = {playing_status}')
        if playing_status.playing():
            if platform.system() == 'Windows':
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
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
                    mc.pause()
                    block_until = time.monotonic() + 5
                    while not mc.status.player_is_paused and time.monotonic() < block_until: time.sleep(0.1)
                    track_position = mc.status.adjusted_current_time
                    app_log.info('paused cast device')
                playing_status.pause()
                if music_queue or sar.alive:
                    metadata = get_current_metadata()
                    title, artist = metadata['title'], metadata['artist']
                    DiscordPresence.update(settings['discord_rpc'], state=t('By') + f': {artist}', details=title,
                                           large_text='Paused')
            except UnsupportedNamespace:
                stop('pause')
            if not gui_window.was_closed(): daemon_commands.put('__UPDATE_GUI__')
            refresh_tray()
            return True
        return False


    def resume(source=''):
        global track_end, track_position, track_start
        app_log.info(f'resume(source = {source}), playing status = {playing_status}')
        if playing_status.paused():
            if music_queue and not os.path.exists(music_queue[0]) and url_expired(music_queue[0]):
                app_log.info(f'url expired, hard playing')
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
                    track_position = mc.status.adjusted_current_time
                track_start = time.monotonic() - track_position
                if track_length is not None:
                    track_end = track_start + track_length
                playing_status.play()
                metadata = get_current_metadata()
                title, artist = metadata['title'], get_first_artist(metadata['artist'])
                DiscordPresence.update(settings['discord_rpc'], state=t('By') + f': {artist}', details=title,
                                       large_text=t('Listening'))
                if platform.system() == 'Windows':
                    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
                if not gui_window.was_closed(): daemon_commands.put('__UPDATE_GUI__')
                refresh_tray()
            except PyChromecastError as e:
                print(e)
                if music_queue: return play(position=track_position)
            return True
        return False


    def stop(stopped_from: str, stop_cast=True):
        """
        can be called from a non-main thread
        does not check if playing_status is busy
        """
        global track_start, track_end, track_position, track_length, playing_url
        app_log.info(f'stopped from {stopped_from}, stop_cast={stop_cast}')
        # allow Windows to go to sleep
        if platform.system() == 'Windows':
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
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
                while ((status.player_is_playing or status.player_is_paused)
                       and time.monotonic() > block_until): time.sleep(0.1)
                if status.player_is_playing or status.player_is_paused: cast.quit_app()
        track_start = track_position = track_end = track_length = 0
        if not gui_window.was_closed(): daemon_commands.put('__UPDATE_GUI__')
        refresh_tray()


    def set_pos(new_position):
        global track_position, track_start, track_end
        if cast is not None:
            try:
                cast.media_controller.update_status()
            except PyChromecastError:
                cast.wait()
            if cast.media_controller.is_idle and music_queue:
                return play(position=new_position, autoplay=playing_status.playing())
            else:
                cast.media_controller.seek(new_position)
                if playing_status.paused(): cast.media_controller.pause()
        else:
            audio_player.set_pos(new_position)
        track_position = new_position
        track_start = time.monotonic() - track_position
        track_end = track_start + track_length


    def next_track(from_timeout=False, times=1, forced=False, ignore_timestamps=False):
        """
        :param from_timeout: whether next track is due to track ending
        :param times: number of times to go to next track
        :param forced: whether to ignore current playing status
        :param ignore_timestamps: whether to ignore timestamps for a track
        :return:
        """
        app_log.info(f'next_track(from_timeout={from_timeout})')
        if cast is not None and cast.app_id != APP_MEDIA_RECEIVER and not forced:
            playing_status.stop()
        elif (forced or playing_status.busy() and not sar.alive) and (next_queue or music_queue):
            with suppress(IndexError, TypeError):  # TypeError:  if track_length is None
                if track_length > 600 and not ignore_timestamps:
                    if url_metadata.get(music_queue[0], {}).get('timestamps'):
                        # smart next track if playing a long URL with multiple tracks
                        timestamps = url_metadata[music_queue[0]]['timestamps']
                        new_position = next(filter(lambda seconds: seconds > get_track_position(), timestamps), 0)
                        if new_position: return set_pos(new_position)
            # keep track of skips (used by smart queue feature)
            if music_queue and track_position < 5 and not from_timeout and playing_status.busy() and not forced:
                settings['skips'][music_queue[0]] = settings['skips'].get(music_queue[0], 0) + 1
                # save queue...
                save_settings()
            # if repeat all or repeat is off or empty queue or manual next
            if settings['repeat'] in {False, None} or not music_queue or not from_timeout:
                if settings['repeat']: update_settings('repeat', False)
                for _ in range(times):
                    if music_queue: done_queue.append(music_queue.popleft())
                    if next_queue: music_queue.appendleft(next_queue.popleft())
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
                        if next_queue: music_queue.appendleft(next_queue.popleft())
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
            stop('next track', stop_cast=not from_timeout)


    def prev_track(times=1, forced=False, ignore_timestamps=False):
        app_log.info('prev_track()')
        if not forced and cast is not None and cast.app_id != APP_MEDIA_RECEIVER:
            playing_status.stop()
        elif forced or playing_status.busy() and not sar.alive:
            with suppress(IndexError, TypeError):  # TypeError:  if track_length is None
                timestamps = url_metadata.get(music_queue[0], {}).get('timestamps', [])
                if track_length > 600 and timestamps and not ignore_timestamps:
                    # smart next track if playing a long URL with multiple tracks
                    _track_position = get_track_position()
                    new_position = next(filter(lambda secs: secs < _track_position - 5, reversed(timestamps)), -1)
                    if new_position != -1: return set_pos(new_position)
            if done_queue:
                for _ in range(times):
                    if settings['repeat']: update_settings('repeat', False)
                    track = done_queue.pop()
                    # if there's a next queue, move mq[0] to top of next_queue
                    if music_queue and next_queue:
                        next_queue.appendleft(music_queue.popleft())
                    music_queue.appendleft(track)
            with suppress(IndexError):
                settings['skips'].pop(music_queue[0], None)  # reset skip counter
                play()

    class UpdateChecker(threading.Timer):
        latest_version = VERSION

        def __init__(self):
            # check for an update every 4 hours
            super().__init__(14_400, self.check_for_updates)
            self.daemon = True
            self.start()

        def check_for_updates(self):
            release = get_latest_release(self.latest_version, VERSION)
            if release:
                # avoid showing a notification for the same latest version
                self.latest_version = release['version']
                if settings['notifications']: tray_notify('update_available', context=self.latest_version)


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
        global auto_updating
        # check for update and update if no must-run arguments were provided or if the update flag was used
        limited_args = len(sys.argv) == 1 or ['-m'] == sys.argv[1:]
        if (limited_args and settings['auto_update'] or args.update) and not args.nupdate: auto_update()
        auto_updating = False

        import pynput.keyboard
        global track_position, track_start, track_end
        if not is_debug(): send_info()
        create_shortcut()
        UpdateChecker()
        p = pynput.keyboard.Listener(on_press=on_press, on_release=lambda key: PRESSED_KEYS.discard(str(key)))
        p.name = 'pynputListener'
        p.start()
        while True:
            scanned = 0
            while not uris_to_scan.empty():
                uri = uris_to_scan.get()
                if uri.startswith('http'):
                    get_url_metadata(uri)
                else:
                    uri = Path(uri).as_posix()
                    all_tracks[uri] = get_metadata_wrapped(uri)
                uris_to_scan.task_done()
                scanned += 1
                if scanned >= 50:
                    scanned = 0
                    gui_window.metadata['update_listboxes'] = True
            if scanned:
                gui_window.metadata['update_listboxes'] = True
            time.sleep(0.1)


    def on_press(key):
        key = str(key)
        PRESSED_KEYS.add(key)
        valid_shortcut = len(PRESSED_KEYS) == 4 and "'m'" in PRESSED_KEYS
        ctrl_clicked = 'Key.ctrl_l' in PRESSED_KEYS or 'Key.ctrl_r' in PRESSED_KEYS
        shift_clicked = 'Key.shift' in PRESSED_KEYS or 'Key.shift_r' in PRESSED_KEYS
        alt_clicked = 'Key.alt_l' in PRESSED_KEYS or 'Key.alt_r' in PRESSED_KEYS
        # Ctrl + Alt + Shift + M open up main window
        if valid_shortcut and ctrl_clicked and shift_clicked and alt_clicked:
            daemon_commands.put('__ACTIVATED__')
        if key not in {'<179>', '<176>', '<177>', '<178>'}: return
        app_log.info(f'valid key press: {key}')
        if key == '<179>' and not pause(): resume('keyboard')
        elif key == '<176>' and playing_status.busy(): next_track()
        elif key == '<177>' and playing_status.busy(): prev_track()
        elif key == '<178>': stop('keyboard shortcut')


    def get_window_location():
        if not settings['save_window_positions']: return None, None
        if settings['mini_mode']: return settings['window_locations'].get('main_mini_mode', (None, None))
        key = 'main_vertical' if settings['vertical_gui'] else 'main'
        w, h = settings['window_locations'].get(key, (None, None))
        if w is None or h is None: return None, None
        # clamp window size to screen size
        if platform.system() == 'Windows':
            from win32api import GetSystemMetrics
            w = max(0, min(w, GetSystemMetrics(78) - 500))
            h = max(0, min(h, GetSystemMetrics(79) - 500))
        return w, h


    def metadata_process_file(file):
        if os.path.isfile(file):
            try:
                file_metadata = get_metadata_wrapped(file)
                gui_window['metadata_file'].update(value=file)
                gui_window['metadata_file'].set_tooltip(file)
                gui_window['metadata_title'].update(value=file_metadata['title'])
                gui_window['metadata_artist'].update(value=file_metadata['artist'])
                gui_window['metadata_album'].update(value=file_metadata['album'])
                gui_window['metadata_track_num'].update(value=file_metadata['track_number'])
                gui_window['metadata_explicit'].update(value=file_metadata['explicit'])
                mime, artwork = get_album_art(file)
                artwork = None if artwork == DEFAULT_ART else artwork
                _, display_art = gui_window['metadata_art'].metadata = (mime, artwork)
                if display_art is not None:
                    display_art = resize_img(display_art, settings['theme']['background'], COVER_MINI)
                gui_window['metadata_art'].update(data=display_art)
            except InvalidAudioFile:
                error = t('ERROR') + ': ' + t('Invalid audio file selected')
                gui_window['metadata_msg'].update(value=error, text_color='red')
                gui_window.TKroot.after(2000, lambda: gui_window['metadata_msg'].update(value=''))


    def add_music_folder(folders):
        added_folders = set(music_folders)
        for folder in folders:
            folder = folder.replace('\\', '/')
            if os.path.isdir(folder) and folder not in added_folders:
                music_folders.append(folder)
                added_folders.add(folder)
        gui_window['music_folders'].update(music_folders)
        refresh_tray()
        save_settings()
        if settings['scan_folders']: index_all_tracks()


    def set_callbacks():
        """ Set callbacks for the main window """

        def save_window_position(event):
            if event.widget is gui_window.TKroot:
                if settings['mini_mode']: key = 'main_mini_mode'
                else: key = 'main_vertical' if settings['vertical_gui'] else 'main'
                settings['window_locations'][key] = gui_window.CurrentLocation()
                save_settings()

        def library_events(event):
            library_tree_view = gui_window['library'].TKTreeview
            region = library_tree_view.identify('region', event.x, event.y)
            column_index = library_tree_view.identify_column(event.x).replace('#', '')
            gui_window.metadata['library']['region'] = region
            gui_window.metadata['library']['column'] = int(column_index)

        def dnd_pl_tracks(event):
            file_paths = gui_window.TKroot.tk.splitlist(event.data)
            pl_tracks = gui_window.metadata['pl_tracks']
            pl_tracks.extend(get_audio_uris(file_paths))
            update_settings('last_folder', os.path.dirname(file_paths[-1]))
            new_values = format_pl_lb(pl_tracks)
            new_i = len(new_values) - 1
            gui_window['pl_tracks'].update(new_values, set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))

        def dnd_queue(event):
            items = tk_lb.tk.splitlist(event.data)
            files = list(filter(os.path.isfile, items))
            dirs = filter(os.path.isdir, items)
            play_uris(files, queue_uris=True, natural_sort=len(files) > 20)
            for directory in dirs:
                # assume album
                play_uris(directory, queue_uris=True, natural_sort=False)

        def report_callback_exception(exc, _, __):
            if exc == KeyboardInterrupt:
                raise KeyboardInterrupt

        gui_window.hidden_master_root.report_callback_exception = report_callback_exception

        if platform.system() == 'Windows':
            gui_window.TKroot.tk.call('package', 'require', 'tkdnd')

        if not settings['mini_mode']:
            gui_window['url_input'].bind('<<Cut>>', '_cut')
            gui_window['url_input'].bind('<<Copy>>', '_copy')
            gui_window['pl_url_input'].bind('<<Cut>>', '_cut')
            gui_window['pl_url_input'].bind('<<Copy>>', '_copy')
            gui_window['library'].TKTreeview.bind('<Button-1>', library_events, add='+')
            gui_window['library'].TKTreeview.bind('<Double-Button-1>', library_events, add='+')
            scroll_areas = ['queue', 'pl_tracks', 'library']
            for scroll_area in scroll_areas:
                gui_window[scroll_area].bind('<Enter>', '_mouse_enter')
                gui_window[scroll_area].bind('<Leave>', '_mouse_leave')
            for input_key in {'url_input', 'pl_url_input', 'pl_name', 'timer_input',
                              'metadata_title', 'metadata_artist', 'metadata_album', 'metadata_track_num'}:
                gui_window[input_key].Widget.config(insertbackground=settings['theme']['text'])

            try:
                # drag and drop callbacks
                tk_lb = gui_window['queue'].TKListbox
                drop_target_register(tk_lb, DND_ALL)
                dnd_bind(tk_lb, '<<Drop>>', dnd_queue)

                tk_lb = gui_window['pl_tracks'].TKListbox
                drop_target_register(tk_lb, DND_ALL)
                dnd_bind(tk_lb, '<<Drop>>', dnd_pl_tracks)

                tk_frame = gui_window['tab_metadata'].TKFrame
                drop_target_register(tk_frame, DND_FILES)
                dnd_bind(tk_frame, '<<Drop>>', lambda event: metadata_process_file(tk_lb.tk.splitlist(event.data)[0]))

                tk_lb = gui_window['music_folders'].TKListbox
                drop_target_register(tk_lb, DND_FILES)
                dnd_bind(tk_lb, '<<Drop>>', lambda event: add_music_folder(tk_lb.tk.splitlist(event.data)))
            except NameError:
                # https://github.com/rdbende/tkinterDnD
                print('TODO: DND Not Implemented')
        else:
            try:
                root = gui_window.TKroot
                drop_target_register(root, DND_ALL)
                dnd_bind(root, '<<Drop>>', lambda event: play_uris(root.tk.splitlist(event.data), queue_uris=True))
            except NameError:
                print('TODO: DND Not Implemented')

        gui_window['volume_slider'].bind('<Enter>', '_mouse_enter')
        gui_window['volume_slider'].bind('<Leave>', '_mouse_leave')
        gui_window['progress_bar'].bind('<Enter>', '_mouse_enter')
        gui_window['progress_bar'].bind('<Leave>', '_mouse_leave')
        gui_window.TKroot.bind('<Configure> ', save_window_position, add='+')
        gui_window.bind('<Control-braceright>', 'mini_mode')
        gui_window.bind('<Control-Q>', 'exit_program')
        gui_window.bind('<Control-r>', 'repeat')
        gui_window.bind('<Control-s>', 's:83')
        gui_window.bind('<Control-m>', 'mute')
        gui_window.bind('<Control-e>', 'locate_uri')
        gui_window.bind('<KeyPress>', 'KeyPress')
        for i in range(1, 10):
            gui_window.bind(f'<Control-Key-{i}>', f'{i}:{48 + i}')
        gui_window.TKroot.bind("<KeyRelease>", lambda _: None)


    def activate_gui(selected_tab=None, url_option='url_play'):
        global gui_window
        # selected_tab can be 'tab_queue', ['tab_library'], 'tab_playlists', 'tab_timer', or 'tab_settings'
        app_log.info(f'activate_main_window: selected_tab={selected_tab}')
        if gui_window.was_closed():
            Shared.using_tcl_theme = settings.get('EXPERIMENTAL', False) and os.path.exists(SUN_VALLEY_TCL)
            # create window if window not alive
            lb_tracks = create_track_list()
            selected_value = lb_tracks[len(done_queue)] if lb_tracks and len(done_queue) < len(lb_tracks) else None
            mini_mode = settings['mini_mode']
            window_location = get_window_location()
            if settings['show_album_art']:
                size = COVER_MINI if mini_mode else COVER_NORMAL
                bg = settings['theme']['background']
                try:
                    album_art_data = resize_img(get_current_art(), bg, size, default_art=DEFAULT_ART)
                except OSError as e:
                    handle_exception(e)
                    album_art_data = resize_img(DEFAULT_ART, bg, size)
            else:
                album_art_data = None
            metadata = get_current_metadata()
            title, artist, album = metadata['title'], get_first_artist(metadata['artist']), metadata['album']
            main_gui_layout = create_main(lb_tracks, selected_value, playing_status, settings, VERSION, timer,
                                          all_tracks, get_devices(), title, artist, album, track_length=track_length,
                                          album_art_data=album_art_data, track_position=get_track_position())
            window_metadata: dict = {'last_event': None, 'update_listboxes': False, 'update_volume_slider': False,
                                     'library': {'sort_by': 0, 'ascending': True, 'region': 'cell', 'column': 1},
                                     'mouse_hover': '', 'url_input': '', 'pl_url_input': ''}
            pl_name = window_metadata['pl_name'] = next(iter(settings['playlists']), '')
            pl_tracks = window_metadata['pl_tracks'] = settings['playlists'].get(pl_name, []).copy()

            gui_window = Sg.Window('Music Caster', main_gui_layout, grab_anywhere=mini_mode, no_titlebar=mini_mode,
                                   margins=(0, 0), finalize=True, icon=WINDOW_ICON, return_keyboard_events=True,
                                   use_default_focus=False, keep_on_top=mini_mode and settings['mini_on_top'],
                                   location=window_location, metadata=window_metadata, debugger_enabled=is_debug())
            if Shared.using_tcl_theme:
                with suppress(TclError):
                    gui_window.TKroot.tk.call('source', SUN_VALLEY_TCL)
                gui_window.TKroot.tk.call('set_theme', 'dark')
            else:
                Shared.using_tcl_theme = False
            if not settings['mini_mode']:
                gui_window['queue'].update(set_to_index=len(done_queue), scroll_to_index=len(done_queue))
                gui_window['pl_tracks'].update(values=format_pl_lb(pl_tracks))
            set_callbacks()
        elif settings['mini_mode']:
            if selected_tab:
                update_settings('mini_mode', not settings['mini_mode'])
                gui_window.close()
                return activate_gui(selected_tab)
            else:
                # flash border if already in mini mode
                accent = settings['theme']['accent']
                for _ in range(2):
                    gui_window.TKroot.config(background=accent, bd=1)
                    gui_window.read(50)
                    gui_window.TKroot.config(background=accent, bd=0)
                    gui_window.read(50)
        if not settings['mini_mode'] and selected_tab is not None:
            gui_window[selected_tab].select()
            if selected_tab == 'tab_timer': gui_window['timer_input'].set_focus()
            elif selected_tab == 'tab_url':
                gui_window[url_option].update(True)
                gui_window['url_input'].set_focus()
                with suppress(pyperclip.PyperclipException):
                    default_text: str = pyperclip.paste()
                    if default_text.startswith('http'):
                        gui_window['url_input'].update(default_text)
                        gui_window.metadata['url_input'] = default_text
            elif selected_tab == 'tab_playlists':
                with suppress(pyperclip.PyperclipException):
                    default_text: str = pyperclip.paste()
                    if default_text.startswith('http'):
                        gui_window['pl_url_input'].update(default_text)
                        gui_window.metadata['pl_url_input'] = default_text
        with suppress(TclError):
            focus_window(gui_window)


    def locate_uri(selected_track_index=0, uri=None):
        # negative: done_queue
        with suppress(IndexError):
            if uri is None:
                if selected_track_index < 0:
                    uri = done_queue[selected_track_index]
                elif selected_track_index == 0:
                    uri = music_queue[0]
                elif 0 < selected_track_index <= len(next_queue):
                    uri = next_queue[selected_track_index - 1]
                else:
                    uri = music_queue[selected_track_index - len(next_queue)]
            if uri.startswith('http'):
                if uri in url_metadata:
                    uri = url_metadata[uri].get('pl_src', uri)
                Thread(target=webbrowser.open, daemon=True, args=[uri]).start()
                return True
            if os.path.exists(uri):
                if platform.system() == 'Windows':
                    Popen(f'explorer /select,"{fix_path(uri)}"')
                elif platform.system() == 'Linux':
                    try:
                        Popen(['nautilus', uri])
                    except FileNotFoundError:
                        try:
                            # fallback 1
                            Popen(['dolphin', uri])
                        except FileNotFoundError:
                            # fallback 2
                            Popen(['xdg-open', Path(uri).parent])
                return True
        # tray_notify(gt('ERROR') + ':' + gt('Could not locate URI'))
        return False


    def exit_program(quick_exit=False):
        gui_window.close()
        close_tray()
        # stop any active scanning
        with suppress(NameError):
            cast_browser.stop_discovery()
        with suppress(PyChromecastError):
            if cast is None:
                stop('exit program')
            elif cast is not None and cast.app_id == APP_MEDIA_RECEIVER and playing_status.busy():
                cast.quit_app()
        DiscordPresence.close()
        if settings['persistent_queue'] and not quick_exit:
            save_queues()
            with suppress(RuntimeError):
                save_queue_thread.join()
        portalocker.unlock(lock_file)
        sys.exit()


    def playlist_action(playlist_name, action='play'):
        if playlist_name in settings['playlists'] and settings['playlists'][playlist_name]:
            if action == 'play' or action == 'queue':
                if action == 'play':
                    music_queue.clear()
                    done_queue.clear()
                shuffle_from = len(music_queue)
                music_queue.extend(get_audio_uris(playlist_name))
                if settings['shuffle']: better_shuffle(music_queue, shuffle_from)
                if music_queue and (action == 'play' or shuffle_from == 0): play()
            elif 'next':
                next_queue.extend(get_audio_uris(playlist_name))


    def other_tray_actions(_tray_item):
        if _tray_item.startswith('device:'):
            device_uuid = _tray_item[7:]
            with suppress(ValueError): change_device(device_uuid)
        elif _tray_item.startswith('PL:'):  # playlist
            playlist_action(_tray_item[3:])
        elif _tray_item == t('Select Folder'):
            folder_action()
        elif _tray_item.startswith('PF:'):  # play folder
            folder_index = int(re.search(r'\d+', _tray_item).group())
            Thread(target=play_uris, name='PlayFolder', daemon=True, args=[[music_folders[folder_index]]]).start()


    def event_is_close(main_event, main_values):
        ignore_events = {'file_action', 'folder_action', 'pl_add_tracks', 'add_music_folder'}
        return (main_values == Sg.WIN_CLOSED or
                main_event in {'Escape:27', ''} and gui_window.metadata['last_event'] not in ignore_events)

    def read_main_window():
        global track_position, track_start, track_end, timer, music_queue, done_queue
        main_event, main_values = gui_window.read(timeout=100)
        if main_event == 'KeyPress':
            e = gui_window.user_bind_event
            main_event = e.char if e.char else str(e.keysym) + ':' + str(e.keycode)
        if event_is_close(main_event, main_values):
            gui_window.close()
            if settings['gui_exits_app']:
                exit_program()
            return False
        if settings['mini_mode']:
            gui_window.TKroot.update_idletasks()
        main_value = main_values.get(main_event)
        if 'mouse_leave' not in main_event and 'mouse_enter' not in main_event and main_event != Sg.TIMEOUT_KEY:
            gui_window.metadata['last_event'] = main_event
        # update timer text if timer is old
        if not settings['mini_mode'] and timer == 0 and gui_window['timer_text'].metadata:
            gui_window['timer_text'].update('No Timer Set')
            gui_window['timer_text'].metadata = False
            gui_window['cancel_timer'].update(visible=False)
        # these events modify main_event (chain events)
        if main_event.startswith('MouseWheel'):
            main_event = main_event.split(':', 1)[1]
            if gui_window.metadata['mouse_hover'] == 'progress_bar':
                delta = {'Up': settings['scrubbing_delta'], 'Down': -settings['scrubbing_delta']}.get(main_event, 0)
                if playing_status.busy() and track_length is not None:
                    get_track_position()
                    new_position = min(max(track_position + delta, 0), track_length)
                    gui_window['progress_bar'].update(new_position)
                    main_values['progress_bar'] = new_position
                    main_event = 'progress_bar'
            elif gui_window.metadata['mouse_hover'] in {'', 'volume_slider'}:  # not in another scroll view
                delta = {'Up': settings['volume_delta'], 'Down': -settings['volume_delta']}.get(main_event, 0)
                new_volume = min(max(0, main_values['volume_slider'] + delta), 100)
                update_settings('volume', new_volume)
                update_settings('muted', False)
                update_volume(new_volume, 'mouse_wheel')
        elif main_event in {'j', 'l'} and (main_values.get('tab_group', 'tab_queue') == 'tab_queue'):
            if playing_status.busy() and track_length is not None:
                delta = {'j': -settings['scrubbing_delta'], 'l': settings['scrubbing_delta']}[main_event]
                get_track_position()
                new_position = min(max(track_position + delta, 0), track_length)
                gui_window['progress_bar'].update(new_position)
                main_values['progress_bar'] = new_position
                main_event = 'progress_bar'
                gui_window.refresh()
        # override keypress events
        in_tab_queue = main_values.get('tab_group') in {'tab_queue', None}
        if main_event != '__TIMEOUT__':
            with suppress(KeyError):
                el = gui_window.find_element_with_focus()
                if el is not None and el.Key in {'track_format', 'sys_audio_delay'}:
                    main_event, main_value = el.Key, main_values.get(el.Key)
        if main_event == '__TIMEOUT__': pass  # avoids checking multiple if statements
        # change/select tabs
        elif main_event == '1:49' and not settings['mini_mode']:  # Queue tab [Ctrl + 1]
            gui_window['tab_queue'].select()
        elif (main_event == '2:50' and not settings['mini_mode'] or  # URL tab [Ctrl + 2]
              main_event == 'tab_group' and main_values.get('tab_group') == 'tab_url'):
            gui_window['tab_url'].select()
            gui_window['url_input'].set_focus()
            with suppress(pyperclip.PyperclipException):
                default_text: str = pyperclip.paste()
                if default_text.startswith('http'):
                    gui_window['url_input'].update(value=default_text)
        elif (main_event == '3:51' and not settings['mini_mode'] or  # Library tab [Ctrl + 3]:
              main_event == 'tab_group' and main_values['tab_group'] == 'tab_library'):
            gui_window['tab_library'].select()
        elif (main_event == '4:52' and not settings['mini_mode'] or  # Playlists tab [Ctrl + 4]:
              main_event == 'tab_group' and main_values['tab_group'] == 'tab_playlists'):
            with suppress(pyperclip.PyperclipException):
                default_text: str = pyperclip.paste()
                if default_text.startswith('http'):
                    gui_window['pl_url_input'].update(value=default_text)
            gui_window['tab_playlists'].select()
            gui_window['playlist_combo'].set_focus()
        elif (main_event == '5:53' and not settings['mini_mode'] or  # Timer Tab [Ctrl + 5]
              main_event == 'tab_group' and main_values['tab_group'] == 'tab_timer'):
            gui_window['tab_timer'].select()
            gui_window['timer_input'].set_focus()
        elif main_event == '6:54' and not settings['mini_mode']:  # Metadata tab [Ctrl + 6]
            gui_window['tab_metadata'].select()
            gui_window['metadata_file'].set_focus()
        elif main_event == '7:55' and not settings['mini_mode']:  # Settings tab [Ctrl + 7]
            gui_window['tab_settings'].select()
        elif main_event in {'progress_bar_mouse_enter', 'queue_mouse_enter', 'pl_tracks_mouse_enter',
                            'volume_slider_mouse_enter', 'library_mouse_enter'}:
            if main_event in {'progress_bar_mouse_enter', 'volume_slider_mouse_enter'} and settings['mini_mode']:
                gui_window.grab_any_where_off()
            gui_window.metadata['mouse_hover'] = '_'.join(main_event.split('_')[:-2])
        elif main_event in {'progress_bar_mouse_leave', 'queue_mouse_leave', 'pl_tracks_mouse_leave',
                            'volume_slider_mouse_leave', 'library_mouse_leave'}:
            if main_event in {'progress_bar_mouse_leave', 'volume_slider_mouse_leave'} and settings['mini_mode']:
                gui_window.grab_any_where_on()
            if main_event != 'volume_slider_mouse_leave': gui_window.metadata['mouse_hover'] = ''
        elif main_event == 'pause/resume' or main_event == 'k' and in_tab_queue:
            if playing_status.paused(): resume('gui')
            elif playing_status.playing(): pause()
            elif music_queue: play()
            else: play_all()
        elif (main_event == 'next' or main_event == 'N' and in_tab_queue) and playing_status.busy():
            next_track()
        elif (main_event == 'prev' or main_event == 'B' and in_tab_queue) and playing_status.busy():
            prev_track()
        elif main_event == 'devices':
            change_device(main_value.id)
        elif main_event == 'sys_audio_delay':
            with suppress(ValueError):
                update_settings('sys_audio_delay', int(main_value))
        elif main_event == 'track_format':
            update_settings('track_format', main_value)
        elif main_event == 'on_battery_res':
            with suppress(KeyError):
                res = get_all_resolutions()[main_value]
                update_settings('on_battery_res', (res['w'], res['h']))
        elif main_event == 'plugged_in_res':
            with suppress(KeyError):
                res = get_all_resolutions()[main_value]
                update_settings('plugged_in_res', (res['w'], res['h']))
        elif main_event == 'shuffle':
            update_settings('shuffle', not settings['shuffle'])
        elif main_event == 'repeat': cycle_repeat()
        elif (main_event == 'volume_slider' or ((main_event in {'a', 'd'} or main_event.isdecimal())
                                                and in_tab_queue)):
            # User scrubbed volume bar or pressed a, d, #
            try:
                new_volume = int(main_event) * 10
            except ValueError:
                delta = {'a': -settings['volume_delta'], 'd': settings['volume_delta']}.get(main_event, 0)
                new_volume = main_values['volume_slider'] + delta
            update_settings('volume', new_volume)
            # un-mute if volume slider was moved
            update_settings('muted', False)
            update_volume(new_volume, 'volume_slider')
        elif main_event in {'Up:38', 'Down:40'}:
            focused_element = gui_window.FindElementWithFocus()
            if settings['mini_mode'] or focused_element not in {gui_window['queue'], gui_window['pl_tracks'],
                                                                gui_window['music_folders']}:
                delta = settings['volume_delta'] if main_event == 'Up:38' else -settings['volume_delta']
                new_volume = main_values['volume_slider'] + delta
                update_settings('volume', new_volume)
                # un-mute if volume slider was moved
                update_settings('muted', False)
                update_volume(new_volume, 'Up:38')
        elif main_event == 'mute':  # toggle mute
            update_volume(0 if update_settings('muted', not settings['muted']) else settings['volume'], 'mute')
        elif main_event in {'Prior:33', 'Next:34'} and not settings['mini_mode']:  # page up, page down
            focused_element = gui_window.FindElementWithFocus()
            move = {'Prior:33': -3, 'Next:34': 3}[main_event]
            if focused_element == gui_window['queue'] and main_values['queue']:
                new_i = gui_window['queue'].get_indexes()[0] + move
                new_i = min(max(new_i, 0), len(gui_window['queue'].Values) - 1)
                gui_window['queue'].update(set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))
            elif focused_element == gui_window['pl_tracks'] and main_values['pl_tracks']:
                new_i = gui_window['pl_tracks'].get_indexes()[0] + move
                new_i = min(max(new_i, 0), len(gui_window.metadata['pl_tracks']) - 1)
                gui_window['pl_tracks'].update(set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))
        elif main_event == 'queue' and main_value:
            with suppress(ValueError):
                selected_uri_index = gui_window['queue'].get_indexes()[0]
                if selected_uri_index <= len(done_queue):
                    prev_track(times=len(done_queue) - selected_uri_index, forced=True, ignore_timestamps=True)
                else:
                    next_track(times=selected_uri_index - len(done_queue), forced=True, ignore_timestamps=True)
                values = create_track_list()
                dq_len = len(done_queue)
                gui_window['queue'].update(values=values, set_to_index=dq_len, scroll_to_index=dq_len)
        elif main_event == 'album' and playing_status.busy():
            locate_uri()
        elif main_event == 'locate_uri':
            if not settings['mini_mode'] and main_values['queue']:
                for index in gui_window['queue'].get_indexes():
                    locate_uri(index - len(done_queue))
            else: locate_uri()
        elif main_event == 'move_to_next_up':
            for i, index_to_move in enumerate(gui_window['queue'].get_indexes(), 1):
                dq_len = len(done_queue)
                nq_len = len(next_queue)
                if index_to_move < dq_len:
                    track = done_queue[index_to_move]
                    del done_queue[index_to_move]
                    if settings['reversed_play_next']: next_queue.appendleft(track)
                    else: next_queue.append(track)
                    if i == len(main_values['queue']):  # update gui after the last swap
                        values = create_track_list()
                        gui_window['queue'].update(values=values, set_to_index=len(done_queue) + len(next_queue),
                                                   scroll_to_index=max(len(done_queue) + len(next_queue) - 16, 0))
                        save_queues()
                elif index_to_move > dq_len + nq_len:
                    track = music_queue[index_to_move - dq_len - nq_len]
                    del music_queue[index_to_move - dq_len - nq_len]
                    if settings['reversed_play_next']: next_queue.appendleft(track)
                    else: next_queue.append(track)
                    if i == len(main_values['queue']):  # update gui after the last swap
                        values = create_track_list()
                        gui_window['queue'].update(values=values, set_to_index=dq_len + len(next_queue),
                                                   scroll_to_index=max(len(done_queue) + len(next_queue) - 3, 0))
                        save_queues()
        elif main_event == 'move_up':
            for i, index_to_move in enumerate(gui_window['queue'].get_indexes(), 1):
                new_i = index_to_move - 1
                dq_len = len(done_queue)
                nq_len = len(next_queue)
                if index_to_move < dq_len and new_i >= 0:  # move within dq
                    # swap places
                    done_queue[index_to_move], done_queue[new_i] = done_queue[new_i], done_queue[index_to_move]
                elif index_to_move == dq_len and done_queue:  # move index -1 to 1
                    if next_queue:
                        next_queue.insert(1, done_queue.pop())
                    else:
                        music_queue.insert(1, done_queue.pop())
                elif index_to_move == dq_len + 1:  # move 1 to -1
                    if next_queue:
                        done_queue.append(next_queue.popleft())
                    else:
                        track = music_queue[1]
                        del music_queue[1]
                        done_queue.append(track)
                elif next_queue and dq_len < index_to_move <= nq_len + dq_len:  # within next_queue
                    nq_i = new_i - dq_len - 1
                    # swap places, could be more efficient using a custom deque with O(n) swaps instead of O(2n)
                    next_queue[nq_i], next_queue[nq_i + 1] = next_queue[nq_i + 1], next_queue[nq_i]
                elif next_queue and index_to_move == dq_len + nq_len + 1:  # moving into next queue
                    track = music_queue[1]
                    del music_queue[1]
                    next_queue.insert(nq_len - 1, track)
                elif new_i >= 0:  # moving within mq
                    mq_i = new_i - dq_len - nq_len
                    music_queue[mq_i], music_queue[mq_i + 1] = music_queue[mq_i + 1], music_queue[mq_i]
                else:
                    new_i = max(new_i, 0)
                if i == len(main_values['queue']):  # update gui after moving the last selected track
                    values = create_track_list()
                    gui_window['queue'].update(values=values, set_to_index=new_i, scroll_to_index=max(new_i - 7, 0))
                    save_queues()
        elif main_event == 'move_down':
            for i, index_to_move in enumerate(reversed(gui_window['queue'].get_indexes()), 1):
                dq_len, nq_len, mq_len = len(done_queue), len(next_queue), len(music_queue)
                if index_to_move < dq_len + nq_len + mq_len - 1:
                    new_i = index_to_move + 1
                    if index_to_move == dq_len - 1:  # move index -1 to 1
                        if next_queue:
                            next_queue.appendleft(done_queue.pop())
                        else:
                            music_queue.insert(1, done_queue.pop())
                    elif index_to_move < dq_len:  # move within dq
                        done_queue[index_to_move], done_queue[new_i] = done_queue[new_i], done_queue[index_to_move]
                    elif index_to_move == dq_len:  # move 1 to -1
                        if next_queue:
                            done_queue.append(next_queue.popleft())
                        else:
                            track = music_queue[1]
                            del music_queue[1]
                            done_queue.append(track)
                    elif next_queue and index_to_move == dq_len + nq_len:  # moving into music_queue
                        music_queue.insert(2, next_queue.pop())
                    elif index_to_move < dq_len + nq_len + 1:  # within next_queue
                        nq_i = index_to_move - dq_len - 1
                        next_queue[nq_i], next_queue[nq_i - 1] = next_queue[nq_i - 1], next_queue[nq_i]
                    else:  # within music_queue
                        mq_i = new_i - dq_len - nq_len
                        # swap places
                        music_queue[mq_i], music_queue[mq_i - 1] = music_queue[mq_i - 1], music_queue[mq_i]
                    if i == len(main_values['queue']):  # update gui after moving the last selected track
                        values, scroll_to = create_track_list(), max(new_i - 3, 0)
                        gui_window['queue'].update(values=values, set_to_index=new_i, scroll_to_index=scroll_to)
                        save_queues()
        elif main_event == 'remove_track' and main_values['queue']:
            for i, index_to_remove in enumerate(reversed(gui_window['queue'].get_indexes()), 1):
                dq_len, nq_len, mq_len = len(done_queue), len(next_queue), len(music_queue)
                if index_to_remove < dq_len:
                    del done_queue[index_to_remove]
                elif index_to_remove == dq_len:
                    with suppress(IndexError):
                        # remove the "0. XXX" track that could be playing right now
                        music_queue.popleft()
                        if next_queue: music_queue.appendleft(next_queue.popleft())
                        # if queue is empty but repeat is all AND there are tracks in the done_queue
                        if not music_queue and settings['repeat'] is False and done_queue:
                            music_queue.extend(done_queue)
                            done_queue.clear()
                        # start playing new track if a track was being played
                        if not sar.alive:
                            if music_queue and playing_status.busy(): play()
                            else: stop('remove_track')
                elif index_to_remove <= nq_len + dq_len:
                    del next_queue[index_to_remove - dq_len - 1]
                elif index_to_remove < nq_len + mq_len + dq_len:
                    del music_queue[index_to_remove - dq_len - nq_len]
                if i == len(main_values['queue']):  # update gui after the last removal
                    values = create_track_list()
                    new_i = min(len(values), index_to_remove)
                    gui_window['queue'].update(values=values, set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))
        elif main_event == 'select_files':
            Thread(target=file_action, name='FileAction', daemon=True,
                   args=[main_values['fs_action']]).start()
        elif main_event == 'select_folders':
            Thread(target=folder_action, name='FolderAction', daemon=True,
                   args=[main_values['fs_action']]).start()

        elif main_event == 'playlist_action':
            playlist_action(main_values['playlists'])
        elif main_event == 'play_all':
            if not any(filter(lambda thread: thread.name == 'PlayAll', threading.enumerate())):
                Thread(target=play_all, name='PlayAll', daemon=True).start()
        elif main_event == 'queue_all': queue_all()
        elif main_event == 'mini_mode':
            update_settings('mini_mode', not settings['mini_mode'])
            gui_window.close()
            activate_gui()
        elif main_event == 'clear_queue':
            gui_window['queue'].update(values=[])
            if playing_status.busy(): stop('clear_queue')
            music_queue.clear()
            next_queue.clear()
            done_queue.clear()
            save_queues()
        elif main_event == 'save_queue':
            pl_tracks = gui_window.metadata['pl_tracks'] = []
            pl_tracks.extend(done_queue)
            if music_queue: pl_tracks.append(music_queue[0])
            pl_tracks.extend(next_queue)
            pl_tracks.extend(islice(music_queue, 1, None))
            gui_window.metadata['pl_name'] = ''
            gui_window['tab_playlists'].select()
            gui_window['pl_name'].set_focus()
            gui_window['pl_name'].update(value=gui_window.metadata['pl_name'])
            gui_window['pl_tracks'].update(values=format_pl_lb(pl_tracks), set_to_index=0)
        elif main_event in {'library', 'Play::library', 'Play Next::library', 'Queue::library', 'Locate::library'}:
            library_metadata = gui_window.metadata['library']
            if library_metadata['region'] == 'heading':
                col_index = library_metadata['column']
                if col_index == library_metadata['sort_by']:
                    reverse = library_metadata['ascending'] = not library_metadata['ascending']
                else:
                    library_metadata['sort_by'] = col_index
                    reverse = library_metadata['ascending'] = True
                library_items = gui_window['library'].Values
                library_items.sort(key=lambda row: row[col_index - 1].casefold(), reverse=not reverse)
                gui_window['library'].update(library_items)
            elif main_event == 'Locate::library':
                for index in main_values['library']:
                    locate_uri(uri=gui_window['library'].Values[index][-1])
            elif main_values['library']:
                paths_to_play = (gui_window['library'].Values[index][-1] for index in main_values['library'])
                if main_event in {'library', 'Play::library'}:
                    if settings['queue_library']: play_all(paths_to_play)
                    else: play_uris(paths_to_play)
                else:
                    # play_next has priority over queue_uris
                    play_uris(paths_to_play, queue_uris=True, play_next=main_event == 'Play Next::library')
        elif main_event == 'progress_bar' and track_length is not None:
            if playing_status.stopped():
                gui_window['progress_bar'].update(disabled=True, value=0)
                return
            else:
                track_position = main_values['progress_bar']
                set_pos(track_position)
                track_start = time.monotonic() - track_position
                track_end = track_start + track_length
        # main window settings tab
        elif main_event == 'open_email':
            Thread(target=webbrowser.open, daemon=True, args=[create_email_url()]).start()
        elif main_event == 'open_github':
            Thread(target=webbrowser.open, daemon=True, args=['https://github.com/elibroftw/music-caster']).start()
        elif main_event == 'web_gui':
            Thread(target=webbrowser.open, daemon=True, args=[f'http://{get_lan_ip()}:{Shared.PORT}']).start()
        # toggle settings
        elif main_event in TOGGLEABLE_SETTINGS:
            update_settings(main_event, main_value)
            if main_event == 'run_on_startup':
                create_shortcut()
            elif main_event == 'persistent_queue':
                if main_value: save_queues()
                else: update_settings('queues', {'done': [], 'music': [], 'next': []})
                update_settings('populate_queue_startup', False)
                gui_window['populate_queue_startup'].update(value=False)
            elif main_event in 'populate_queue_startup':
                gui_window['persistent_queue'].update(value=False)
                update_settings('persistent_queue', False)
            elif main_event == 'discord_rpc':
                with suppress(Exception):
                    if main_value:
                        if playing_status.busy():
                            metadata = url_metadata['SYSTEM_AUDIO'] if sar.alive else get_uri_metadata(music_queue[0])
                            title, artist = metadata['title'], get_first_artist(metadata['artist'])
                            DiscordPresence.connect()
                            DiscordPresence.update(state=t('By') + f': {artist}', details=title,
                                                   large_text='Listening')
                    elif not main_value:
                        DiscordPresence.clear()
            elif main_event in {'show_album_art', 'vertical_gui', 'flip_main_window'}:
                # re-render main GUI
                gui_window.close()
                activate_gui('tab_settings')
            elif main_event in {'show_track_number', 'show_queue_index'}:
                gui_window.metadata['update_listboxes'] = True
            elif main_event == 'scan_folders' and main_value:
                index_all_tracks()
            elif main_event == 'folder_cover_override':
                size = COVER_MINI if settings['mini_mode'] else COVER_NORMAL
                bg = settings['theme']['background']
                try:
                    album_art_data = resize_img(get_current_art(), bg, size, default_art=DEFAULT_ART)
                except OSError as e:
                    handle_exception(e)
                    album_art_data = resize_img(DEFAULT_ART, bg, size)
                gui_window['artwork'].update(data=album_art_data)
            elif main_event == 'lang':
                Shared.lang = main_value
                gui_window.close()
                activate_gui('tab_settings')
                refresh_tray(True)
        elif main_event == 'remove_music_folder' and main_values['music_folders']:
            with suppress(ValueError):
                for selected_item in main_values['music_folders']:
                    music_folders.remove(selected_item)
                gui_window['music_folders'].update(music_folders)
                refresh_tray()
                save_settings()
                if settings['scan_folders']: index_all_tracks()
        elif main_event == 'add_music_folder':
            initial_folder = settings['last_folder'] if settings['use_last_folder'] else DEFAULT_FOLDER
            folder_path = Sg.popup_get_folder(t('Select Folder'), initial_folder=initial_folder, no_window=True,
                                              icon=WINDOW_ICON)
            if folder_path: add_music_folder([folder_path])
        elif main_event == 'settings_file':
            startfile(SETTINGS_FILE)
        elif main_event == 'changelog_file':
            try:
                if not os.path.exists('CHANGELOG.txt'):
                    raise FileNotFoundError
                startfile('CHANGELOG.txt')
            except FileNotFoundError:
                changelog_url = 'https://github.com/elibroftw/music-caster/blob/master/src/build_files/CHANGELOG.txt'
                Thread(target=webbrowser.open, daemon=True, args=(changelog_url,)).start()
        elif main_event == 'music_folders':
            with suppress(IndexError):
                Popen(f'explorer "{fix_path(main_values["music_folders"][0])}"')
        # url tab
        elif main_event == 'url_input':
            gui_window.metadata['url_input'] = main_value
        elif main_event == 'url_input_cut':
            cut_text = get_cut_text(gui_window, 'url_input')
            if cut_text:
                pyperclip.copy(cut_text)
                gui_window.metadata['url_input'] = gui_window['url_input'].get()
        elif main_event == 'url_input_copy':
            with suppress(TclError):
                pyperclip.copy(gui_window['url_input'].Widget.selection_get())
        elif (main_event in {'\r', 'special 16777220', 'special 16777221', 'url_submit'}
              and main_values.get('tab_group') == 'tab_url' and main_values['url_input']):
            urls_to_insert = main_values['url_input'].strip()
            if '\n' in urls_to_insert: urls_to_insert = urls_to_insert.split('\n')
            else: urls_to_insert = urls_to_insert.split(';')
            gui_window['url_input'].update(value='')
            if main_values['url_play'] or not music_queue:
                music_queue.extendleft(reversed(urls_to_insert))
                gui_window['url_msg'].update(t('Loading URL(s)'), text_color='yellow')
                gui_window.read(1)
                play()
                gui_window['url_msg'].update('')
                urls_to_insert.pop(0)
            elif main_values['url_queue']:
                music_queue.extend(urls_to_insert)
                gui_window['url_msg'].update(t('Added URL(s)'), text_color='green')
                gui_window.TKroot.after(2000, lambda: gui_window['url_msg'].update(value=''))
            else:  # add to next queue
                if settings['reversed_play_next']: next_queue.extendleft(reversed(urls_to_insert))
                else: next_queue.extend(urls_to_insert)
                gui_window['url_msg'].update(t('Added URL(s)'), text_color='green')
                gui_window.TKroot.after(2000, lambda: gui_window['url_msg'].update(value=''))
            for inserted_url in urls_to_insert: uris_to_scan.put(inserted_url)
            gui_window['url_input'].set_focus()
            gui_window.metadata['update_listboxes'] = True
        # timer tab
        elif main_event == 'cancel_timer':
            gui_window['timer_text'].update('No Timer Set')
            gui_window['timer_text'].metadata = False
            gui_window['timer_error'].update(visible=False)
            gui_window['cancel_timer'].update(visible=False)
            cancel_timer()
        # handle enter/submit event
        elif main_event in SUBMIT_EVENTS and main_values.get('tab_group') == 'tab_timer':
            try:
                timer_value: str = main_values['timer_input']
                timer_set_to = set_timer(timer_value)
                gui_window['timer_text'].update(f'Timer set for {timer_set_to}')
                gui_window['timer_text'].metadata = True
                gui_window['cancel_timer'].update(visible=True)
                gui_window['timer_error'].update(visible=False)
                gui_window['timer_input'].update(value='')
                gui_window['timer_input'].set_focus()
            except ValueError:
                # flash timer error
                for _ in range(3):
                    gui_window['timer_error'].update(visible=True, text_color='#ffcccb')
                    gui_window.read(10)
                    gui_window['timer_error'].update(text_color='red')
                    gui_window.read(10)
                gui_window['timer_input'].set_focus()
        elif main_event in {'shut_down', 'hibernate', 'sleep', 'timer_stop'}:
            update_settings('timer_hibernate', main_values['hibernate'])
            update_settings('timer_sleep', main_values['sleep'])
            update_settings('timer_shut_down', main_values['shut_down'])
        # playlists tab
        elif main_event == 'playlist_combo':
            # user selected a playlist from the drop-down
            pl_name = gui_window.metadata['pl_name'] = main_value if main_value in settings['playlists'] else ''
            pl_tracks = gui_window.metadata['pl_tracks'] = settings['playlists'].get(pl_name, []).copy()
            gui_window['pl_name'].update(value=pl_name)
            gui_window['pl_tracks'].update(values=format_pl_lb(pl_tracks), set_to_index=0)
        elif main_event in {'new_pl', 'n:78'}:
            gui_window.metadata['pl_name'] = ''
            gui_window.metadata['pl_tracks'] = []
            gui_window['pl_name'].update(value='')
            gui_window['pl_name'].set_focus()
            gui_window['pl_tracks'].update(values=[])
            gui_window['playlist_combo'].update(value='')
        elif main_event == 'export_pl':
            if main_values['playlist_combo'] and settings['playlists'].get(main_values['playlist_combo']):
                playlist_uris = settings['playlists'][main_values['playlist_combo']]
                playlist_path = export_playlist(main_values['playlist_combo'], playlist_uris)
                locate_uri(uri=playlist_path)
        elif main_event == 'delete_pl':
            pl_name = gui_window.metadata['pl_name'] = main_values.get('playlist_combo', '')
            settings['playlists'].pop(pl_name, None)
            pl_name = gui_window.metadata['pl_name'] = next(iter(settings['playlists']), '')
            gui_window['playlist_combo'].update(value=pl_name, values=tuple(settings['playlists']))
            pl_tracks = gui_window.metadata['pl_tracks'] = settings['playlists'].get(pl_name, []).copy()
            # update playlist editor
            gui_window['pl_name'].update(value=pl_name)
            gui_window['pl_tracks'].update(values=format_pl_lb(pl_tracks), set_to_index=0)
            save_settings()
            refresh_tray()
        elif main_event == 'play_pl':
            temp_lst = settings['playlists'].get(main_values['playlist_combo'], [])
            if temp_lst:
                done_queue.clear()
                music_queue.clear()
                music_queue.extend(temp_lst)
                if settings['shuffle']: shuffle(music_queue)
                play()
        elif main_event == 'queue_pl':
            playlist_action(main_values['playlist_combo'], 'queue')
            gui_window.metadata['update_listboxes'] = True
        elif main_event == 'add_next_pl':
            playlist_action(main_values['playlist_combo'], 'next')
            gui_window.metadata['update_listboxes'] = True
        elif main_event in {'pl_save', 's:83'} and main_values.get('tab_group') == 'tab_playlists':
            # save playlist
            if main_values['pl_name']:
                pl_name = gui_window.metadata['pl_name']
                save_name = main_values['pl_name']
                if pl_name != save_name:
                    # if user is renaming a playlist, remove old data
                    settings['playlists'].pop(pl_name, '')
                    pl_name = gui_window.metadata['pl_name'] = save_name
                settings['playlists'][pl_name] = gui_window.metadata['pl_tracks']
                # sort playlists alphabetically
                playlist_names = sorted(settings['playlists'])
                settings['playlists'] = {k: settings['playlists'][k] for k in playlist_names}
                gui_window['playlist_combo'].update(value=pl_name, values=playlist_names)
            save_settings()
            refresh_tray()
        elif (main_event == 'pl_rm_items' and main_values['pl_tracks']
              and main_values.get('tab_group') == 'tab_playlists'):
            # remove items from playlist
            # remove bottom to top to avoid dynamic indices
            pl_tracks = gui_window.metadata['pl_tracks']
            for i, to_remove in enumerate(reversed(gui_window['pl_tracks'].get_indexes()), 1):
                pl_tracks.pop(to_remove)
                if i == len(main_values['pl_tracks']):  # update gui after the last removal
                    scroll_to_index = max(to_remove - 3, 0)
                    new_values = format_pl_lb(pl_tracks)
                    gui_window['pl_tracks'].update(new_values, set_to_index=to_remove, scroll_to_index=scroll_to_index)
        elif main_event == 'pl_add_tracks':
            initial_folder = settings['last_folder'] if settings['use_last_folder'] else DEFAULT_FOLDER
            file_paths = Sg.popup_get_file('Select Audio Files', no_window=True, initial_folder=initial_folder,
                                           multiple_files=True, file_types=AUDIO_FILE_TYPES, icon=WINDOW_ICON)
            if file_paths:
                pl_tracks = gui_window.metadata['pl_tracks']
                pl_tracks.extend(get_audio_uris(file_paths))
                update_settings('last_folder', os.path.dirname(file_paths[-1]))
                with suppress(TclError):
                    gui_window.TKroot.focus_force()
                    gui_window.normal()
                    new_values = format_pl_lb(pl_tracks)
                    new_i = len(new_values) - 1
                    gui_window['pl_tracks'].update(new_values, set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))
        elif main_event == 'pl_url_input':
            gui_window.metadata['pl_url_input'] = main_value
        elif main_event == 'pl_url_input_cut':
            cut_text = get_cut_text(gui_window, 'pl_url_input')
            if cut_text:
                pyperclip.copy(cut_text)
                gui_window.metadata['pl_url_input'] = gui_window['pl_url_input'].get()
        elif main_event == 'pl_url_input_copy':
            with suppress(TclError):
                pyperclip.copy(gui_window['pl_url_input'].Widget.selection_get())
        elif main_event == 'pl_add_url':
            links = main_values['pl_url_input']
            if '\n' in links: links = links.split('\n')
            else: links = links.split(';')
            for link in links:
                if link.startswith('http://') or link.startswith('https://'):
                    uris_to_scan.put(link)
                    pl_tracks = gui_window.metadata['pl_tracks']
                    pl_tracks.append(link)
                    new_values = format_pl_lb(pl_tracks)
                    new_i = len(new_values) - 1
                    gui_window['pl_tracks'].update(new_values, set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))
                    # empty the input field
                    gui_window['pl_url_input'].update(value='')
                    gui_window['pl_url_input'].set_focus()
                else:
                    tray_notify(t('ERROR') + ': ' + t("Invalid URL. URL's need to start with http:// or https://"))
        elif main_event == 'pl_move_up':
            # only allow moving up if 1 item is selected and pl_files is not empty
            for i, to_move in enumerate(gui_window['pl_tracks'].get_indexes(), 1):
                if to_move:  # can't move the first index up
                    new_i = to_move - 1
                    pl_tracks = gui_window.metadata['pl_tracks']
                    pl_tracks.insert(new_i, pl_tracks.pop(to_move))
                    if i == len(main_values['pl_tracks']):  # update gui after the last swap
                        new_values = format_pl_lb(pl_tracks)
                        gui_window['pl_tracks'].update(new_values, set_to_index=new_i,
                                                       scroll_to_index=max(new_i - 3, 0))
        elif main_event == 'pl_move_down':
            # only allow moving down if 1 item is selected and pl_files is not empty
            for i, to_move in enumerate(gui_window['pl_tracks'].get_indexes(), 1):
                pl_tracks = gui_window.metadata['pl_tracks']
                if to_move < len(pl_tracks) - 1:
                    new_i = to_move + 1
                    pl_tracks.insert(new_i, pl_tracks.pop(to_move))
                    if i == len(main_values['pl_tracks']):  # update gui after the last swap
                        gui_window['pl_tracks'].update(format_pl_lb(pl_tracks), set_to_index=new_i,
                                                       scroll_to_index=max(new_i - 3, 0))
        elif main_event in {'pl_locate_selected', 'pl_tracks'}:
            for i in gui_window['pl_tracks'].get_indexes(): locate_uri(uri=gui_window.metadata['pl_tracks'][i])
        elif main_event in {'play_pl_selected', 'queue_pl_selected', 'add_next_pl_selected'}:
            uris = (gui_window.metadata['pl_tracks'][i] for i in gui_window['pl_tracks'].get_indexes())
            play_uris(uris, queue_uris=main_event == 'queue_pl_selected',
                      play_next=main_event == 'add_next_pl_selected', natural_sort=settings['shuffle'])
        # metadata editor tab
        elif main_event in {'metadata_browse', 'metadata_file'}:
            initial_folder = settings['last_folder'] if settings['use_last_folder'] else DEFAULT_FOLDER
            selected_file = Sg.popup_get_file('Select audio file', initial_folder=initial_folder, no_window=True,
                                              file_types=AUDIO_FILE_TYPES, icon=WINDOW_ICON)
            metadata_process_file(selected_file)
        elif main_event == 'metadata_select_art' and gui_window['metadata_file'].get():
            selected_file = Sg.popup_get_file('Select image/audio file', no_window=True,
                                              file_types=IMG_FILE_TYPES, icon=WINDOW_ICON)
            if selected_file:
                if os.path.splitext(selected_file)[1][1:].casefold() in AUDIO_EXTS:
                    mime, artwork = get_album_art(selected_file, settings['folder_cover_override'])
                else:
                    img = Image.open(selected_file).convert('RGB')
                    data = io.BytesIO()
                    img.save(data, format='jpeg', quality=95)
                    mime, artwork = 'image/jpeg', b64encode(data.getvalue()).decode()
                art_metadata = (mime, None if artwork == DEFAULT_ART else artwork)
                _, display_art = gui_window['metadata_art'].metadata = art_metadata
                if display_art is not None:
                    display_art = resize_img(display_art, settings['theme']['background'], COVER_MINI)
                gui_window['metadata_art'].update(data=display_art)
        elif main_event == 'metadata_search_art' and gui_window['metadata_file'].get():
            # search for artwork using spotify API
            gui_window['metadata_msg'].update(value=t('Searching for artwork...'), text_color='yellow')
            found_artwork = False
            for mkt in {'MX', 'CA', 'US', 'UK', 'HK'}:
                title = main_values['metadata_title']
                artist = main_values['metadata_artist']
                url = f'https://api.spotify.com/v1/search?q={title}'
                if artist: url += f'+artist:{artist}'
                url += f'&type=track&market={mkt}'
                r = requests.get(url, headers=get_spotify_headers()).json()
                if 'tracks' in r:
                    for art_link in (item['album']['images'][0]['url'] for item in r['tracks']['items']):
                        display_art = base64.b64encode(requests.get(art_link).content).decode()
                        gui_window['metadata_art'].metadata = ('image/jpeg', display_art)
                        display_art = resize_img(display_art, settings['theme']['background'], COVER_MINI)
                        gui_window['metadata_art'].update(data=display_art)
                        found_artwork = True
                        break
            if found_artwork:
                gui_window['metadata_msg'].update(value=t('Artwork found'), text_color='green')
                gui_window.TKroot.after(2000, lambda: gui_window['metadata_msg'].update(value=''))
            else:
                gui_window['metadata_msg'].update(value=t('No artwork found'), text_color='red')
                gui_window.TKroot.after(2000, lambda: gui_window['metadata_msg'].update(value=''))
        elif main_event == 'metadata_remove_art':
            gui_window['metadata_art'].metadata = (None, None)
            gui_window['metadata_art'].update(data=None)
        elif main_event in {'metadata_save', 's:83'} and main_values.get('tab_group') == 'tab_metadata':
            if gui_window['metadata_file'].get():
                mime, art = gui_window['metadata_art'].metadata
                new_metadata = {'title': main_values['metadata_title'], 'artist': main_values['metadata_artist'],
                                'album': main_values['metadata_album'], 'explicit': main_values['metadata_explicit'],
                                'track_number': main_values['metadata_track_num'], 'mime': mime, 'art': art}
                gui_window['metadata_msg'].update(value=t('Saving metadata'), text_color='yellow')
                try:
                    set_metadata(gui_window['metadata_file'].get(), new_metadata)
                    gui_window['metadata_msg'].update(value=t('Metadata saved'), text_color='green')
                except Exception as e:  # e.g. ValueError track number incorrectly entered
                    print(repr(e))
                    error = t('ERROR') + ': ' + repr(e)
                    gui_window['metadata_msg'].update(value=error, text_color='red')
                gui_window.TKroot.after(2000, lambda: gui_window['metadata_msg'].update(value=''))
                gui_window['title'].update(' ' + gui_window['title'].DisplayText + ' ')  # try updating now playing
        elif main_event == 'exit_program':
            exit_program()
        # other GUI updates
        if gui_window.metadata['update_listboxes'] and not settings['mini_mode']:
            gui_window.metadata['update_listboxes'] = False
            dq_len = len(done_queue)
            lb_tracks = create_track_list()
            gui_window['queue'].update(values=lb_tracks, set_to_index=dq_len, scroll_to_index=dq_len)
            pl_tracks = gui_window.metadata['pl_tracks']
            gui_window['pl_tracks'].update(values=format_pl_lb(pl_tracks))
            if len(all_tracks) != len(gui_window['library'].Values):
                lib_data = [[track['title'], get_first_artist(track['artist']), track['album'], uri] for uri, track in
                            index_all_tracks(False).items()]
                gui_window['library'].update(values=lib_data)
        if gui_window.metadata['update_volume_slider']:
            gui_window['mute'].update(image_data=VOLUME_MUTED_IMG if settings['muted'] else VOLUME_IMG)
            gui_window['mute'].set_tooltip(t('unmute') if settings['muted'] else t('mute'))
            gui_window['volume_slider'].update(0 if settings['muted'] else settings['volume'])
            gui_window.metadata['update_volume_slider'] = False
        # update progress bar
        progress_bar: Sg.Slider = gui_window['progress_bar']
        time_elapsed_text, time_left_text = create_progress_bar_text(get_track_position(), track_length)
        if time_elapsed_text != gui_window['time_elapsed'].get(): gui_window['time_elapsed'].update(time_elapsed_text)
        if time_left_text != gui_window['time_left'].get(): gui_window['time_left'].update(time_left_text)
        if music_queue and playing_status.busy() and not sar.alive: progress_bar.update(floor(track_position))
        return True


    def create_shortcut():
        """ Creates short-cut in Startup folder (enter "startup" in Explorer address bar to)
            if setting['run_on_startup'], else removes existing shortcut """
        if platform.system() == 'Windows':
            Thread(target=create_shortcut_windows, name='CreateShortcut',
                   args=(is_debug(), IS_FROZEN, settings['run_on_startup'], working_dir)).start()
        else:
            print('TODO: create_shortcut not implemented for', platform.system())

    def auto_update():
        """ auto_start should be True when checking for updates at startup up,
            false when checking for updates before exiting """
        with suppress(requests.RequestException):
            app_log.info(f'called auto_update(), IS_FROZEN={IS_FROZEN}')
            release = get_latest_release(VERSION, VERSION, force=(not IS_FROZEN or is_debug()))
            if release:
                latest_ver = release['version']
                setup_dl_link = release['setup']
                app_log.info(f'Update found: v{latest_ver}')
                print('Installer Link:', setup_dl_link)
                if int(VERSION.split('.', 1)[0]) < int(latest_ver.split('.', 1)[0]):
                    if not is_os_64bit():
                        tray_notify(f"The update v{latest_ver}, is 64-bit only")
                        tray_notify("I've turned off auto-update for you, so you don't have to worry")
                        return update_settings('auto_update', False)
                if is_debug() or not setup_dl_link:
                    return app_log.info(f'Not updating because: DEBUG: {DEBUG} or not setup_dl_link={setup_dl_link}')
                if IS_FROZEN:
                    if platform.system() in {'Linux', 'Darwin'}:
                        tray_notify('update_available', context=latest_ver)
                    elif os.path.exists(UNINSTALLER):
                        # only show message on startup to not confuse the user
                        cmd = ['mc_installer.exe', '/VERYSILENT', '/FORCECLOSEAPPLICATIONS',
                               '/MERGETASKS="!desktopicon"', '&&', 'Music Caster.exe']
                        cmd.extend(sys.argv[1:])
                        # cmd = 'mc_installer.exe /VERYSILENT /FORCECLOSEAPPLICATIONS /MERGETASKS="!desktopicon"'
                        # cmd_args = ' '.join(sys.argv[1:])
                        # cmd += f' && "Music Caster.exe" {cmd_args}'  # auto start is True when updating on startup
                        if gui_window.was_closed() and not args.minimized:
                            cmd.append('-m')
                            # cmd += ' -m'
                        download_update = t('Downloading update $VER').replace('$VER', latest_ver)
                        tray_notify(download_update)
                        tray_tooltip = download_update
                        tray_process_queue.put({'tooltip': tray_tooltip})
                        try:
                            # download setup, close tray, run setup, and exit
                            download(setup_dl_link, 'mc_installer.exe')
                            tray_notify(t('Update downloaded, restarting now'))
                            time.sleep(0.3)
                            Popen(cmd, shell=True)
                            daemon_commands.put('__EXIT__')  # tell main thread to exit
                        except OSError as e:
                            if e.errno == errno.ENOSPC:
                                tray_notify(t('ERROR') + ': ' + t('No space left on device to auto-update'))
                        except Exception:
                            tray_notify('update_available', context=latest_ver)
                    elif os.path.exists('Updater.exe'):
                        # portable installation
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
            else:
                app_log.info(f'auto_update: no update found, or no internet, or API rate limited')

    def send_info():
        with suppress(requests.RequestException):
            mac = hashlib.md5(get_mac().encode()).hexdigest()
            requests.post('https://en3ay96poz86qa9.m.pipedream.net', json={'MAC': mac, 'VERSION': VERSION})


    def cast_monitor(msg: dict = None):
        global track_position, track_start, track_end
        if cast is None:
            return
        try:
            if msg is None and playing_status.busy():
                # block/monitor in background thread
                return cast.media_controller.update_status(callback_function_param=cast_monitor)
            if cast.app_id == APP_MEDIA_RECEIVER:
                with cast_monitor_lock:
                    media_controller = cast.media_controller
                    is_stopped = media_controller.status.player_is_idle
                    is_live = track_length is None
                    if not is_stopped and playing_status.busy():
                        # sync track position with chromecast, also allows scrubbing from external apps
                        with suppress(IndexError):
                            buffer = 2 if music_queue[0].startswith('http') else 0.5
                            if abs(media_controller.status.adjusted_current_time - track_position) > buffer:
                                track_position = media_controller.status.adjusted_current_time
                                track_start = time.monotonic() - track_position
                                if not is_live: track_end = track_start + track_length
                    if media_controller.status.player_is_paused and playing_status.playing():
                        pause('cast_monitor')
                    elif media_controller.status.player_is_playing and playing_status.paused():
                        resume('cast_monitor')
                    elif (is_stopped and playing_status.busy() and
                          not is_live and time.monotonic() - track_end > 1):
                        # if cast says nothing is playing, only stop if we are not at the end of the track
                        #  this will prevent false positives
                        stop('cast_monitor', False)
                    cast_volume = round(cast.status.volume_level * 100, 1)
                    if settings['volume'] != cast_volume:
                        if not settings['muted'] and (not isinstance(settings['volume'], (float, int)) or
                                                      abs(settings['volume'] - cast_volume) > 0.05):
                            # if volume was changed via Google Home App
                            if update_settings('volume', cast_volume) and settings['muted']:
                                update_settings('muted', False)
                            gui_window.metadata['update_volume_slider'] = True
            elif playing_status.playing() and cast.media_controller.is_idle:
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


    def handle_action(action):
        actions = {
            '__ACTIVATED__': activate_gui,
            '__UPDATE_GUI__': update_gui,
            '__EXIT__': exit_program,
            # from tray menu
            t('Exit'): exit_program,
            t('Rescan Library'): index_all_tracks,
            t('Refresh Devices'): lambda: refresh_tray(True),
            # isdigit should be an if statement
            t('Settings'): lambda: activate_gui('tab_settings'),
            t('Playlists Tab'): lambda: activate_gui('tab_playlists'),
            # PL should be an if statement
            t('Set Timer'): lambda: activate_gui('tab_timer'),
            t('Cancel Timer'): cancel_timer,
            t('System Audio'): play_system_audio,
            t('Play URL'): lambda: activate_gui('tab_url', 'url_play'),
            t('Queue URL'): lambda: activate_gui('tab_url', 'url_queue'),
            t('Play URL Next'): lambda: activate_gui('tab_url', 'url_play_next'),
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
        if settings['update_message'] == '': tray_notify(WELCOME_MSG)
        elif settings['update_message'] != UPDATE_MESSAGE and settings['notifications']: tray_notify(UPDATE_MESSAGE)
        # show important information regardless of notification settings
        update_settings('update_message', UPDATE_MESSAGE)

        # set file handlers only if installed from the setup (Not a portable installation)
        if os.path.exists(UNINSTALLER):
            with suppress(PermissionError):
                add_reg_handlers(f'{working_dir}/Music Caster.exe', add_folder_context=settings['folder_context_menu'])

        with suppress(FileNotFoundError, OSError): os.remove('mc_installer.exe')
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
        # find a port to bind to
        socket_timeout = 0.5 if args.shell else 0.1
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s1, \
                    socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s2:
                s1.settimeout(socket_timeout), s2.settimeout(socket_timeout)
                # check if ports are not occupied
                if s1.connect_ex(('127.0.0.1', Shared.PORT)) != 0 and s2.connect_ex(('::1', Shared.PORT)) != 0:
                    # if ports are not occupied
                    with suppress(OSError):
                        # try to start server and bind it to PORT
                        if platform.system() == 'Windows':
                            server_kwargs = {'host': '0.0.0.0', 'port': Shared.PORT, 'threaded': True}
                            Thread(target=app.run, name='FlaskServer', daemon=True, kwargs=server_kwargs).start()
                        # Linux maps ipv4 to ipv6
                        server_kwargs = {'host': '::', 'port': Shared.PORT, 'threaded': True}
                        Thread(target=app.run, name='FlaskServer', daemon=True, kwargs=server_kwargs).start()
                        break
                Shared.PORT += 1  # port in use or failed to bind to port
        with suppress(PermissionError):
            if is_debug:
                # only want to store PID of original instance
                lock_file.read()
            create_pid_file(port=Shared.PORT)
        tray_process = mp.Process(target=system_tray, name='Music Caster Tray',
                                  args=(daemon_commands, tray_process_queue), daemon=True)
        tray_process.start()
        print(f'Running on http://127.0.0.1:{Shared.PORT}/')
        print(f'Running on http://[::1]:{Shared.PORT}/')
        app_log.info(f'LAN IPV4: http://{get_ipv4()}:{Shared.PORT}/')
        try:
            app_log.info(f'LAN IPV6: http://{get_ipv6()}:{Shared.PORT}/')
        except StopIteration:
            app_log.info('Could not get LAN IPV6 address')
        DiscordPresence.connect(settings['discord_rpc'])
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
        # open window if minimized argument not given
        if not args.minimized and not settings.get('DEBUG', False):
            daemon_commands.put('__ACTIVATED__')
        TIME_TO_START = time.monotonic() - start_time
        app_log.info(f'Time to start (excluding imports) is {TIME_TO_START:.2f} seconds')
        app_log.info(f'Time to start (including imports) is {TIME_TO_START + TIME_TO_IMPORT:.2f} seconds')
        last_position_save = time.monotonic()
        while True:
            while not daemon_commands.empty(): handle_action(daemon_commands.get())
            if playing_status.playing() and track_length is not None and time.monotonic() > track_end:
                next_track(from_timeout=time.monotonic() > track_end)
            elif timer and time.time() > timer:
                stop('timer')
                timer = 0
                # use lock to prevent corrupting settings
                with settings_file_lock:
                    if settings['timer_shut_down']:  # shutdown computer
                        os.system('shutdown /p /f') if platform.system() == 'Windows' else os.system('shutdown -h now')
                    elif settings['timer_hibernate']: # hibernate computer
                        if platform.system() == 'Windows': os.system(r'rundll32.exe powrprof.dll,SetSuspendState Hibernate')
                    elif settings['timer_sleep']: # sleep computer
                        if platform.system() == 'Windows': os.system('rundll32.exe powrprof.dll,SetSuspendState 0,1,0')
            # if settings.json was updated outside of Music Caster, reload settings
            try:
                if os.path.getmtime(SETTINGS_FILE) != settings_last_modified: load_settings()
            except FileNotFoundError:
                load_settings(first_load=True)
            if settings['persistent_queue'] and time.monotonic() - last_position_save > 2.5:
                update_settings('position', get_track_position())
                last_position_save = time.monotonic()
            if cast is not None:
                cast_monitor()
            if platform.system() == 'Windows':
                try:
                    if settings['on_battery_res'] != settings['plugged_in_res']:
                        user32 = ctypes.windll.user32
                        res_map = get_all_resolutions()
                        if is_plugged_in(throw_error=False):
                            plugged_in_info = res_map[fmt_res(*settings['plugged_in_res'])]
                            if user32.GetSystemMetrics(0) * plugged_in_info['dpi_scale'] != settings['plugged_in_res'][0]:
                                refresh_rate = max(get_all_refresh_rates())
                                set_resolution(plugged_in_info['w'], plugged_in_info['h'], plugged_in_info['dpi_scale'], refresh_rate=refresh_rate)
                                refresh_tray_icon()
                        else:  # on battery
                            on_battery_info = res_map[fmt_res(*settings['on_battery_res'])]
                            if user32.GetSystemMetrics(0) * on_battery_info['dpi_scale'] != settings['on_battery_res'][0]:
                                refresh_rate = 60 if 60 in get_all_refresh_rates() else min(get_all_refresh_rates())
                                set_resolution(on_battery_info['w'], on_battery_info['h'], on_battery_info['dpi_scale'], refresh_rate=refresh_rate)
                                refresh_tray_icon()
                except KeyError:
                    update_settings('plugged_in_res', get_initial_res())
                    update_settings('on_battery_res', get_initial_res())
                    tray_notify(t('ERROR') + ': ' + t('Could not set resolution'))
            time.sleep(0.2) if gui_window.was_closed() else read_main_window()
    except KeyboardInterrupt:
        exit_program()
    except Exception as exception:
        app_log.info(f'FATAL exception detected: {exception}')
        # try to auto-update before exiting
        if not settings.get('DEBUG', False): auto_update()
        handle_exception(exception, True)
