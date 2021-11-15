# Important note: Discord RPC has been disabled
#   Affected code: load_settings, helpers.create_settings
VERSION = latest_version = '4.90.108'
UPDATE_MESSAGE = """
[Feature] Ctrl + (Shift) + }
[HELP] Could use some translators
""".strip()
import argparse
from contextlib import suppress
from itertools import islice
# noinspection PyUnresolvedReferences
import io
import multiprocessing as mp
import os
from queue import Queue
# noinspection PyUnresolvedReferences
import re
# noinspection PyUnresolvedReferences
import requests
import sys
import threading
from subprocess import Popen, PIPE, DEVNULL
from urllib.request import pathname2url
from inspect import currentframe, getframeinfo


parser = argparse.ArgumentParser(description='Music Caster')
parser.add_argument('--debug', '-d', default=False, action='store_true', help='allows > 1 instance + no info sent')
parser.add_argument('--queue', '-q', default=False, action='store_true', help='paths are queued')
parser.add_argument('--playnext', '-n', default=False, action='store_true', help='paths are added to next up')
parser.add_argument('--urlprotocol', '-p', default=False, action='store_true', help='launched using uri protocol')
parser.add_argument('--update', '-u', default=False, action='store_true', help='allow updating')
parser.add_argument('--exit', '-x', default=False, action='store_true',
                    help='exits any existing instance (including self)')
parser.add_argument('--minimized', '-m', default=False, action='store_true', help='start minimized to tray')
parser.add_argument('uris', nargs='*', default=[], help='list of files/dirs/playlists/urls to play/queue')
parser.add_argument('--version', '-v', default=False, action='store_true', help='returns the version')
parser.add_argument('--resume-playback', '-r', default=False, action='store_true', help='play if tracks in queue')
parser.add_argument('--start-playing', default=False, action='store_true', help='resume or shuffle play all')
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
UNINSTALLER = 'unins000.exe'
WAIT_TIMEOUT, IS_FROZEN = 15, getattr(sys, 'frozen', False)
daemon_commands, tray_process_queue, uris_to_scan = mp.Queue(), mp.Queue(), Queue()


def get_running_processes(look_for=''):
    cmd = f'tasklist /NH /FI "IMAGENAME eq {look_for}"' if look_for else f'tasklist /NH'
    p = Popen(cmd, shell=True, stdout=PIPE, stdin=DEVNULL, stderr=DEVNULL, text=True)
    p.stdout.readline()
    for task in iter(lambda: p.stdout.readline().strip(), ''):
        m = re.match(r'(.+?) +(\d+) (.+?) +(\d+) +(\d+.* K).*', task)
        if m is not None:
            yield {'name': m.group(1), 'pid': int(m.group(2)), 'session_name': m.group(3),
                   'session_num': m.group(4), 'mem_usage': m.group(5)}


def is_already_running(look_for='Music Caster.exe', threshold=1):
    for process in get_running_processes(look_for=look_for):
        if process['name'] == look_for:
            threshold -= 1
            if threshold < 0: return True
    return False


def system_tray(main_queue: mp.Queue, child_queue: mp.Queue):
    from b64_images import FILLED_ICON, UNFILLED_ICON, b64decode
    from PIL import Image
    import pystray
    import time
    filled_icon = Image.open(io.BytesIO(b64decode(FILLED_ICON)))
    unfilled_icon = Image.open(io.BytesIO(b64decode(UNFILLED_ICON)))

    def create_menu(lst, root=True):
        # e.g. ['Item 1', ('Item 2 Display', 'item_2_key'), ['Sub Menu Title', ('Sub Menu Item 1 Display', 'KEY')]]
        # TODO: checked/radio
        items = []
        if root: items.append(pystray.MenuItem('', on_tray_click('__ACTIVATED__'), default=True, visible=False))
        for element in lst:
            if type(element) == list:
                items.append(pystray.MenuItem(element[0], create_menu(islice(element, 1, None), root=False)))
            elif type(element) == tuple and len(element) == 2:
                element, key = element
                items.append(pystray.MenuItem(element, on_tray_click(element, key)))
            else:
                items.append(pystray.MenuItem(element, on_tray_click(element)))
        return pystray.Menu(*items)

    def on_tray_click(string, key=''):
        if key == 'exit':  # special case to end the tray
            first_fn = on_tray_click(string)
            return lambda: first_fn() and child_queue.put({'close': None})
        return lambda: (main_queue.put(key) if key else main_queue.put(string))

    def background():
        while True:
            while not child_queue.empty():
                for parent_cmd, arguments in child_queue.get().items():
                    if parent_cmd == 'tooltip':
                        tray.title = arguments
                    elif parent_cmd == 'menu':  # set icon to unfilled
                        tray.menu = create_menu(arguments)
                        tray.update_menu()
                    elif parent_cmd == 'filled':  # set icon to filled
                        tray.icon = filled_icon
                    elif parent_cmd == 'unfilled':  # set icon to unfilled
                        tray.icon = unfilled_icon
                    elif parent_cmd == 'notify':
                        tray.notify(arguments['message'], title=arguments.get('title'))  # msg, title
                    elif parent_cmd == 'hide':
                        tray.visible = False
                    elif parent_cmd == 'close':
                        tray.stop()
            time.sleep(0.1)
    tray = pystray.Icon('Music Caster SystemTray', unfilled_icon, title='Music Caster [LOADING]')
    threading.Thread(target=background, daemon=True).start()
    tray.run()


def activate_instance(port):
    r_text = ''
    while port <= 2004 and not r_text:
        with suppress(requests.RequestException):
            endpoint = f'http://127.0.0.1:{port}'
            if args.exit:  # --exit argument
                r_text = requests.post(f'{endpoint}/exit/').text
            elif args.uris:  # MC was supplied at least one path to a folder/file
                data = {'uris': args.uris, 'queue': args.queue, 'play_next': args.playnext}
                r_text = requests.post(f'{endpoint}/play/', data=data).text
            else:  # neither --exit nor paths was supplied
                r_text = requests.post(f'{endpoint}?activate').text
        port += 1
    return not not r_text


if __name__ == '__main__':
    mp.freeze_support()
    # if the (exact) program is already running, open the running GUI and exit this instance
    #   running a portable version after running an installed version won't open up the second GUI
    try:
        with suppress(FileNotFoundError): os.remove('music_caster.log')
        # if an instance is already running, open that one's GUI and exit this instance
        if is_already_running(threshold=1 if os.path.exists(UNINSTALLER) else 2): raise PermissionError
    except PermissionError:
        # if music_caster.log can't be opened, its being used by an existing Music Caster process
        if IS_FROZEN and not DEBUG:
            activate_instance(2001)
            sys.exit()
    if args.exit: sys.exit()
    tray_process = mp.Process(target=system_tray, args=(daemon_commands, tray_process_queue), daemon=True)
    tray_process.start()


from helpers import *
from audio_player import AudioPlayer
import base64
from contextlib import suppress
from collections import defaultdict, deque
from collections.abc import Iterable
from copy import deepcopy
from datetime import datetime, timedelta
import errno
# noinspection PyUnresolvedReferences
import encodings.idna  # DO NOT REMOVE
from functools import cmp_to_key
import glob
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
from math import log10
from pathlib import Path
import pprint
from random import shuffle
from shutil import copyfileobj, rmtree
from win32com.universal import com_error
import traceback
import urllib.parse
from urllib.parse import urlsplit
import webbrowser  # takes 0.05 seconds
import zipfile
# 3rd party imports
from Cryptodome.Cipher import Blowfish
from flask import Flask, jsonify, render_template, request, redirect, send_file, Response, make_response
from werkzeug.exceptions import InternalServerError
import pychromecast.controllers.media
from pychromecast.error import UnsupportedNamespace, NotConnected
from pychromecast.config import APP_MEDIA_RECEIVER
from pychromecast import Chromecast
import pynput.keyboard
import pyperclip
import pypresence
import pythoncom
from PIL import UnidentifiedImageError
from TkinterDnD2 import DND_FILES, DND_ALL
import tkinter
from urllib3.exceptions import ProtocolError
import win32com.client
from win32comext.shell import shell, shellcon
from youtube_dl.utils import DownloadError

main_window = Sg.Window('', metadata={})
main_window.close()
working_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
os.chdir(working_dir)
WELCOME_MSG = gt('Thanks for installing Music Caster.') + '\n' + \
              gt('Music Caster is running in the tray.')
STREAM_CHUNK = 1024
MUSIC_CASTER_DISCORD_ID = '696092874902863932'
EMAIL = 'elijahllopezz@gmail.com'
AUDIO_EXTS = ('mp3', 'mp4', 'mpeg', 'm4a', 'flac', 'aac', 'ogg', 'opus', 'wma', 'wav')
AUDIO_FILE_TYPES = (('Audio File', '*.' + ' *.'.join(AUDIO_EXTS) + ' *.m3u *.m3u8'),)
IMG_FILE_TYPES = (('Image', '*.gif *.pdf *.png *.tiff *.webp *.' + ' *.'.join(AUDIO_EXTS)),)
SETTINGS_FILE = 'settings.json'
PRESSED_KEYS = set()
settings_file_lock = threading.Lock()
last_play_command = settings_last_modified = 0
update_last_checked = time.time()  # check every hour
# noinspection PyTypeChecker
cast: Chromecast = None
all_tracks, url_metadata, all_tracks_sorted = {}, {}, []
tray_playlists = [gt('Playlists Menu')]
CHECK_MARK = '✓'
music_folders, chromecasts, device_names = [], [], [(f'{CHECK_MARK} ' + gt('Local device'), 'device:0')]
music_queue, done_queue, next_queue = deque(), deque(), deque()
playing_url = deezer_opened = False
# seconds but using time()
track_position = timer = track_end = track_length = track_start = 0
DEFAULT_FOLDER = home_music_folder = (Path.home() / 'Music').as_posix()
DEFAULT_THEME = {'accent': '#00bfff', 'background': '#121212', 'text': '#d7d7d7', 'alternate_background': '#222222'}
settings = {  # default settings
    'previous_device': None, 'window_locations': {}, 'update_message': '', 'smart_queue': False, 'skips': {},
    'auto_update': True, 'run_on_startup': os.path.exists(UNINSTALLER), 'notifications': True, 'shuffle': False, 'repeat': None,
    'discord_rpc': False, 'save_window_positions': True, 'populate_queue_startup': False, 'persistent_queue': False,
    'volume': 50, 'muted': False, 'volume_delta': 5, 'scrubbing_delta': 5, 'flip_main_window': False,
    'show_track_number': False, 'folder_cover_override': False, 'show_album_art': True, 'folder_context_menu': True,
    'vertical_gui': False, 'mini_mode': False, 'mini_on_top': True, 'scan_folders': True, 'update_check_hours': 1,
    'timer_shut_down': False, 'timer_hibernate': False, 'timer_sleep': False, 'show_queue_index': True,
    'queue_library': False, 'lang': '', 'theme': DEFAULT_THEME.copy(), 'use_last_folder': False, 'upload_pw': '',
    'last_folder': DEFAULT_FOLDER, 'track_format': '&artist - &title', 'reversed_play_next': False, 'delay': 0,
    'music_folders': [DEFAULT_FOLDER], 'playlists': {}, 'queues': {'done': [], 'music': [], 'next': []}}
default_settings = deepcopy(settings)
indexing_tracks_thread = save_queue_thread = Thread()
playing_status = PlayingStatus()
sar = SystemAudioRecorder()
app = Flask(__name__)
app.jinja_env.lstrip_blocks = app.jinja_env.trim_blocks = True
logging.getLogger('werkzeug').disabled = not DEBUG
os.environ['WERKZEUG_RUN_MAIN'] = 'true'
os.environ['FLASK_SKIP_DOTENV'] = '1'
stop_discovery_browser = None


def get_linenumber():
    cf = currentframe()
    return cf.f_back.f_lineno


def tray_notify(message, title='Music Caster', context=''):
    if message == 'update_available':
        message = gt('Update $VER is available').replace('$VER', f'v{context}')
    # wrapper for tray_process_queue
    tray_process_queue.put({'notify': {'message': message, 'title': title}})


def close_tray():
    tray_process_queue.put({'close': None})
    tray_process.join()


def save_settings():
    global settings_last_modified
    with settings_file_lock:
        try:
            with open(SETTINGS_FILE, 'w') as outfile:
                json.dump(settings, outfile, indent=2)
            settings_last_modified = os.path.getmtime(SETTINGS_FILE)
        except OSError as e:
            if e.errno == errno.ENOSPC:
                tray_notify(gt('ERROR') + ': ' + gt('No space left on device to save settings'))
            else:
                tray_notify(gt('ERROR') + f': {e}')


def cast_wait():
    with suppress(AttributeError, RuntimeError):
        cast.wait(timeout=WAIT_TIMEOUT)


def refresh_tray():
    tray_folders = [gt('Select Folder(s)')]
    for i, folder in enumerate(music_folders):
        folder = Path(folder)
        folder = ('../' + '/'.join(folder.parts[-2:])) if len(folder.parts) > 2 else folder.as_posix()
        tray_folders.append((folder, f'PF:{i}'))
    repeat_menu = [gt('Repeat All') + f' {CHECK_MARK}' * (settings['repeat'] is False),
                   gt('Repeat One') + f' {CHECK_MARK}' * (settings['repeat'] is True),
                   gt('Repeat Off') + f' {CHECK_MARK}' * (settings['repeat'] is None)]
    tray_menu_default = [gt('Settings'), gt('Rescan Library'), gt('Refresh Devices'),
                         [gt('Select Device'), *device_names], [gt('Timer'), gt('Set Timer'), gt('Cancel Timer')],
                         [gt('Play'), gt('System Audio'),
                          [gt('URL'), gt('Play URL'), gt('Queue URL'), gt('Play URL Next')],
                          [gt('Folders'), *tray_folders], [gt('Playlists'), *tray_playlists],
                          [gt('Select File(s)'), gt('Play File(s)'), gt('Queue File(s)'), gt('Play File(s) Next')],
                          gt('Play All')], (gt('Exit'), 'exit')]
    tray_menu_playing = [gt('Settings'), gt('Rescan Library'), gt('Refresh Devices'),
                         [gt('Select Device'), *device_names], [gt('Timer'), gt('Set Timer'), gt('Cancel Timer')],
                         [gt('Controls'), gt('locate track', 1), [gt('Repeat Options'), *repeat_menu], gt('Stop'),
                          gt('previous track', 1), gt('next track', 1), gt('Pause')],
                         [gt('Play'), gt('System Audio'),
                          [gt('URL'), gt('Play URL'), gt('Queue URL'), gt('Play URL Next')],
                          [gt('Folders'), *tray_folders], [gt('Playlists'), *tray_playlists],
                          [gt('Select File(s)'), gt('Play File(s)'), gt('Queue File(s)'), gt('Play File(s) Next')],
                          gt('Play All')], (gt('Exit'), 'exit')]
    tray_menu_paused = [gt('Settings'), gt('Rescan Library'), gt('Refresh Devices'),
                        [gt('Select Device'), *device_names], [gt('Timer'), gt('Set Timer'), gt('Cancel Timer')],
                        [gt('Controls'), gt('locate track', 1), [gt('Repeat Options'), *repeat_menu], gt('Stop'),
                         gt('previous track', 1), gt('next track', 1), gt('Resume')],
                        [gt('Play'), gt('System Audio'),
                         [gt('URL'), gt('Play URL'), gt('Queue URL'), gt('Play URL Next')],
                         [gt('Folders'), *tray_folders],
                         [gt('Playlists'), *tray_playlists],
                         [gt('Select File(s)'), gt('Play File(s)'), gt('Queue File(s)'), gt('Play File(s) Next')],
                         gt('Play All')], (gt('Exit'), 'exit')]
    # refresh playlists
    tray_playlists.clear()
    tray_playlists.append(gt('Playlists Menu'))
    tray_playlists.extend([(f'{pl}'.replace('&', '&&&'), f'PL:{pl}') for pl in settings['playlists']])
    # tell tray process to update
    # icon = FILLED_ICON if playing_status.playing() else UNFILLED_ICON
    icon = {'filled': None} if playing_status.playing() else {'unfilled': None}
    if playing_status.busy():
        menu = tray_menu_playing if playing_status.playing() else tray_menu_paused
        metadata = get_current_metadata()
        title, artists = metadata['artist'], metadata['title']
        _tooltip = f"{get_first_artist(artists)} - {title}".replace('&', '&&&')
    else:
        menu, _tooltip = tray_menu_default, 'Music Caster'
    if settings.get('DEBUG', DEBUG): _tooltip += ' [DEBUG]'
    tray_process_queue.put({'menu': menu, 'tooltip': _tooltip, **icon})


def change_settings(settings_key, new_value):
    """ can be called from non-main thread """
    if settings[settings_key] != new_value:
        settings[settings_key] = new_value
        save_settings()
        if settings_key == 'repeat':
            daemon_commands.put('update_gui')
            refresh_tray()
        elif settings_key == 'shuffle':
            if not main_window.was_closed(): daemon_commands.put('update_gui')
            shuffle_queue() if new_value else un_shuffle_queue()
    return new_value


def save_queues():
    global save_queue_thread

    def _save_queue():
        settings['queues']['done'] = tuple(done_queue)
        settings['queues']['music'] = tuple(music_queue)
        settings['queues']['next'] = tuple(next_queue)
        save_settings()

    if settings['persistent_queue'] and not save_queue_thread.is_alive():
        save_queue_thread = Thread(target=_save_queue, name='SaveQueue')
        save_queue_thread.start()


def update_volume(new_vol):
    """new_vol: float[0, 100]"""
    main_window.metadata['update_volume_slider'] = True
    new_vol = new_vol / 100
    audio_player.set_volume(new_vol)
    if cast is not None:
        with suppress(NotConnected): cast.set_volume(new_vol)


def cycle_repeat():
    """ :return: new repeat value """
    # Repeat Off (None) becomes All (False) becomes One (True) becomes Off
    new_repeat_setting = {None: False, True: None, False: True}[settings['repeat']]
    return change_settings('repeat', new_repeat_setting)


def create_email_url():
    try:
        with open('music_caster.log') as f:
            log_lines = f.read().splitlines()[-10:]  # get last 10 lines of the log
    except FileNotFoundError:
        log_lines = []
    log_lines = '%0D%0A'.join(log_lines)
    email_body = f'body=%0D%0A%23%20Last%20Few%20Lines%20of%20the%20Log%0D%0A%0D%0A{log_lines}'
    mail_to = f'mailto:{EMAIL}?subject=Regarding%20Music%20Caster%20v{VERSION}&{email_body}'
    return mail_to


def handle_exception(e, restart_program=False):
    current_time = str(datetime.now())
    trace_back_msg = traceback.format_exc()
    exc_type, exc_tb = sys.exc_info()[0], sys.exc_info()[2]
    if playing_url: playing_uri = 'url'
    elif sar.alive: playing_uri = 'system audio'
    elif playing_status.busy(): playing_uri = 'file'
    else: playing_uri = 'N/A'
    try:
        with open('music_caster.log') as f:
            log_lines = f.read().splitlines()[-5:]  # get last 5 lines of the log
    except FileNotFoundError:
        log_lines = []
    payload = {'VERSION': VERSION, 'EXCEPTION TYPE': exc_type.__name__, 'LINE': exc_tb.tb_lineno,
               'PORTABLE': not os.path.exists(UNINSTALLER), 'CWD': os.getcwd(),
               'MQ': len(music_queue), 'NQ': len(next_queue), 'DQ': len(done_queue),
               'TRACEBACK': trace_back_msg.replace('\\', '/'), 'MAC': hashlib.md5(get_mac().encode()).hexdigest(),
               'FATAL': restart_program, 'LOG': log_lines, 'CASTING': cast is not None,
               'OS': platform.platform(), 'TIME': current_time, 'PLAYING_TYPE': playing_uri}
    if IS_FROZEN:
        with suppress(requests.RequestException):
            requests.post('https://dc19f29a6822522162e00f0b4bee7632.m.pipedream.net', json=payload)
    try:
        with open('error.log', 'r') as _f:
            content = _f.read()
    except (FileNotFoundError, ValueError):
        content = ''
    with open('error.log', 'w') as _f:
        _f.write(pprint.pformat(payload))
        _f.write('\n')
        _f.write(content)
    close_tray()
    if restart_program:
        with suppress(Exception): stop('error handling')
        tray_notify(gt('An error occurred, restarting now'))
        if IS_FROZEN: os.startfile('Music Caster.exe')
        else: raise e  # raise exception if running in script rather than executable
        sys.exit()


def get_album_art(file_path: str) -> tuple:  # mime: str, data: str
    with suppress(MutagenError):
        folder = os.path.dirname(file_path)
        if settings['folder_cover_override']:
            for ext in ('png', 'jpg', 'jpeg'):
                folder_cover = os.path.join(folder, f'cover.{ext}')
                if os.path.exists(folder_cover):
                    with open(folder_cover, 'rb') as f:
                        return ext, base64.b64encode(f.read())
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.flac':
            pics = mutagen.flac.FLAC(file_path).pictures
            with suppress(IndexError): return pics[0].mime, base64.b64encode(pics[0].data).decode()
        elif ext in {'.mp4', '.m4a', '.aac'}:
            with suppress(KeyError, IndexError):
                cover = mutagen.File(file_path)['covr'][0]
                image_format = cover.imageformat
                mime = 'image/png' if image_format == 14 else 'image/jpeg'
                return mime, base64.b64encode(cover).decode()
        else:
            tags = mutagen.File(file_path)
            if tags is not None:
                for tag in tags.keys():
                    if 'APIC' in tag:
                        try:
                            return tags[tag].mime, base64.b64encode(tags[tag].data).decode()
                        except AttributeError:
                            mime = tags['mime'][0].value if 'mime' in tags else 'image/jpeg'
                            return mime, base64.b64encode(tags[tag][0].value).decode()

    return 'image/jpeg', DEFAULT_ART


def get_current_art():
    if sar.alive: return custom_art('SYS')
    if playing_status.busy() and music_queue:
        uri = music_queue[0]
        if uri.startswith('http'):
            if 'art' not in url_metadata.get(uri, {}): return custom_art('URL')
            if 'art_data' in url_metadata[uri]: return url_metadata[uri]['art_data']
            # use 'art_data' else download 'art' link and cache to 'art_data'
            url_metadata[uri]['art_data'] = base64.b64encode(requests.get(url_metadata[uri]['art']).content)
            return url_metadata[uri]['art_data']
        with suppress(MutagenError):
            return get_album_art(uri)[1]
    return DEFAULT_ART


def get_metadata_wrapped(file_path: str) -> dict:  # keys: title, artist, album, sort_key
    try:
        return get_metadata(file_path)
    except mutagen.MutagenError:
        try:
            metadata = all_tracks[Path(file_path).as_posix()]
            return metadata
        except KeyError:
            return {'title': Unknown('Title'), 'artist': Unknown('Artist'), 'explicit': False,
                    'album': Unknown('Title'), 'sort_key': get_file_name(file_path), 'track_number': '0'}


def get_uri_metadata(uri, read_file=True):
    uri = uri.replace('\\', '/')
    try:
        return all_tracks[uri]
    except KeyError:
        try:
            # if uri is a url
            return url_metadata[uri]
        except KeyError:
            # uri is probably a file that has not been cached yet
            if not read_file: raise KeyError
            metadata = get_metadata_wrapped(uri)
            if uri.startswith('http'): return metadata
            all_tracks[uri] = metadata
            return metadata


def get_current_metadata() -> dict:
    if sar.alive: return url_metadata['SYSTEM_AUDIO']
    if music_queue and playing_status.busy(): return get_uri_metadata(music_queue[0])
    return {'artist': '', 'title': gt('Nothing Playing'), 'album': ''}


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
        if uri in settings['playlists']:
            yield from get_audio_uris(settings['playlists'][uri], scan_uris=scan_uris, ignore_m3u=ignore_m3u,
                                      parsed_m3us=parsed_m3us)
        elif os.path.isdir(uri) and not ignore_dir:
            # if scanning a folder, ignore playlist files and folders that are named as files as they aren't audio files
            yield from get_audio_uris(glob.iglob(f'{glob.escape(uri)}/**/*.*', recursive=True),
                                      scan_uris=scan_uris, ignore_m3u=True, parsed_m3us=parsed_m3us, ignore_dir=True)
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


def index_all_tracks(update_global=True, ignore_files: set = None):
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
        for uri in get_audio_uris(music_folders, False, True):
            dict_to_use[uri] = get_metadata_wrapped(uri)
        if use_temp: all_tracks = all_tracks_temp
        main_window.metadata['update_listboxes'] = True
        # scan playlist items
        for _ in get_audio_uris(settings['playlists']): pass
        all_tracks_sorted = sorted(all_tracks.items(), key=lambda item: item[1]['sort_key'])

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
    """
    global settings, music_folders, settings_last_modified, DEFAULT_FOLDER
    _save_settings = False
    with settings_file_lock:
        try:
            with open(SETTINGS_FILE) as json_file:
                loaded_settings = json.load(json_file)
        except (FileNotFoundError, json.JSONDecodeError):
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
        settings['discord_rpc'] = False  # NOTE: THIS DISABLES DISCORD RPC
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
        Shared.lang = settings['lang']
        Shared.track_format = settings['track_format']
        fg, bg, accent = theme['text'], theme['background'], theme['accent']
        Sg.set_options(text_color=fg, element_text_color=fg, input_text_color=fg,
                       button_color=(bg, bg), element_background_color=bg, scrollbar_color=bg,
                       text_element_background_color=bg, background_color=bg,
                       input_elements_background_color=bg, progress_meter_color=accent,
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
            if resume():
                api_msg = 'resumed playback'
            else:
                if music_queue:
                    play(music_queue[0])
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
            shuffle_enabled = change_settings('shuffle', not settings['shuffle'])
            api_msg = f'shuffle set to {shuffle_enabled}'
        elif 'activate' in request.values:
            daemon_commands.put('__ACTIVATED__')  # tells main loop to bring to front all GUI's
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
    formatted_devices = ['Local Device'] + [cc.name for cc in chromecasts]
    return render_template('index.html', device_name=platform.node(), shuffle=shuffle_enabled, repeat_enabled=repeat_enabled,
                           playing_status=playing_status, metadata=metadata, art=art,
                           settings=settings, list_of_tracks=list_of_tracks, repeat_option=repeat_option, queue=_queue,
                           playing_index=len(done_queue), device_index=device_index, devices=formatted_devices,
                           version=VERSION, gt=gt)


@app.route('/play/', methods=['GET', 'POST'])
def api_play():
    global last_play_command
    from_explorer = time.time() - last_play_command < 0.5
    queue_only = request.values.get('queue', 'false').lower() == 'true' or from_explorer
    play_next = request.values.get('play_next', 'false').lower() == 'true'
    # < 0.5 because that's how fast Windows would open each instance of MC
    last_play_command = time.time()
    if 'uris' in request.values:
        play_uris(request.values.getlist('uris'), queue_uris=queue_only, play_next=play_next,
                  from_explorer=from_explorer)
    elif 'uri' in request.values:
        play_uris([request.values['uri']], queue_uris=queue_only, play_next=play_next, from_explorer=from_explorer)
        if settings['queue_library']: queue_all()
    return redirect('/') if request.method == 'GET' else 'true'


@app.route('/state/')
def api_state():
    metadata = get_current_metadata()
    now_playing = {'status': str(playing_status), 'volume': settings['volume'], 'lang': settings['lang'],
                   'title': str(metadata['title']), 'artist': str(metadata['artist']), 'album': str(metadata['album']),
                   'queue_length': len(done_queue) + len(music_queue) + len(next_queue)}
    return jsonify(now_playing)


@app.errorhandler(InternalServerError)
def handle_500(_e):
    original = getattr(_e, "original_exception", None)

    if original is None:
        # direct 500 error, such as abort(500)
        handle_exception(_e)
        return gt('An Internal Server Error occurred') + f': {_e}'

    # wrapped unhandled error
    handle_exception(original)
    return gt('An Internal Server Error occurred') + f': {original}'


@app.route('/debug/')
def api_get_debug_info():
    threads = [(t.name, t.is_alive()) for t in threading.enumerate()]
    if settings.get('DEBUG', DEBUG):
        return jsonify({'pressed_keys': list(PRESSED_KEYS),
                        'last_traceback': sys.exc_info(),
                        'threads': threads,
                        'mac': get_mac()})
    return gt('set DEBUG = true in `settings.json` to enable this page')


@app.route('/running/', methods=['GET', 'POST', 'OPTIONS'])
def api_running():
    response = make_response('true')
    if request.environ.get('HTTP_ORIGIN') in {'https://elijahlopez.herokuapp.com', 'http://elijahlopez.herokuapp.com'}:
        response.headers.add('Access-Control-Allow-Origin', request.environ['HTTP_ORIGIN'])
    return response


@app.route('/exit/', methods=['GET', 'POST'])
def api_exit():
    daemon_commands.put(gt('Exit'))
    return 'true'


@app.route('/change-setting/', methods=['POST'])
def api_change_setting():
    with suppress(KeyError):
        setting_key = request.json['setting_name']
        if setting_key in settings or setting_key in {'timer_stop'}:
            val = request.json['value']
            change_settings(setting_key, val)
            timer_settings = {'timer_hibernate', 'timer_sleep',
                              'timer_shut_down', 'timer_stop'}
            if val and setting_key in timer_settings:
                for timer_setting in timer_settings.difference({setting_key, 'timer_stop'}):
                    change_settings(timer_setting, False)
            if setting_key == 'volume':
                update_volume(0 if settings['muted'] else settings['volume'])
        return 'true'
    return 'false'


@app.route('/refresh-devices/')
def api_refresh_devices():
    start_chromecast_discovery(start_thread=True)
    return 'true'


@app.route('/rescan-library/')
def api_rescan_library():
    index_all_tracks()
    return 'true'


@app.get('/devices/')
def api_get_devices():
    devices = ['0. Local Device']
    for i, chromecast in enumerate(chromecasts):
        i += 1
        devices.append(f'{i}. {chromecast}')
    return jsonify(devices)


@app.post('/change-device/')
def api_change_device():
    with suppress(KeyError):
        change_device(int(request.json['device_index']))
        return 'true'
    return 'false'


def cancel_timer():
    global timer
    timer = 0
    if settings['notifications']: tray_notify(gt('Timer cancelled'))


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
        if seconds_delta < 0: seconds_delta += 43200  # add 12 hours
        seconds = seconds_delta
    else:
        raise ValueError()
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
        return set_timer(val.lower())
    else:  # GET request
        return str(timer)


@app.route('/file/')
def api_get_file():
    if 'path' in request.args:
        file_path = request.args['path']
        if os.path.isfile(file_path) and valid_audio_file(file_path) or file_path == 'DEFAULT_ART':
            if request.args.get('thumbnail_only', False) or file_path == 'DEFAULT_ART':
                mime_type, img_data = get_album_art(file_path)
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
    return Response(sar.get_audio_data(settings['delay']))


@cmp_to_key
def chromecast_sorter(cc1: Chromecast, cc2: Chromecast):
    # sort by groups, then by name, then by UUID
    if cc1.device.cast_type == 'group' and cc2.device.cast_type != 'group': return -1
    if cc1.device.cast_type != 'group' and cc2.device.cast_type == 'group': return 1
    if cc1.name < cc2.name: return -1
    if cc1.name > cc2.name: return 1
    if str(cc1.uuid) > str(cc2.uuid): return 1
    return -1


def chromecast_callback(chromecast):
    global cast
    previous_device = settings['previous_device']
    if str(chromecast.uuid) == previous_device and cast != chromecast:
        cast = chromecast
        cast.wait()
    if chromecast.uuid not in (_cc.uuid for _cc in chromecasts):
        chromecasts.append(chromecast)
        # chromecasts.sort(key=lambda _cc: (_cc.device.model_name, type, _cc.name, _cc.uuid))
        chromecasts.sort(key=chromecast_sorter)
        device_names.clear()
        for _i, _cc in enumerate(chain(['Local device'], chromecasts)):
            _cc: Chromecast
            device_name = _cc if _i == 0 else _cc.name
            if (cast is None and _i == 0) or (type(_cc) != str and str(_cc.uuid) == previous_device):
                # device_names.append(f'{CHECK_MARK} {device_name}::device')
                device_names.append((f'{CHECK_MARK} {device_name}', f'device:{_i}'))
            else:
                # device_names.append(f'    {device_name}::device')
                device_names.append((f'    {device_name}', f'device:{_i}'))
        refresh_tray()


def start_chromecast_discovery(start_thread=False):
    global stop_discovery_browser
    if start_thread: return Thread(target=start_chromecast_discovery, daemon=True, name='CCDiscovery').start()
    # stop any active scanning
    if stop_discovery_browser is not None:
        pychromecast.discovery.stop_discovery(stop_discovery_browser)
    chromecasts.clear()
    stop_discovery_browser = pychromecast.get_chromecasts(blocking=False, callback=chromecast_callback)
    time.sleep(WAIT_TIMEOUT + 1)
    pychromecast.discovery.stop_discovery(stop_discovery_browser)
    stop_discovery_browser = None
    if not device_names:
        device_names.append((f'{CHECK_MARK} Local device', 'device:0'))
        refresh_tray()


def change_device(new_idx):
    # new_idx is the index of the new device
    global cast
    new_device: Chromecast = None if (new_idx == 0 or new_idx > len(chromecasts)) else chromecasts[new_idx - 1]

    if cast != new_device:
        device_names.clear()
        for idx, cc in enumerate(['Local device'] + chromecasts):
            cc: Chromecast = cc if idx == 0 else cc.name
            tray_device_name = f'{CHECK_MARK} {cc}' if idx == new_idx else f'    {cc}'
            device_names.append((tray_device_name, f'device:{idx}'))
        refresh_tray()

        current_pos = 0
        if cast is not None and cast.app_id == APP_MEDIA_RECEIVER:
            if playing_status.busy():
                mc = cast.media_controller
                with suppress(UnsupportedNamespace):
                    mc.update_status()  # Switch device without playback loss
                    current_pos = mc.status.adjusted_current_time
                    if mc.is_playing or mc.is_paused: mc.stop()
            with suppress(NotConnected):
                cast.quit_app()
        elif cast is None and audio_player.is_busy():
            current_pos = audio_player.stop()
        cast = new_device
        change_settings('previous_device', None if cast is None else str(cast.uuid))
        if playing_status.busy() and (music_queue or sar.alive):
            if not sar.alive:
                play(music_queue[0], position=current_pos, autoplay=playing_status.playing(), switching_device=True)
            elif not play_system_audio(True):
                playing_status.stop()
        else:
            cast_wait()
            volume = 0 if settings['muted'] else settings['volume']
            update_volume(volume)


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
    main_window.metadata['update_listboxes'] = True


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
    main_window.metadata['update_listboxes'] = True


def format_uri(uri: str, use_basename=False):
    try:
        if use_basename: raise TypeError
        metadata = get_uri_metadata(uri, read_file=False)
        title, artist = metadata['title'], metadata['artist']
        if artist == Unknown('Artist') or title == Unknown('Title'): raise KeyError
        formatted = settings['track_format'].replace('&artist', artist).replace('&title', title)
        number = metadata.get('track_number', '')
        if '&trck' in formatted:
            formatted = formatted.replace('&trck', number)
        elif settings['show_track_number'] and number:
            formatted = f'[{number}] {formatted}'
        return formatted
    except (TypeError, KeyError):
        if uri.startswith('http'): return uri
        base = os.path.basename(uri)
        return os.path.splitext(base)[0]


def create_track_list():
    """:returns the formatted tracks queue, and the selected value (currently playing)"""
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
                formatted_track = format_uri(uri)
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


def _update_gui():
    if not main_window.was_closed():
        if playing_status.stopped():
            main_window['progress_bar'].update(0, disabled=True)
        else:
            value, range_max = (1, 1) if track_length is None else (floor(track_position), track_length)
            main_window['progress_bar'].update(value, range=(0, range_max), disabled=track_length is None)
        metadata = get_current_metadata()
        title, artist, album = metadata['title'], get_first_artist(metadata['artist']), metadata['album']
        if playing_status.busy() and music_queue and not sar.alive:
            if settings['show_track_number']:
                with suppress(KeyError):
                    track_number = metadata['track_number']
                    title = f'{track_number}. {title}'
        if settings['mini_mode']: title = truncate_title(title)
        else: main_window['album'].update(album)
        main_window['title'].update(title)
        main_window['artist'].update(artist)
        image_data = PAUSE_BUTTON_IMG if playing_status.playing() else PLAY_BUTTON_IMG
        main_window['pause/resume'].update(image_data=image_data)
        if settings['show_album_art']:
            size = COVER_MINI if settings['mini_mode'] else COVER_NORMAL
            try:
                album_art_data = resize_img(get_current_art(), settings['theme']['background'], size).decode()
            except (UnidentifiedImageError, OSError):
                album_art_data = resize_img(DEFAULT_ART, settings['theme']['background'], size).decode()
            main_window['artwork'].update(data=album_art_data)
        repeat_button: Sg.Button = main_window['repeat']
        repeat_img, new_tooltip = repeat_img_tooltip(settings['repeat'])
        repeat_button.metadata = settings['repeat']
        repeat_button.update(image_data=repeat_img)
        repeat_button.set_tooltip(new_tooltip)
        shuffle_image_data = SHUFFLE_ON if settings['shuffle'] else SHUFFLE_OFF
        main_window['shuffle'].update(image_data=shuffle_image_data)


def after_play(title, artists: str, autoplay, switching_device):
    app_log.info(f'after_play: autoplay={autoplay}, switching_device={switching_device}')
    # prevent Windows from going to sleep
    if autoplay:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
        if settings['notifications'] and not switching_device and main_window.was_closed():
            # artists is comma separated string
            tray_notify(gt('Playing') + f': {get_first_artist(artists)} - {title}')
        playing_status.play()
    else:
        playing_status.pause()
    refresh_tray()
    save_queues()
    if settings['discord_rpc']:
        with suppress(Exception):
            rich_presence.update(state=gt('By') + f': {artists}', details=title, large_image='default',
                                 large_text=gt('Listening'), small_image='logo', small_text='Music Caster')
    if not main_window.was_closed():
        main_window.metadata['update_listboxes'] = True
        daemon_commands.put('update_gui')


def play_system_audio(switching_device=False):
    global track_position, track_start, track_end, track_length
    if cast is None:
        tray_notify(gt('ERROR') + ': ' + gt('Not connected to a cast device'))
        sar.alive = False
        return False
    else:
        cast_wait()
        try:
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
            mc.block_until_active(WAIT_TIMEOUT)
            start_time = time.monotonic()
            block_until = time.monotonic() + WAIT_TIMEOUT
            while not mc.status.player_is_playing and time.monotonic() < block_until: time.sleep(0.01)
            mc.play()
            sar.lag = time.monotonic() - start_time  # ~1 second
            track_length = None
            track_position = 0
            track_start = time.monotonic() - track_position
            after_play(title, artist, True, switching_device)
            return True
        except NotConnected as e:
            tray_notify(gt('ERROR') + ': ' + gt('Could not connect to cast device') + ' ' + str(get_linenumber()))
            handle_exception(e)
            return False
        except OSError:
            tray_notify(gt('ERROR') + ': ' + gt('Could not find an output device to record'))
            return False


# noinspection PyTypeChecker
def get_url_metadata(url, fetch_art=True) -> list:
    """
    Tries to parse url and set url_metadata[url] to parsed metadata
    Supports: YouTube, Soundcloud, any url ending with a valid audio extension
    """
    global deezer_opened
    metadata_list = []
    if url in url_metadata and not url_metadata[url].get('expired', lambda: True)(): return [url_metadata[url]]
    if url.startswith('http') and valid_audio_file(url):  # source url e.g. http://...radio.mp3
        ext = url[::-1].split('.', 1)[0][::-1]
        url_frags = urlsplit(url)
        title, artist, album = url_frags.path.split('/')[-1], url_frags.netloc, url_frags.path[1:]
        url_metadata[url] = metadata = {'title': title, 'artist': artist, 'length': None, 'album': album,
                                        'src': url, 'url': url, 'ext': ext, 'expired': lambda: False}
        metadata_list.append(metadata)
    elif 'twitch.tv' in url:
        with suppress(StopIteration, DownloadError):
            r = ydl().extract_info(url, download=False)
            audio_url = max(r['formats'], key=lambda item: item['tbr'] * (item['vcodec'] == 'none'))['url']
            metadata = {'title': r['description'], 'artist': r['uploader'], 'ext': r['ext'],
                        'expired': lambda: False, 'album': 'Twitch', 'length': None,
                        'art': r['thumbnail'], 'url': r['url'], 'audio_url': audio_url, 'src': url}
            url_metadata[url] = metadata
            metadata_list.append(metadata)
    elif 'soundcloud.com' in url:
        with suppress(StopIteration, DownloadError):
            r = ydl().extract_info(url, download=False)
            if 'entries' in r:
                for entry in r['entries']:
                    parsed_url = parse_qs(urlparse(entry['url']).query)['Policy'][0].replace('_', '=')
                    policy = base64.b64decode(parsed_url).decode()
                    expiry_time = json.loads(policy)['Statement'][0]['Condition']['DateLessThan']['AWS:EpochTime']
                    album = entry.get('album', r.get('title', 'SoundCloud'))
                    metadata = {'title': entry['title'], 'artist': entry['uploader'], 'album': album,
                                'length': entry['duration'], 'art': entry['thumbnail'], 'src': entry['webpage_url'],
                                'url': entry['url'], 'ext': entry['ext'], 'expired': lambda: time.time() > expiry_time}
                    url_metadata[entry['webpage_url']] = metadata
                    metadata_list.append(metadata)
            else:
                policy = base64.b64decode(parse_qs(urlparse(r['url']).query)['Policy'][0].replace('_', '=')).decode()
                expiry_time = json.loads(policy)['Statement'][0]['Condition']['DateLessThan']['AWS:EpochTime']
                is_expired = lambda: time.time() > expiry_time
                url_metadata[url] = metadata = {'title': r['title'], 'artist': r['uploader'], 'album': 'SoundCloud',
                                                'src': url, 'ext': r['ext'], 'expired': is_expired,
                                                'length': r['duration'], 'art': r['thumbnail'], 'url': r['url']}
                metadata_list.append(metadata)
    elif get_yt_id(url) is not None or url.startswith('ytsearch:'):
        with suppress(DownloadError, TypeError):  # type error in case video was deleted
            try:
                r = ydl().extract_info(url, download=False)
            except DownloadError:
                proxy = get_proxy(False)['https']
                r = ydl(proxy).extract_info(url, download=False)
            if 'entries' in r:
                for entry in r['entries']:
                    audio_url = max(entry['formats'], key=lambda item: item['tbr'] * (item['vcodec'] == 'none'))['url']
                    formats = [_f for _f in entry['formats'] if _f['acodec'] != 'none' and _f['vcodec'] != 'none']
                    _f = max(formats, key=lambda _f: (_f['width'], _f['tbr']))
                    expiry_time = time.time() + 3600  # expire in an hour
                    album = entry.get('album', r.get('title', entry.get('playlist', 'YouTube')))
                    length = entry['duration'] if entry['duration'] != 0 else None
                    metadata = {'title': entry['title'], 'artist': entry['uploader'], 'art': entry['thumbnail'],
                                'album': album, 'length': length, 'ext': _f['ext'],
                                'expired': lambda: time.time() > expiry_time,
                                'src': entry['webpage_url'], 'url': _f['url'], 'audio_url': audio_url}
                    # if duration > 10 minutes, try to parse out timestamps for track from comment section
                    if entry['duration'] > 600: metadata['timestamps'] = get_video_timestamps(entry)
                    for webpage_url in get_yt_urls(entry['id']): url_metadata[webpage_url] = metadata
                    metadata_list.append(metadata)
            else:
                audio_url = max(r['formats'], key=lambda item: item['tbr'] * (item['vcodec'] == 'none'))['url']
                formats = [_f for _f in r['formats'] if _f['acodec'] != 'none' and _f['vcodec'] != 'none']
                _f = max(formats, key=lambda _f: (_f['width'], _f['tbr']))
                expiry_time = time.time() + 3600
                length = r['duration'] if r['duration'] != 0 else None
                metadata = {'title': r.get('track', r['title']), 'artist': r.get('artist', r['uploader']),
                            'expired': lambda: time.time() > expiry_time,
                            'album': r.get('album', 'YouTube'), 'length': length, 'ext': _f['ext'],
                            'art': r['thumbnail'], 'url': _f['url'], 'audio_url': audio_url, 'src': url}
                # if duration > 10 minutes, try to parse out timestamps for track from comment section
                if r['duration'] > 600: metadata['timestamps'] = get_video_timestamps(r)
                for webpage_url in get_yt_urls(r['id']): url_metadata[webpage_url] = metadata
                url_metadata[url] = metadata
                metadata_list.append(metadata)
    elif url.startswith('https://open.spotify.com'):
        # Handle Spotify URL (get metadata to search for track on YouTube)
        if url in url_metadata:
            metadata = url_metadata[url]
            query = f"{get_first_artist(metadata['artist'])} - {metadata['title']}"
            youtube_metadata = get_url_metadata(f'ytsearch:{query}', False)[0]
            metadata = {**youtube_metadata, **metadata}
            url_metadata[metadata['src']] = url_metadata[youtube_metadata['src']] = metadata
            metadata_list.append(metadata)
        else:
            # get a list of spotify tracks from the track/album/playlist Spotify URL
            spotify_tracks = get_spotify_tracks(url)
            if spotify_tracks:
                metadata = spotify_tracks[0]
                query = f"{get_first_artist(metadata['artist'])} - {metadata['title']}"
                youtube_metadata = get_url_metadata(f'ytsearch:{query}', False)[0]
                metadata = {**youtube_metadata, **metadata}
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
                Thread(target=webbrowser.open, daemon=True, args=['https://www.deezer.com/login']).start()
                tray_notify(gt('ERROR') + ': ' + gt('Not logged into deezer.com'))
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
    if metadata_list and fetch_art:
        # fetch and cache artwork for first url
        metadata = metadata_list[0]
        if 'art' in metadata and 'art_data' not in metadata:
            url_metadata[metadata['src']]['art_data'] = base64.b64encode(requests.get(metadata['art']).content)
    return metadata_list


def play_url(url, position=0, autoplay=True, switching_device=False):
    global cast, playing_url, cast_last_checked, track_length, track_start, track_end, track_position
    metadata_list = get_url_metadata(url)
    if metadata_list:
        if len(metadata_list) > 1:
            # url was for multiple sources
            music_queue.popleft()
            music_queue.extendleft((metadata['src'] for metadata in reversed(metadata_list)))
        metadata = metadata_list[0]
        title, artist, album = metadata['title'], metadata['artist'], metadata['album']
        ext = metadata['ext']
        url = metadata['audio_url'] if cast is None and 'audio_url' in metadata else metadata['url']
        thumbnail = metadata['art'] if 'art' in metadata else f'{get_ipv4()}/file?path=DEFAULT_ART'
        track_length = metadata['length']
        if cast is None:
            audio_player.play(url, start_playing=autoplay, start_from=position)
        else:
            try:
                cast_last_checked = time.monotonic() + 60  # make sure background_tasks doesn't interfere
                with suppress(RuntimeError): cast.wait(timeout=WAIT_TIMEOUT)
                cast.set_volume(0 if settings['muted'] else settings['volume'] / 100)
                mc = cast.media_controller
                if mc.status.player_is_playing or mc.status.player_is_paused:
                    mc.stop()
                    mc.block_until_active(WAIT_TIMEOUT)
                _metadata = {'metadataType': 3, 'albumName': album, 'title': title, 'artist': artist}
                stream_type = 'LIVE' if track_length is None else 'BUFFERED'
                mc.play_media(url, f'video/{ext}', metadata=_metadata, thumb=thumbnail,
                              current_time=position, autoplay=autoplay, stream_type=stream_type)
                mc.block_until_active(WAIT_TIMEOUT)
                block_until = time.monotonic() + 5
                while mc.status.player_state not in {'PLAYING', 'PAUSED'} and time.monotonic() < block_until:
                    time.sleep(0.2)
                if track_length is None: mc.play()
            except (UnsupportedNamespace, NotConnected, OSError) as e:
                tray_notify(gt('ERROR') + ': ' + gt('Could not connect to cast device') + ' ' + str(get_linenumber()))
                handle_exception(e)
                return stop('play')
        track_position = position
        track_start = time.monotonic() - track_position
        if track_length is not None:
            track_end = track_start + track_length
        playing_url = True
        after_play(title, artist, autoplay, switching_device)
        return True
    if settings['notifications']: tray_notify(gt('ERROR') + ': ' + gt('Could not play $URL').replace('$URL', url))
    return False


def play(uri, position=0, autoplay=True, switching_device=False):
    global track_start, track_end, track_length, track_position, music_queue, cast_last_checked, playing_url
    while not os.path.exists(uri):
        if play_url(uri, position=position, autoplay=autoplay, switching_device=switching_device): return
        music_queue.remove(uri)
        if not music_queue: return
        uri = music_queue[0]
        position = 0
    uri = Path(uri).as_posix()
    playing_url = sar.alive = False
    cleaned_uri = 'some_file.' + uri.split('.')[-1]  # clean uri for log
    app_log.info(f'play: {cleaned_uri}, position={position}, autoplay={autoplay}, switching_device={switching_device}')
    try:
        track_length = get_length(uri)
    except InvalidAudioFile:
        tray_notify(f"ERROR: can't play {music_queue.popleft()}")
        if music_queue: play(music_queue[0])
        return
    metadata = get_metadata_wrapped(uri)
    # update metadata of track in case something changed
    all_tracks[uri] = metadata
    _volume = 0 if settings['muted'] else settings['volume'] / 100
    if cast is None:  # play locally
        audio_player.play(uri, volume=_volume, start_playing=autoplay, start_from=position)
    else:
        try:
            cast_last_checked = time.monotonic() + 30  # make sure background_tasks doesn't interfere
            url_args = urllib.parse.urlencode({'path': uri})
            url = f'http://{get_ipv4()}:{Shared.PORT}/file?{url_args}'
            with suppress(RuntimeError):
                cast.wait(timeout=WAIT_TIMEOUT)
            cast.set_volume(_volume)
            mc = cast.media_controller
            metadata = {'title': metadata['title'], 'artist': metadata['artist'],
                        'albumName': metadata['album'], 'metadataType': 3}
            ext = uri.split('.')[-1]
            mc.play_media(url, f'audio/{ext}', current_time=position,
                          metadata=metadata, thumb=url + '&thumbnail_only=true', autoplay=autoplay)
            wait_until = time.monotonic() + WAIT_TIMEOUT
            mc.block_until_active(WAIT_TIMEOUT + 1)
            if time.monotonic() > wait_until: app_log.info('play: FAILED TO BLOCK UNTIL ACTIVE')
            block_until = time.monotonic() + 5
            while mc.status.player_state not in {'PLAYING', 'PAUSED'} and time.monotonic() < block_until:
                time.sleep(0.2)
            app_log.info(f'play: mc.status.player_state={mc.status.player_state}')
        except (UnsupportedNamespace, NotConnected, OSError) as e:
            tray_notify(gt('ERROR') + ': ' + gt('Could not connect to cast device') + ' ' + str(get_linenumber()))
            handle_exception(e)
            return stop('play')
    track_position = position
    track_start = time.monotonic() - track_position
    track_end = track_start + track_length
    after_play(metadata['title'], metadata['artist'], autoplay, switching_device)


def play_uris(uris: Iterable, queue_uris=False, play_next=False, from_explorer=False, sort=True):
    """
    Appends all music files in the provided uris (playlist names, folders, files, urls) to a temp list,
        which is shuffled if shuffled is enabled in settings, and then extends music_queue.
        Note: file/folder paths take precedence over playlist names
    If queue_only is false, the music queue and done queue are cleared,
        before files are added to the music_queue
    play_next has priority over queue_uris
    If from_explorer is true, then the whole music queue is shuffled (if setting enabled),
        except for the track that is currently playing
    If sort is False, shuffle being off does not sort items
    """
    if not queue_uris and not play_next and not from_explorer:
        music_queue.clear()
        done_queue.clear()
    temp_queue = list(get_audio_uris(uris))
    if not settings['shuffle'] and sort: temp_queue.sort(key=natural_key_file)
    if play_next:
        if settings['shuffle']: better_shuffle(temp_queue)
        if settings['reversed_play_next']: next_queue.extendleft(temp_queue)
        else: next_queue.extend(temp_queue)
        main_window.metadata['update_listboxes'] = True
        return
    if settings['shuffle']:
        if from_explorer:
            # if from_explorer make temp_queue should also include files in the queue
            temp_queue.extend(islice(music_queue, 1, None))
            # remove all but first track if from_explorer
            for _ in range(len(music_queue) - 1): music_queue.pop()
        shuffle(temp_queue)
    music_queue.extend(temp_queue)
    if not queue_uris and not play_next:
        if music_queue:
            return play(music_queue[0])
        elif next_queue:
            playing_status.play()
            return next_track()
    main_window.metadata['update_listboxes'] = True
    save_queues()


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
        info = gt('INFO')
        tray_notify(f'{info}: ' + gt('Library indexing incomplete, only scanned files have been added'))
    start_shuffle_from = len(music_queue)
    music_queue.extend(index_all_tracks(False, ignore_files).keys())
    better_shuffle(music_queue, start_shuffle_from)
    if not queue_only:
        if music_queue:
            play(music_queue[0])
        elif next_queue:
            next_track(forced=True)
    main_window.metadata['update_listboxes'] = True


def queue_all():
    if not any(filter(lambda t: t.name == 'PlayAll', threading.enumerate())):
        Thread(target=play_all, kwargs={'queue_only': True}, daemon=True, name='PlayAll').start()


def file_action(action='pf'):
    """
    action = {'pf': 'Play File(s)', 'pfn': 'Play File(s) Next', 'qf': 'Queue File(s)'}
    :param action: one of {'pf': 'Play File(s)', 'pfn': 'Play File(s) Next', 'qf': 'Queue File(s)'}
    :return:
    """
    initial_folder = settings['last_folder'] if settings['use_last_folder'] else DEFAULT_FOLDER
    # noinspection PyTypeChecker
    paths: tuple = Sg.popup_get_file(gt('Select Music File(s)'), no_window=True, initial_folder=initial_folder,
                                     multiple_files=True, file_types=AUDIO_FILE_TYPES, icon=WINDOW_ICON)
    if paths:
        settings['last_folder'] = os.path.dirname(paths[-1])
        app_log.info(f'file_action(action={action}), len(lst) is {len(paths)}')
        if action in {gt('Play File(s)'), 'pf'}:
            if settings['queue_library']:
                play_all(starting_files=paths)
            else:
                play_uris(paths)
        elif action in {gt('Queue File(s)'), 'qf'}:
            play_uris(paths, queue_uris=True)
        elif action in {gt('Play File(s) Next'), 'pfn'}:
            play_uris(paths, play_next=True)
        else: raise ValueError(f'file_action expected something else. Got {action}')
    else: main_window.metadata['main_last_event'] = 'file_action'


def folder_action(action='pf'):
    """
    :param action: one of {'pf': 'Play Folder', 'qf': 'Queue Folder', 'pfn': 'Play Folder Next'}
    """
    initial_folder = settings['last_folder'] if settings['use_last_folder'] else DEFAULT_FOLDER
    folder_path = Sg.popup_get_folder(gt('Select Folder'), initial_folder=initial_folder, no_window=True,
                                      icon=WINDOW_ICON)
    if folder_path:
        main_window.metadata['main_last_event'] = Sg.TIMEOUT_KEY
        settings['last_folder'] = folder_path
        temp_queue = []
        # keep track of paths by (sub) folder
        files_to_queue = defaultdict(list)
        for file_path in get_audio_uris(folder_path):
            path = Path(file_path)
            files_to_queue[path.parent.as_posix()].append(path.as_posix())
        if settings['shuffle']:
            for files in files_to_queue.values(): temp_queue.extend(files)
            shuffle(temp_queue)
        else:
            # extend files from each (sub) folder path to maintain sort order
            for files in files_to_queue.values():
                files.sort(key=natural_key_file)
                temp_queue.extend(files)
        app_log.info(f'folder_action: action={action}), len(lst) is {len(temp_queue)}')
        if not temp_queue:
            if settings['notifications']:
                tray_notify(gt('ERROR') + ': ' + gt('Folder does not contain audio files'))
        elif action in {gt('Play Folder'), 'pf'}:
            music_queue.clear()
            done_queue.clear()
            music_queue.extend(temp_queue)
            play(music_queue[0])
        elif action in {gt('Play Folder Next'), 'pfn'}:
            if settings['reversed_play_next']: next_queue.extendleft(temp_queue)
            else: next_queue.extend(temp_queue)
            if playing_status.stopped() and not music_queue and next_queue:
                if cast is not None and cast.app_id != APP_MEDIA_RECEIVER: cast.wait(timeout=WAIT_TIMEOUT)
                playing_status.play()
                next_track()
        elif action in {gt('Queue Folder'), 'qf'}:
            music_queue.extend(temp_queue)
            if len(temp_queue) == len(music_queue) and not sar.alive: play(music_queue[0])
        else: raise ValueError(f'folder_action expected something else. Got {action}')
        main_window.metadata['update_listboxes'] = True
        save_queues()
    else: main_window.metadata['main_last_event'] = 'folder_action'


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
    app_log.info(f'pause() called, playing status = {playing_status}')
    if playing_status.playing():
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        try:
            if cast is None:
                track_position = time.monotonic() - track_start
                if audio_player.pause():
                    app_log.info(f'{source}. paused local audio player')
                else:
                    app_log.info(f'{source}. could not pause local audio player')
            else:
                mc = cast.media_controller
                mc.update_status()
                mc.pause()
                block_until = time.monotonic() + 5
                while not mc.status.player_is_paused and time.monotonic() < block_until: time.sleep(0.1)
                track_position = mc.status.adjusted_current_time
                app_log.info('paused cast device')
            playing_status.pause()
            if settings['discord_rpc'] and (music_queue or sar.alive):
                metadata = get_current_metadata()
                title, artist = metadata['title'], metadata['artist']
                with suppress(Exception):
                    rich_presence.update(state=gt('By') + f': {artist}', details=title,
                                         large_image='default', large_text='Paused',
                                         small_image='logo', small_text='Music Caster')
        except UnsupportedNamespace:
            stop('pause')
        if not main_window.was_closed(): daemon_commands.put('update_gui')
        refresh_tray()
        return True
    return False


def resume():
    global track_end, track_position, track_start
    app_log.info(f'resume() called, playing status = {playing_status}')
    if playing_status.paused():
        # time.time() > url_metadata.get(music_queue[0], {'expired': False})['expired']:
        if music_queue and url_metadata.get(music_queue[0], {'expired': lambda: False})['expired']():
            # check if the url has expired before resuming in case it has been a long time
            play(music_queue[0], position=track_position, autoplay=False)
        try:
            if cast is None:
                audio_player.resume()
            else:
                mc = cast.media_controller
                mc.update_status()
                mc.play()
                mc.block_until_active(WAIT_TIMEOUT)
                block_until = time.monotonic() + 5
                while not mc.status.player_state == 'PLAYING' and time.monotonic() < block_until: time.sleep(0.1)
                track_position = mc.status.adjusted_current_time
            track_start = time.monotonic() - track_position
            if track_length is not None:
                track_end = track_start + track_length
            playing_status.play()
            metadata = get_current_metadata()
            title, artist = metadata['title'], get_first_artist(metadata['artist'])
            if settings['discord_rpc']:
                with suppress(Exception):
                    rich_presence.update(state=gt('By') + f': {artist}', details=title,
                                         large_image='default', large_text=gt('Listening'),
                                         small_image='logo', small_text='Music Caster')
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
            if not main_window.was_closed(): daemon_commands.put('update_gui')
            refresh_tray()
        except (UnsupportedNamespace, NotConnected):
            if music_queue: return play(music_queue[0], position=track_position)
        return True
    return False


def stop(stopped_from: str, stop_cast=True):
    """
    can be called from a non-main thread
    does not check if playing_status is busy
    """
    global track_start, track_end, track_position, track_length, playing_url
    app_log.info(f'Stop reason: {stopped_from}')
    # allow Windows to go to sleep
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
    playing_status.stop()
    sar.alive = playing_url = False
    if settings['discord_rpc']:
        with suppress(Exception): rich_presence.clear()
    if cast is not None:
        if cast.app_id == APP_MEDIA_RECEIVER:
            mc = cast.media_controller
            if stop_cast:
                with suppress(NotConnected, UnsupportedNamespace):
                    mc.stop()
                    block_until = time.monotonic() + 5  # 5 seconds
                    status = mc.status
                    while ((status.player_is_playing or status.player_is_paused)
                           and time.monotonic() > block_until): time.sleep(0.1)
                    if status.player_is_playing or status.player_is_paused: cast.quit_app()
            else:  # only when background tasks calls stop()
                # check if background tasks is wrong
                mc.update_status()
                if mc.is_playing:
                    playing_status.play()
                elif mc.is_paused:
                    playing_status.pause()
                return
    else:
        audio_player.stop()
    track_start = track_position = track_end = track_length = 0
    if not main_window.was_closed(): daemon_commands.put('update_gui')
    refresh_tray()


def set_pos(new_position):
    global track_position, track_start, track_end
    if cast is not None:
        try:
            cast.media_controller.update_status()
        except UnsupportedNamespace:
            cast.wait()
        if cast.media_controller.is_idle and music_queue:
            return play(music_queue[0], position=new_position, autoplay=playing_status.playing())
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
            if track_length > 600 and url_metadata.get(music_queue[0], {}).get('timestamps') and not ignore_timestamps:
                # smart next track if playing a long URL with multiple tracks
                timestamps = url_metadata[music_queue[0]]['timestamps']
                new_position = next(filter(lambda seconds: seconds > get_track_position(), timestamps), 0)
                if new_position: return set_pos(new_position)
        # keep track of skips (used by smart queue feature)
        if music_queue and track_position < 5 and not from_timeout and playing_status.busy() and not forced:
            settings['skips'][music_queue[0]] = settings['skips'].get(music_queue[0], 0) + 1
            save_settings()
        # if repeat all or repeat is off or empty queue or manual next
        if not settings['repeat'] or not music_queue or not from_timeout:
            if settings['repeat']: change_settings('repeat', False)
            for _ in range(times):
                if music_queue: done_queue.append(music_queue.popleft())
                if next_queue: music_queue.insert(0, next_queue.popleft())
                # if queue is empty but repeat is all AND there are tracks in the done_queue
                if not music_queue and settings['repeat'] is False and done_queue:
                    music_queue.extend(done_queue)
                    done_queue.clear()
        if music_queue:
            if settings['smart_queue'] and from_timeout:
                # auto skip tracks that are likely to be skipped.
                # instead of using an arbitrary number, compare to median skips
                max_skips = len(music_queue) + len(next_queue) + len(done_queue)
                while settings['skips'].get(music_queue[0], 0) > 3 and max_skips > 0:
                    if music_queue: done_queue.append(music_queue.popleft())
                    if next_queue: music_queue.insert(0, next_queue.popleft())
                    # if queue is empty but repeat is all AND there are tracks in the done_queue
                    if not music_queue and settings['repeat'] is False and done_queue:
                        music_queue.extend(done_queue)
                        done_queue.clear()
                    max_skips -= 1
            elif times > 1:  # explicitly selected
                settings['skips'].pop(music_queue[0], None)  # reset skip counter
                save_settings()
            return play(music_queue[0])
        stop('next track')  # repeat is off / no tracks in queue


def prev_track(times=1, forced=False):
    app_log.info('prev_track()')
    if not forced and cast is not None and cast.app_id != APP_MEDIA_RECEIVER:
        playing_status.stop()
    elif forced or playing_status.busy() and not sar.alive:
        with suppress(IndexError, TypeError):  # TypeError:  if track_length is None
            if track_length > 600 and url_metadata.get(music_queue[0], {}).get('timestamps'):
                # smart next track if playing a long URL with multiple tracks
                timestamps = url_metadata[music_queue[0]]['timestamps']
                new_position = next(filter(lambda seconds: seconds < get_track_position(), timestamps), -1)
                if new_position != -1: return set_pos(new_position)
        if done_queue:
            for _ in range(times):
                if settings['repeat']: change_settings('repeat', False)
                track = done_queue.pop()
                music_queue.insert(0, track)
        with suppress(IndexError):
            settings['skips'].pop(music_queue[0], None)  # reset skip counter
            play(music_queue[0])


def check_for_updates():
    global latest_version
    release = get_latest_release(latest_version)
    # never show a notification for the same latest version
    if release:
        latest_version = release['version']
        if settings['notifications']: tray_notify('update_available', context=latest_version)


def background_tasks():
    """
    Startup tasks:
    - sends info
    - creates/removes shortcut
    - starts keyboard listener
    Periodic (While True) tasks:
    - checks for Chromecast status update
    - reloads settings.json if settings.json is modified
    - scans files
    """
    global cast_last_checked, track_position, track_start, track_end, settings_last_modified
    if not settings.get('DEBUG', DEBUG): send_info()
    create_shortcut()
    update_checker = threading.Timer(216000, check_for_updates)
    update_checker.daemon = True
    update_checker.start()
    p = pynput.keyboard.Listener(on_press=on_press, on_release=lambda key: PRESSED_KEYS.discard(str(key)))
    p.setName('pynputListener')
    p.start()
    while True:
        # if settings.json was updated outside of Music Caster, reload settings
        if os.path.getmtime(SETTINGS_FILE) != settings_last_modified: load_settings()
        # check cast every 5 seconds
        if cast is not None and time.monotonic() - cast_last_checked > 5:
            with suppress(UnsupportedNamespace):
                if cast.app_id == APP_MEDIA_RECEIVER:
                    mc = cast.media_controller
                    mc.update_status()
                    is_playing, is_paused = mc.status.player_is_playing, mc.status.player_is_paused
                    is_stopped = mc.status.player_is_idle
                    is_live = track_length is None
                    if not is_stopped and playing_status.busy():
                        # sync track position with chromecast, also allows scrubbing from external apps
                        if abs(mc.status.adjusted_current_time - track_position) > 0.5:
                            track_position = mc.status.adjusted_current_time
                            track_start = time.monotonic() - track_position
                            if not is_live: track_end = track_start + track_length
                    if is_paused: pause('background tasks')
                    elif is_playing: resume()
                    elif is_stopped and playing_status.busy() and not is_live and time.monotonic() - track_end > 1:
                        # if cast says nothing is playing, only stop if we are not at the end of the track
                        #  this will prevent false positives
                        stop('background tasks', False)
                    _volume = settings['volume']
                    cast_volume = round(cast.status.volume_level * 100, 1)
                    if _volume != cast_volume:
                        if cast_volume > 0.5 or cast_volume <= 0.5 and not settings['muted']:
                            # if volume was changed via Google Home App
                            _volume = change_settings('volume', cast_volume)
                            if _volume and settings['muted']: change_settings('muted', False)
                            main_window.metadata['update_volume_slider'] = True
                elif playing_status.playing():
                    stop('background tasks; app not running')
            cast_last_checked = time.monotonic()
            # don't check cast around the time the next track will start playing
            if track_end is not None and track_end - cast_last_checked < 10: cast_last_checked += 5
        # scan at most 500 files per loop.
        # Testing on an i7-7700k, scanning ~1000 files would block for 5 seconds
        uris_scanned = 0
        while uris_scanned < 500 and not uris_to_scan.empty():
            uri = uris_to_scan.get()
            if uri.startswith('http'):
                get_url_metadata(uri)
            else:
                uri = Path(uri).as_posix()
                all_tracks[uri] = get_metadata_wrapped(uri)
            uris_to_scan.task_done()
            uris_scanned += 1
        if uris_scanned: main_window.metadata['update_listboxes'] = True
        # if no files were scanned, pause for 5 seconds
        else: time.sleep(5)


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
    if key == '<179>' and not pause(): resume()
    elif key == '<176>' and playing_status.busy(): next_track()
    elif key == '<177>' and playing_status.busy(): prev_track()
    elif key == '<178>': stop('keyboard shortcut')


def get_window_location():
    if not settings['save_window_positions']: return None, None
    if settings['mini_mode']: return settings['window_locations'].get('main_mini_mode', (None, None))
    key = 'main_vertical' if settings['vertical_gui'] else 'main'
    return settings['window_locations'].get(key, (None, None))


def metadata_process_file(file):
    if os.path.isfile(file):
        main_window['metadata_file'].update(value=file)
        main_window['metadata_file'].set_tooltip(file)
        file_metadata = get_metadata_wrapped(file)
        main_window['metadata_title'].update(value=file_metadata['title'])
        main_window['metadata_artist'].update(value=file_metadata['artist'])
        main_window['metadata_album'].update(value=file_metadata['album'])
        main_window['metadata_track_num'].update(value=file_metadata['track_number'])
        main_window['metadata_explicit'].update(value=file_metadata['explicit'])
        mime, artwork = get_album_art(file)
        _, display_art = main_window['metadata_art'].metadata = (mime, None if artwork == DEFAULT_ART else artwork)
        if display_art is not None:
            display_art = resize_img(display_art, settings['theme']['background'], COVER_MINI)
        main_window['metadata_art'].update(data=display_art)


def add_music_folder(folders):
    added_folders = set(music_folders)
    for folder in folders:
        folder = folder.replace('\\', '/')
        if os.path.isdir(folder) and folder not in added_folders:
            music_folders.append(folder)
            added_folders.add(folder)
    main_window['music_folders'].update(music_folders)
    refresh_tray()
    save_settings()
    if settings['scan_folders']: index_all_tracks()


def set_callbacks():
    """ Set callbacks for the main window """

    def save_window_position(event):
        if event.widget is main_window.TKroot:
            if settings['mini_mode']: key = 'main_mini_mode'
            else: key = 'main_vertical' if settings['vertical_gui'] else 'main'
            settings['window_locations'][key] = main_window.CurrentLocation()
            save_settings()

    def library_events(event):
        library_tree_view = main_window['library'].TKTreeview
        region = library_tree_view.identify('region', event.x, event.y)
        column_index = library_tree_view.identify_column(event.x).replace('#', '')
        main_window.metadata['library']['region'] = region
        main_window.metadata['library']['column'] = int(column_index)

    def dnd_pl_tracks(event):
        file_paths = main_window.TKroot.tk.splitlist(event.data)
        pl_tracks = main_window.metadata['pl_tracks']
        pl_tracks.extend(get_audio_uris(file_paths))
        settings['last_folder'] = os.path.dirname(file_paths[-1])
        new_values = [f'{i + 1}. {format_uri(path)}' for i, path in enumerate(pl_tracks)]
        new_i = len(new_values) - 1
        main_window['pl_tracks'].update(new_values, set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))

    # drag and drop callbacks
    main_window.TKroot.tk.call('package', 'require', 'tkdnd')
    if not settings['mini_mode']:
        main_window['url_input'].bind('<<Cut>>', '_cut')
        main_window['url_input'].bind('<<Copy>>', '_copy')
        main_window['pl_url_input'].bind('<<Cut>>', '_cut')
        main_window['pl_url_input'].bind('<<Copy>>', '_copy')
        main_window['library'].TKTreeview.bind('<Button-1>', library_events, add='+')
        main_window['library'].TKTreeview.bind('<Double-Button-1>', library_events, add='+')
        scroll_areas = ['queue', 'pl_tracks', 'library']
        for scroll_area in scroll_areas:
            main_window[scroll_area].bind('<Enter>', '_mouse_enter')
            main_window[scroll_area].bind('<Leave>', '_mouse_leave')
        for input_key in ('url_input', 'pl_url_input', 'pl_name', 'timer_input',
                          'metadata_title', 'metadata_artist', 'metadata_album', 'metadata_track_num'):
            main_window[input_key].Widget.config(insertbackground=settings['theme']['text'])
        tk_lb = main_window['queue'].TKListbox
        drop_target_register(tk_lb, DND_ALL)
        dnd_bind(tk_lb, '<<Drop>>', lambda event: play_uris(tk_lb.tk.splitlist(event.data), queue_uris=True))

        tk_lb = main_window['pl_tracks'].TKListbox
        drop_target_register(tk_lb, DND_ALL)
        dnd_bind(tk_lb, '<<Drop>>', dnd_pl_tracks)

        tk_frame = main_window['tab_metadata'].TKFrame
        drop_target_register(tk_frame, DND_FILES)
        dnd_bind(tk_frame, '<<Drop>>', lambda event: metadata_process_file(tk_lb.tk.splitlist(event.data)[0]))

        tk_lb = main_window['music_folders'].TKListbox
        drop_target_register(tk_lb, DND_FILES)
        dnd_bind(tk_lb, '<<Drop>>', lambda event: add_music_folder(tk_lb.tk.splitlist(event.data)))
    else:
        root = main_window.TKroot
        drop_target_register(root, DND_ALL)
        dnd_bind(root, '<<Drop>>', lambda event: play_uris(root.tk.splitlist(event.data), queue_uris=True))

    main_window['volume_slider'].bind('<Enter>', '_mouse_enter')
    main_window['volume_slider'].bind('<Leave>', '_mouse_leave')
    main_window['progress_bar'].bind('<Enter>', '_mouse_enter')
    main_window['progress_bar'].bind('<Leave>', '_mouse_leave')
    main_window.TKroot.bind('<Configure> ', save_window_position, add='+')
    main_window.bind('<Control-}>', 'mini_mode')
    main_window.bind('<Control-r>', 'repeat')


def activate_main_window(selected_tab=None, url_option='url_play'):
    global main_window
    # selected_tab can be 'tab_queue', ['tab_library'], 'tab_playlists', 'tab_timer', or 'tab_settings'
    app_log.info(f'activate_main_window: selected_tab={selected_tab}')
    if main_window.was_closed():
        lb_tracks = create_track_list()
        selected_value = lb_tracks[len(done_queue)] if lb_tracks and len(done_queue) < len(lb_tracks) else None
        mini_mode = settings['mini_mode']
        window_location = get_window_location()
        if settings['show_album_art']:
            size = COVER_MINI if mini_mode else COVER_NORMAL
            try:
                album_art_data = resize_img(get_current_art(), settings['theme']['background'], size).decode()
            except (UnidentifiedImageError, OSError):
                album_art_data = resize_img(DEFAULT_ART, settings['theme']['background'], size).decode()
        else:
            album_art_data = None
        window_margins = (0, 0) if mini_mode else (0, 0)
        metadata = get_current_metadata()
        title, artist, album = metadata['title'], get_first_artist(metadata['artist']), metadata['album']
        position = get_track_position()
        main_gui_layout = create_main(lb_tracks, selected_value, playing_status, settings, VERSION, timer,
                                      all_tracks, title, artist, album, track_length=track_length,
                                      album_art_data=album_art_data, track_position=position)
        window_metadata: dict = {'main_last_event': None, 'update_listboxes': False, 'update_volume_slider': False,
                                 'library': {'sort_by': 0, 'ascending': True, 'region': 'cell', 'column': 1},
                                 'mouse_hover': '', 'url_input': '', 'pl_url_input': ''}
        pl_name = window_metadata['pl_name'] = next(iter(settings['playlists']), '')
        pl_tracks = window_metadata['pl_tracks'] = settings['playlists'].get(pl_name, []).copy()
        main_window = Sg.Window('Music Caster', main_gui_layout, grab_anywhere=mini_mode, no_titlebar=mini_mode,
                                finalize=True, icon=WINDOW_ICON, return_keyboard_events=True, use_default_focus=False,
                                margins=window_margins, keep_on_top=mini_mode and settings['mini_on_top'],
                                location=window_location, metadata=window_metadata)
        if not settings['mini_mode']:
            main_window['queue'].update(set_to_index=len(done_queue), scroll_to_index=len(done_queue))
            default_pl_tracks = [f'{i + 1}. {format_uri(pl_track)}' for i, pl_track in enumerate(pl_tracks)]
            main_window['pl_tracks'].update(values=default_pl_tracks)
        set_callbacks()
    elif settings['mini_mode'] and selected_tab:
        change_settings('mini_mode', not settings['mini_mode'])
        main_window.close()
        return activate_main_window(selected_tab)
    if not settings['mini_mode'] and selected_tab is not None:
        main_window[selected_tab].select()
        if selected_tab == 'tab_timer': main_window['timer_input'].set_focus()
        elif selected_tab == 'tab_url':
            main_window[url_option].update(True)
            main_window['url_input'].set_focus()
            default_text: str = pyperclip.paste()
            if default_text.startswith('http'):
                main_window['url_input'].update(default_text)
                main_window.metadata['url_input'] = default_text
        elif selected_tab == 'tab_playlists':
            default_text: str = pyperclip.paste()
            if default_text.startswith('http'):
                main_window['pl_url_input'].update(default_text)
                main_window.metadata['pl_url_input'] = default_text
    focus_window(main_window)


def locate_uri(selected_track_index=0, uri=None):
    with suppress(IndexError):
        if uri is None:
            if selected_track_index < 0:
                uri = done_queue[selected_track_index]
            elif (selected_track_index == 0 or selected_track_index > len(next_queue)) and music_queue:
                uri = music_queue[selected_track_index]
            elif 0 < selected_track_index <= len(next_queue):
                uri = next_queue[selected_track_index - 1]
            else:
                uri = ''
        if uri.startswith('http'):
            if uri.startswith('http'): Thread(target=webbrowser.open, daemon=True, args=[uri]).start()
        elif os.path.exists(uri):
            Popen(f'explorer /select,"{fix_path(uri)}"')


def exit_program():
    main_window.close()
    close_tray()
    with suppress(UnsupportedNamespace, NotConnected):
        if cast is None:
            stop('exit program')
        elif cast is not None and cast.app_id == APP_MEDIA_RECEIVER:
            cast.quit_app()
    with suppress(Exception):
        rich_presence.close()
    if settings['persistent_queue']:
        save_queues()
        save_queue_thread.join()
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
            if music_queue and (action == 'play' or shuffle_from == 0): play(music_queue[0])
        elif 'next':
            next_queue.extend(get_audio_uris(playlist_name))


def other_tray_actions(_tray_item):
    if _tray_item.startswith('device:'):
        device_index = int(re.search(r'\d+', _tray_item).group())
        with suppress(ValueError): change_device(device_index)
    elif _tray_item.startswith('PL:'):  # playlist
        playlist_action(_tray_item[3:])
    elif _tray_item == gt('Select Folder(s)'):
        folder_action()
    elif _tray_item.startswith('PF:'):  # play folder
        folder_index = int(re.search(r'\d+', _tray_item).group())
        Thread(target=play_uris, name='PlayFolder', daemon=True, args=[[music_folders[folder_index]]]).start()


def read_main_window():
    global track_position, track_start, track_end, timer, music_queue, done_queue
    main_event, main_values = main_window.read(timeout=100)
    ignore_events = {'file_action', 'folder_action', 'pl_add_tracks', 'add_music_folder'}
    if (main_event in {None, 'Escape:27'} and main_window.metadata['main_last_event'] not in ignore_events
            or main_values is None):
        main_window.close()
        return False
    main_value = main_values.get(main_event)
    if 'mouse_leave' not in main_event and 'mouse_enter' not in main_event and main_event != Sg.TIMEOUT_KEY:
        main_window.metadata['main_last_event'] = main_event
    # update timer text if timer is old
    if not settings['mini_mode'] and timer == 0 and main_window['timer_text'].metadata:
        main_window['timer_text'].update('No Timer Set')
        main_window['timer_text'].metadata = False
        main_window['cancel_timer'].update(visible=False)
    # these events modify main_event (chain events)
    if main_event.startswith('MouseWheel'):
        main_event = main_event.split(':', 1)[1]
        if main_window.metadata['mouse_hover'] == 'progress_bar':
            delta = {'Up': settings['scrubbing_delta'], 'Down': -settings['scrubbing_delta']}.get(main_event, 0)
            if playing_status.busy() and track_length is not None:
                get_track_position()
                new_position = min(max(track_position + delta, 0), track_length)
                main_window['progress_bar'].update(new_position)
                main_values['progress_bar'] = new_position
                main_event = 'progress_bar'
        elif main_window.metadata['mouse_hover'] in {'', 'volume_slider'}:  # not in another scroll view
            delta = {'Up': settings['volume_delta'], 'Down': -settings['volume_delta']}.get(main_event, 0)
            new_volume = min(max(0, main_values['volume_slider'] + delta), 100)
            change_settings('volume', new_volume)
            change_settings('muted', False)
            update_volume(new_volume)
    elif main_event in {'j', 'l'} and (main_values.get('tab_group', 'tab_queue') == 'tab_queue'):
        if playing_status.busy() and track_length is not None:
            delta = {'j': -settings['scrubbing_delta'], 'l': settings['scrubbing_delta']}[main_event]
            get_track_position()
            new_position = min(max(track_position + delta, 0), track_length)
            main_window['progress_bar'].update(new_position)
            main_values['progress_bar'] = new_position
            main_event = 'progress_bar'
            main_window.refresh()
    # change/select tabs
    if main_event == '__TIMEOUT__': pass  # avoids checking multiple if statements
    elif main_event == '1:49' and not settings['mini_mode']:  # Queue tab [Ctrl + 1]
        main_window['tab_queue'].select()
    elif (main_event == '2:50' and not settings['mini_mode'] or  # URL tab [Ctrl + 2]
          main_event == 'tab_group' and main_values.get('tab_group') == 'tab_url'):
        main_window['tab_url'].select()
        main_window['url_input'].set_focus()
        default_text: str = pyperclip.paste()
        if default_text.startswith('http'):
            main_window['url_input'].update(value=default_text)
    elif (main_event == '3:51' and not settings['mini_mode'] or  # Library tab [Ctrl + 3]:
          main_event == 'tab_group' and main_values['tab_group'] == 'tab_library'):
        main_window['tab_library'].select()
    elif (main_event == '4:52' and not settings['mini_mode'] or  # Playlists tab [Ctrl + 4]:
          main_event == 'tab_group' and main_values['tab_group'] == 'tab_playlists'):
        default_text: str = pyperclip.paste()
        if default_text.startswith('http'):
            main_window['pl_url_input'].update(value=default_text)
        main_window['tab_playlists'].select()
        main_window['playlist_combo'].set_focus()
    elif (main_event == '5:53' and not settings['mini_mode'] or  # Timer Tab [Ctrl + 5]
          main_event == 'tab_group' and main_values['tab_group'] == 'tab_timer'):
        main_window['tab_timer'].select()
        main_window['timer_input'].set_focus()
    elif main_event == '6:54' and not settings['mini_mode']:  # Metadata tab [Ctrl + 6]
        main_window['tab_metadata'].select()
        main_window['metadata_file'].set_focus()
    elif main_event == '7:55' and not settings['mini_mode']:  # Settings tab [Ctrl + 7]
        main_window['tab_settings'].select()
    elif main_event in {'progress_bar_mouse_enter', 'queue_mouse_enter', 'pl_tracks_mouse_enter',
                        'volume_slider_mouse_enter', 'library_mouse_enter'}:
        if main_event in {'progress_bar_mouse_enter', 'volume_slider_mouse_enter'} and settings['mini_mode']:
            main_window.grab_any_where_off()
        main_window.metadata['mouse_hover'] = '_'.join(main_event.split('_')[:-2])
    elif main_event in {'progress_bar_mouse_leave', 'queue_mouse_leave', 'pl_tracks_mouse_leave',
                        'volume_slider_mouse_leave', 'library_mouse_leave'}:
        if main_event in {'progress_bar_mouse_leave', 'volume_slider_mouse_leave'} and settings['mini_mode']:
            main_window.grab_any_where_on()
        if main_event != 'volume_slider_mouse_leave': main_window.metadata['mouse_hover'] = ''
    elif main_event == 'pause/resume' or main_event == 'k' and main_values.get('tab_group') in {'tab_queue', None}:
        if playing_status.paused(): resume()
        elif playing_status.playing(): pause()
        elif music_queue: play(music_queue[0])
        else: play_all()
    elif main_event == 'next' and playing_status.busy():
        next_track()
    elif main_event == 'prev' and playing_status.busy():
        prev_track()
    elif main_event == 'delay':
        with suppress(ValueError):
            change_settings('delay', int(main_value))
    elif main_event == 'shuffle':
        change_settings('shuffle', not settings['shuffle'])
    elif main_event == 'repeat': cycle_repeat()
    elif (main_event == 'volume_slider' or ((main_event in {'a', 'd'} or main_event.isdigit())
                                            and (main_values.get('tab_group') in {'tab_queue', None}))):
        # User scrubbed volume bar or pressed a, d, #
        if main_event.isdigit():
            new_volume = int(main_event) * 10
        else:
            delta = {'a': -settings['volume_delta'], 'd': settings['volume_delta']}.get(main_event, 0)
            new_volume = main_values['volume_slider'] + delta
        change_settings('volume', new_volume)
        # un-mute if volume slider was moved
        change_settings('muted', False)
        update_volume(new_volume)
    elif main_event in {'Up:38', 'Down:40'}:
        focused_element = main_window.FindElementWithFocus()
        if settings['mini_mode'] or focused_element not in {main_window['queue'], main_window['pl_tracks'],
                                                            main_window['music_folders']}:
            delta = settings['volume_delta'] if main_event == 'Up:38' else -settings['volume_delta']
            new_volume = main_values['volume_slider'] + delta
            change_settings('volume', new_volume)
            # un-mute if volume slider was moved
            change_settings('muted', False)
            update_volume(new_volume)
    elif main_event in {'mute', 'm:77'}:  # toggle mute
        update_volume(0 if change_settings('muted', not settings['muted']) else settings['volume'])
    elif main_event in {'Prior:33', 'Next:34'} and settings['mini_mode']:  # page up, page down
        focused_element = main_window.FindElementWithFocus()
        move = {'Prior:33': -3, 'Next:34': 3}[main_event]
        if focused_element == main_window['queue'] and main_values['queue']:
            new_i = main_window['queue'].get_indexes()[0] + move
            new_i = min(max(new_i, 0), len(main_window['queue'].Values) - 1)
            main_window['queue'].update(set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))
        elif focused_element == main_window['pl_tracks'] and main_values['pl_tracks']:
            new_i = main_window['pl_tracks'].get_indexes()[0] + move
            new_i = min(max(new_i, 0), len(main_window.metadata['pl_tracks']) - 1)
            main_window['pl_tracks'].update(set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))
    elif main_event == 'queue' and main_value:
        with suppress(ValueError):
            selected_uri_index = main_window['queue'].get_indexes()[0]
            if selected_uri_index <= len(done_queue):
                prev_track(times=len(done_queue) - selected_uri_index, forced=True)
            else:
                next_track(times=selected_uri_index - len(done_queue), forced=True)
            values = create_track_list()
            dq_len = len(done_queue)
            main_window['queue'].update(values=values, set_to_index=dq_len, scroll_to_index=dq_len)
    elif main_event == 'album' and playing_status.busy(): locate_uri()
    elif main_event in {'locate_uri', 'e:69'}:
        if not settings['mini_mode'] and main_values['queue']:
            for index in main_window['queue'].get_indexes(): locate_uri(index - len(done_queue))
        else: locate_uri()
    elif main_event == 'move_to_next_up':
        for i, index_to_move in enumerate(main_window['queue'].get_indexes(), 1):
            dq_len = len(done_queue)
            nq_len = len(next_queue)
            if index_to_move < dq_len:
                track = done_queue[index_to_move]
                del done_queue[index_to_move]
                if settings['reversed_play_next']: next_queue.insert(0, track)
                else: next_queue.append(track)
                if i == len(main_values['queue']):  # update gui after the last swap
                    values = create_track_list()
                    main_window['queue'].update(values=values, set_to_index=len(done_queue) + len(next_queue),
                                                scroll_to_index=max(len(done_queue) + len(next_queue) - 16, 0))
                    save_queues()
            elif index_to_move > dq_len + nq_len:
                track = music_queue[index_to_move - dq_len - nq_len]
                del music_queue[index_to_move - dq_len - nq_len]
                if settings['reversed_play_next']: next_queue.insert(0, track)
                else: next_queue.append(track)
                if i == len(main_values['queue']):  # update gui after the last swap
                    values = create_track_list()
                    main_window['queue'].update(values=values, set_to_index=dq_len + len(next_queue),
                                                scroll_to_index=max(len(done_queue) + len(next_queue) - 3, 0))
                    save_queues()
    elif main_event == 'move_up':
        for i, index_to_move in enumerate(main_window['queue'].get_indexes(), 1):
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
            if i == len(main_values['queue']):  # update gui after the last swap
                values = create_track_list()
                main_window['queue'].update(values=values, set_to_index=new_i, scroll_to_index=max(new_i - 7, 0))
                save_queues()
    elif main_event == 'move_down':
        for i, index_to_move in enumerate(reversed(main_window['queue'].get_indexes()), 1):
            dq_len, nq_len, mq_len = len(done_queue), len(next_queue), len(music_queue)
            if index_to_move < dq_len + nq_len + mq_len - 1:
                new_i = index_to_move + 1
                if index_to_move == dq_len - 1:  # move index -1 to 1
                    if next_queue:
                        next_queue.insert(0, done_queue.pop())
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
                if i == len(main_values['queue']):  # update gui after the last swap
                    values = create_track_list()
                    main_window['queue'].update(values=values, set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))
                    save_queues()
    elif main_event == 'remove_track' and main_values['queue']:
        for i, index_to_remove in enumerate(reversed(main_window['queue'].get_indexes()), 1):
            dq_len, nq_len, mq_len = len(done_queue), len(next_queue), len(music_queue)
            if index_to_remove < dq_len:
                del done_queue[index_to_remove]
            elif index_to_remove == dq_len:
                with suppress(IndexError):
                    # remove the "0. XXXX" track that could be playing right now
                    music_queue.popleft()
                    if next_queue: music_queue.insert(0, next_queue.popleft())
                    # if queue is empty but repeat is all AND there are tracks in the done_queue
                    if not music_queue and settings['repeat'] is False and done_queue:
                        music_queue.extend(done_queue)
                        done_queue.clear()
                    # start playing new track if a track was being played
                    if not sar.alive:
                        if music_queue and playing_status.busy(): play(music_queue[0])
                        else: stop('remove_track')
            elif index_to_remove <= nq_len + dq_len:
                del next_queue[index_to_remove - dq_len - 1]
            elif index_to_remove < nq_len + mq_len + dq_len:
                del music_queue[index_to_remove - dq_len - nq_len]
            if i == len(main_values['queue']):  # update gui after the last removal
                values = create_track_list()
                new_i = min(len(values), index_to_remove)
                main_window['queue'].update(values=values, set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))
    elif main_event == 'file_option':
        main_window['file_action'].update(text=main_values['file_option'])
    elif main_event == 'folder_option':
        main_window['folder_action'].update(text=main_values['folder_option'])
    elif main_event == 'file_action':
        Thread(target=file_action, name='FileAction', daemon=True,
               args=[main_values['file_option']]).start()
    elif main_event == 'folder_action':
        Thread(target=folder_action, name='FolderAction', daemon=True,
               args=[main_values['folder_option']]).start()
    elif main_event == 'playlist_action':
        playlist_action(main_values['playlists'])
    elif main_event == 'play_all':
        if not any(filter(lambda thread: thread.name == 'PlayAll', threading.enumerate())):
            Thread(target=play_all, name='PlayAll', daemon=True).start()
    elif main_event == 'queue_all': queue_all()
    elif main_event == 'mini_mode':
        change_settings('mini_mode', not settings['mini_mode'])
        main_window.close()
        activate_main_window()
    elif main_event == 'clear_queue':
        main_window['queue'].update(values=[])
        stop('clear queue')
        music_queue.clear()
        next_queue.clear()
        done_queue.clear()
        save_queues()
    elif main_event == 'save_queue':
        pl_tracks = main_window.metadata['pl_tracks'] = []
        pl_tracks.extend(done_queue)
        if music_queue: pl_tracks.append(music_queue[0])
        pl_tracks.extend(next_queue)
        pl_tracks.extend(islice(music_queue, 1, None))
        new_values = [f'{i + 1}. {format_uri(path)}' for i, path in enumerate(pl_tracks)]
        main_window.metadata['pl_name'] = ''
        main_window['tab_playlists'].select()
        main_window['pl_name'].set_focus()
        main_window['pl_name'].update(value=main_window.metadata['pl_name'])
        main_window['pl_tracks'].update(values=new_values, set_to_index=0)
    elif main_event in {'library', 'Play::library', 'Play Next::library', 'Queue::library', 'Locate::library'}:
        library_metadata = main_window.metadata['library']
        if library_metadata['region'] == 'heading':
            col_index = library_metadata['column']
            if col_index == library_metadata['sort_by']:
                reverse = library_metadata['ascending'] = not library_metadata['ascending']
            else:
                library_metadata['sort_by'] = col_index
                reverse = library_metadata['ascending'] = True
            library_items = main_window['library'].Values
            library_items.sort(key=lambda row: row[col_index - 1].lower(), reverse=not reverse)
            main_window['library'].update(library_items)
        elif main_event == 'Locate::library':
            for index in main_values['library']:
                locate_uri(uri=main_window['library'].Values[index][-1])
        elif main_values['library']:
            paths_to_play = (main_window['library'].Values[index][-1] for index in main_values['library'])
            if main_event in {'library', 'Play::library'}:
                if settings['queue_library']: play_all(paths_to_play)
                else: play_uris(paths_to_play)
            else:
                # play_next has priority over queue_uris
                play_uris(paths_to_play, queue_uris=True, play_next=main_event == 'Play Next::library')
    elif main_event == 'progress_bar' and track_length is not None:
        if playing_status.stopped():
            main_window['progress_bar'].update(disabled=True, value=0)
            return
        else:
            track_position = main_values['progress_bar']
            set_pos(track_position)
            track_start = time.monotonic() - track_position
            track_end = track_start + track_length
    # main window settings tab
    elif main_event == 'email':
        Thread(target=webbrowser.open, daemon=True, args=[create_email_url()]).start()
    elif main_event == 'web_gui':
        Thread(target=webbrowser.open, daemon=True, args=[f'http://{get_ipv4()}:{Shared.PORT}']).start()
    # toggle settings
    elif main_event in {'auto_update', 'notifications', 'discord_rpc', 'run_on_startup', 'folder_cover_override',
                        'folder_context_menu', 'save_window_positions', 'populate_queue_startup', 'lang', 'smart_queue',
                        'show_track_number', 'persistent_queue', 'flip_main_window', 'vertical_gui', 'use_last_folder',
                        'show_album_art', 'reversed_play_next', 'scan_folders', 'show_queue_index', 'queue_library'}:
        change_settings(main_event, main_value)
        if main_event == 'run_on_startup':
            create_shortcut()
        elif main_event == 'persistent_queue':
            if main_value: save_queues()
            else: change_settings('queues', {'done': [], 'music': [], 'next': []})
            change_settings('populate_queue_startup', False)
            main_window['populate_queue_startup'].update(value=False)
        elif main_event in 'populate_queue_startup':
            main_window['persistent_queue'].update(value=False)
            change_settings('persistent_queue', False)
        elif main_event == 'discord_rpc':
            with suppress(Exception):
                if main_value:
                    rich_presence = pypresence.Presence(MUSIC_CASTER_DISCORD_ID)
                    if playing_status.busy():
                        metadata = url_metadata['SYSTEM_AUDIO'] if sar.alive else get_uri_metadata(music_queue[0])
                        title, artist = metadata['title'], get_first_artist(metadata['artist'])
                        rich_presence.connect()
                        rich_presence.update(state=gt('By') + f': {artist}', details=title,
                                            large_image='default', large_text='Listening',
                                            small_image='logo', small_text='Music Caster')
                elif not main_value:
                    rich_presence.clear()
        elif main_event in {'show_album_art', 'vertical_gui', 'flip_main_window'}:
            # re-render main GUI
            main_window.close()
            activate_main_window('tab_settings')
        elif main_event in {'show_track_number', 'show_queue_index'}:
            main_window.metadata['update_listboxes'] = True
        elif main_event == 'scan_folders' and main_value:
            index_all_tracks()
        elif main_event == 'folder_cover_override':
            size = COVER_MINI if settings['mini_mode'] else COVER_NORMAL
            try:
                album_art_data = resize_img(get_current_art(), settings['theme']['background'], size).decode()
            except (UnidentifiedImageError, OSError):
                album_art_data = resize_img(DEFAULT_ART, settings['theme']['background'], size).decode()
            main_window['artwork'].update(data=album_art_data)
        elif main_event == 'lang':
            Shared.lang = main_value
            main_window.close()
            activate_main_window('tab_settings')
            refresh_tray()
    elif main_event == 'remove_music_folder' and main_values['music_folders']:
        with suppress(ValueError):
            for selected_item in main_values['music_folders']:
                music_folders.remove(selected_item)
            main_window['music_folders'].update(music_folders)
            refresh_tray()
            save_settings()
            if settings['scan_folders']: index_all_tracks()
    elif main_event == 'add_music_folder':
        initial_folder = settings['last_folder'] if settings['use_last_folder'] else DEFAULT_FOLDER
        folder_path = Sg.popup_get_folder(gt('Select Folder'), initial_folder=initial_folder, no_window=True,
                                          icon=WINDOW_ICON)
        if folder_path: add_music_folder([folder_path])
    elif main_event in {'settings_file', 'o:79'}:
        try:
            os.startfile(SETTINGS_FILE)
        except OSError:
            Popen(f'explorer /select,"{fix_path(SETTINGS_FILE)}"')
    elif main_event == 'changelog_file':
        with suppress(FileNotFoundError):
            os.startfile('changelog.txt')
    elif main_event == 'music_folders':
        with suppress(IndexError):
            Popen(f'explorer "{fix_path(main_values["music_folders"][0])}"')
    # url tab
    elif main_event == 'url_input':
        main_window.metadata['url_input'] = main_value
    elif main_event == 'url_input_cut':
        cut_text = get_cut_text(main_window, 'url_input')
        if cut_text:
            pyperclip.copy(cut_text)
            main_window.metadata['url_input'] = main_window['url_input'].get()
    elif main_event == 'url_input_copy':
        with suppress(tkinter.TclError):
            pyperclip.copy(main_window['url_input'].Widget.selection_get())
    elif (main_event in {'\r', 'special 16777220', 'special 16777221', 'url_submit'}
          and main_values.get('tab_group') == 'tab_url' and main_values['url_input']):
        urls_to_insert = main_values['url_input'].strip()
        if '\n' in urls_to_insert: urls_to_insert = urls_to_insert.split('\n')
        else: urls_to_insert = urls_to_insert.split(';')
        main_window['url_input'].update(value='')
        if main_values['url_play'] or not music_queue:
            music_queue.extendleft(reversed(urls_to_insert))
            main_window['url_msg'].update(gt('Loading URL(s)'), text_color='yellow')
            main_window.read(1)
            play(music_queue[0])
            main_window['url_msg'].update('')
            urls_to_insert.pop(0)
        elif main_values['url_queue']:
            music_queue.extend(urls_to_insert)
            main_window['url_msg'].update(gt('Added URL(s)'), text_color='green')
            main_window.TKroot.after(2000, lambda: main_window['url_msg'].update(value=''))
        else:  # add to next queue
            if settings['reversed_play_next']: next_queue.extendleft(reversed(urls_to_insert))
            else: next_queue.extend(urls_to_insert)
            main_window['url_msg'].update(gt('Added URL(s)'), text_color='green')
            main_window.TKroot.after(2000, lambda: main_window['url_msg'].update(value=''))
        for inserted_url in urls_to_insert: uris_to_scan.put(inserted_url)
        main_window['url_input'].set_focus()
        main_window.metadata['update_listboxes'] = True
    # timer tab
    elif main_event == 'cancel_timer':
        main_window['timer_text'].update('No Timer Set')
        main_window['timer_text'].metadata = False
        main_window['timer_error'].update(visible=False)
        main_window['cancel_timer'].update(visible=False)
    # handle enter/submit event
    elif (main_event in {'\r', 'special 16777220', 'special 16777221', 'timer_submit'}
          and main_values.get('tab_group') == 'tab_timer'):
        try:
            timer_value: str = main_values['timer_input']
            timer_set_to = set_timer(timer_value)
            main_window['timer_text'].update(f'Timer set for {timer_set_to}')
            main_window['timer_text'].metadata = True
            main_window['cancel_timer'].update(visible=True)
            main_window['timer_error'].update(visible=False)
            main_window['timer_input'].update(value='')
            main_window['timer_input'].set_focus()
        except ValueError:
            # flash timer error
            for i in range(3):
                main_window['timer_error'].update(visible=True, text_color='#ffcccb')
                main_window.read(10)
                main_window['timer_error'].update(text_color='red')
                main_window.read(10)
            main_window['timer_input'].set_focus()
    elif main_event in {'shut_down', 'hibernate', 'sleep', 'timer_stop'}:
        change_settings('timer_hibernate', main_values['hibernate'])
        change_settings('timer_sleep', main_values['sleep'])
        change_settings('timer_shut_down', main_values['shut_down'])
    # playlists tab
    elif main_event == 'playlist_combo':
        # user selected a playlist from the drop-down
        pl_name = main_window.metadata['pl_name'] = main_value if main_value in settings['playlists'] else ''
        pl_tracks = main_window.metadata['pl_tracks'] = settings['playlists'].get(pl_name, []).copy()
        main_window['pl_name'].update(value=pl_name)
        new_values = [f'{i + 1}. {format_uri(path)}' for i, path in enumerate(pl_tracks)]
        main_window['pl_tracks'].update(values=new_values, set_to_index=0)
    elif main_event in {'new_pl', 'n:78'}:
        main_window.metadata['pl_name'] = ''
        main_window.metadata['pl_tracks'] = []
        main_window['pl_name'].update(value='')
        main_window['pl_name'].set_focus()
        main_window['pl_tracks'].update(values=[])
        main_window['playlist_combo'].update(value='')
    elif main_event == 'export_pl':
        if main_values['playlist_combo'] and settings['playlists'].get(main_values['playlist_combo']):
            playlist_uris = settings['playlists'][main_values['playlist_combo']]
            playlist_path = export_playlist(main_values['playlist_combo'], playlist_uris)
            locate_uri(uri=playlist_path)
    elif main_event == 'delete_pl':
        pl_name = main_window.metadata['pl_name'] = main_values.get('playlist_combo', '')
        settings['playlists'].pop(pl_name, None)
        pl_name = main_window.metadata['pl_name'] = next(iter(settings['playlists']), '')
        main_window['playlist_combo'].update(value=pl_name, values=tuple(settings['playlists']))
        pl_tracks = main_window.metadata['pl_tracks'] = settings['playlists'].get(pl_name, []).copy()
        new_values = [f'{i + 1}. {format_uri(path)}' for i, path in enumerate(pl_tracks)]
        # update playlist editor
        main_window['pl_name'].update(value=pl_name)
        main_window['pl_tracks'].update(values=new_values, set_to_index=0)
        save_settings()
        refresh_tray()
    elif main_event == 'play_pl':
        temp_lst = settings['playlists'].get(main_values['playlist_combo'], [])
        if temp_lst:
            done_queue.clear()
            music_queue.clear()
            music_queue.extend(temp_lst)
            if settings['shuffle']: shuffle(music_queue)
            play(music_queue[0])
    elif main_event == 'queue_pl':
        playlist_action(main_values['playlist_combo'], 'queue')
        main_window.metadata['update_listboxes'] = True
    elif main_event == 'add_next_pl':
        playlist_action(main_values['playlist_combo'], 'next')
        main_window.metadata['update_listboxes'] = True
    elif main_event in {'pl_save', 's:83'} and main_values.get('tab_group') == 'tab_playlists':
        # save playlist
        if main_values['pl_name']:
            pl_name = main_window.metadata['pl_name']
            save_name = main_values['pl_name']
            if pl_name != save_name:
                # if user is renaming a playlist, remove old data
                settings['playlists'].pop(pl_name, '')
                pl_name = main_window.metadata['pl_name'] = save_name
            settings['playlists'][pl_name] = main_window.metadata['pl_tracks']
            # sort playlists alphabetically
            playlist_names = sorted(settings['playlists'])
            settings['playlists'] = {k: settings['playlists'][k] for k in playlist_names}
            main_window['playlist_combo'].update(value=pl_name, values=playlist_names)
        save_settings()
        refresh_tray()
    elif main_event in {'pl_rm_items', 'q:81'} and main_values['pl_tracks']:
        # remove items from playlist
        # remove bottom to top to avoid dynamic indices
        pl_tracks = main_window.metadata['pl_tracks']
        for i, to_remove in enumerate(reversed(main_window['pl_tracks'].get_indexes()), 1):
            pl_tracks.pop(to_remove)
            if i == len(main_values['pl_tracks']):  # update gui after the last removal
                scroll_to_index = max(to_remove - 3, 0)
                new_values = [f'{j + 1}. {format_uri(path)}' for j, path in enumerate(pl_tracks)]
                main_window['pl_tracks'].update(new_values, set_to_index=to_remove, scroll_to_index=scroll_to_index)
    elif main_event == 'pl_add_tracks':
        initial_folder = settings['last_folder'] if settings['use_last_folder'] else DEFAULT_FOLDER
        file_paths = Sg.popup_get_file('Select Music File(s)', no_window=True, initial_folder=initial_folder,
                                       multiple_files=True, file_types=AUDIO_FILE_TYPES, icon=WINDOW_ICON)
        if file_paths:
            pl_tracks = main_window.metadata['pl_tracks']
            pl_tracks.extend(get_audio_uris(file_paths))
            settings['last_folder'] = os.path.dirname(file_paths[-1])
            main_window.TKroot.focus_force()
            main_window.normal()
            new_values = [f'{i + 1}. {format_uri(path)}' for i, path in enumerate(pl_tracks)]
            new_i = len(new_values) - 1
            main_window['pl_tracks'].update(new_values, set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))
    elif main_event == 'pl_url_input':
        main_window.metadata['pl_url_input'] = main_value
    elif main_event == 'pl_url_input_cut':
        cut_text = get_cut_text(main_window, 'pl_url_input')
        if cut_text:
            pyperclip.copy(cut_text)
            main_window.metadata['pl_url_input'] = main_window['pl_url_input'].get()
    elif main_event == 'pl_url_input_copy':
        with suppress(tkinter.TclError):
            pyperclip.copy(main_window['pl_url_input'].Widget.selection_get())
    elif main_event == 'pl_add_url':
        links = main_values['pl_url_input']
        if '\n' in links: links = links.split('\n')
        else: links = links.split(';')
        for link in links:
            if link.startswith('http://') or link.startswith('https://'):
                uris_to_scan.put(link)
                pl_tracks = main_window.metadata['pl_tracks']
                pl_tracks.append(link)
                new_values = [f'{i + 1}. {format_uri(path)}' for i, path in enumerate(pl_tracks)]
                new_i = len(new_values) - 1
                main_window['pl_tracks'].update(new_values, set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))
                # empty the input field
                main_window['pl_url_input'].update(value='')
                main_window['pl_url_input'].set_focus()
            else:
                tray_notify(gt('ERROR') + ': ' + gt("Invalid URL. URL's need to start with http:// or https://"))
    elif main_event == 'pl_move_up':
        # only allow moving up if 1 item is selected and pl_files is not empty
        for i, to_move in enumerate(main_window['pl_tracks'].get_indexes(), 1):
            if to_move:  # can't move the first index up
                new_i = to_move - 1
                pl_tracks = main_window.metadata['pl_tracks']
                pl_tracks.insert(new_i, pl_tracks.pop(to_move))
                if i == len(main_values['pl_tracks']):  # update gui after the last swap
                    new_values = [f'{j + 1}. {format_uri(path)}' for j, path in enumerate(pl_tracks)]
                    main_window['pl_tracks'].update(new_values, set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))
    elif main_event == 'pl_move_down':
        # only allow moving down if 1 item is selected and pl_files is not empty
        for i, to_move in enumerate(main_window['pl_tracks'].get_indexes(), 1):
            pl_tracks = main_window.metadata['pl_tracks']
            if to_move < len(pl_tracks) - 1:
                new_i = to_move + 1
                pl_tracks.insert(new_i, pl_tracks.pop(to_move))
                if i == len(main_values['pl_tracks']):  # update gui after the last swap
                    new_values = [f'{i + 1}. {format_uri(path)}' for i, path in enumerate(pl_tracks)]
                    main_window['pl_tracks'].update(new_values, set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))
    elif main_event in {'pl_locate_selected', 'pl_tracks'}:
        for i in main_window['pl_tracks'].get_indexes(): locate_uri(uri=main_window.metadata['pl_tracks'][i])
    elif main_event in {'play_pl_selected', 'queue_pl_selected', 'add_next_pl_selected'}:
        uris = (main_window.metadata['pl_tracks'][i] for i in main_window['pl_tracks'].get_indexes())
        play_uris(uris, queue_uris=main_event == 'queue_pl_selected',
                  play_next=main_event == 'add_next_pl_selected', sort=settings['shuffle'])
    # metadata tab
    elif main_event in {'metadata_browse', 'metadata_file'}:
        initial_folder = settings['last_folder'] if settings['use_last_folder'] else DEFAULT_FOLDER
        selected_file = Sg.popup_get_file('Select audio file', initial_folder=initial_folder, no_window=True,
                                          file_types=AUDIO_FILE_TYPES, icon=WINDOW_ICON)
        metadata_process_file(selected_file)
    elif main_event == 'metadata_select_art' and main_window['metadata_file'].get():
        selected_file = Sg.popup_get_file('Select image/audio file', no_window=True,
                                          file_types=IMG_FILE_TYPES, icon=WINDOW_ICON)
        if selected_file:
            if os.path.splitext(selected_file)[1][1:].lower() in AUDIO_EXTS:
                mime, artwork = get_album_art(selected_file)
            else:
                img = Image.open(selected_file)
                data = io.BytesIO()
                img.save(data, format='jpeg', quality=95)
                mime, artwork = 'image/jpeg', b64encode(data.getvalue())
            _, display_art = main_window['metadata_art'].metadata = (mime, None if artwork == DEFAULT_ART else artwork)
            if display_art is not None:
                display_art = resize_img(display_art, settings['theme']['background'], COVER_MINI)
            main_window['metadata_art'].update(data=display_art)
    elif main_event == 'metadata_search_art' and main_window['metadata_file'].get():
        # search for artwork using spotify API
        main_window['metadata_msg'].update(value=gt('Searching for artwork...'), text_color='yellow')
        found_artwork = False
        for mkt in ('MX', 'CA', 'US', 'UK', 'HK'):
            title = main_values['metadata_title']
            artist = main_values['metadata_artist']
            url = f'https://api.spotify.com/v1/search?q={title}'
            if artist: url += f'+artist:{artist}'
            url += f'&type=track&market={mkt}'
            r = requests.get(url, headers=get_spotify_headers()).json()
            if 'tracks' in r:
                for art_link in (item['album']['images'][0]['url'] for item in r['tracks']['items']):
                    display_art = base64.b64encode(requests.get(art_link).content)
                    main_window['metadata_art'].metadata = ('image/jpeg', display_art)
                    display_art = resize_img(display_art, settings['theme']['background'], COVER_MINI)
                    main_window['metadata_art'].update(data=display_art)
                    found_artwork = True
                    break
        if found_artwork:
            main_window['metadata_msg'].update(value=gt('Artwork found'), text_color='green')
            main_window.TKroot.after(2000, lambda: main_window['metadata_msg'].update(value=''))
        else:
            main_window['metadata_msg'].update(value=gt('No artwork found'), text_color='red')
            main_window.TKroot.after(2000, lambda: main_window['metadata_msg'].update(value=''))
    elif main_event == 'metadata_remove_art':
        main_window['metadata_art'].metadata = (None, None)
        main_window['metadata_art'].update(data=None)
    elif main_event in {'metadata_save', 's:83'} and main_values.get('tab_group') == 'tab_metadata':
        if main_window['metadata_file'].get():
            mime, art = main_window['metadata_art'].metadata
            new_metadata = {'title': main_values['metadata_title'], 'artist': main_values['metadata_artist'],
                            'album': main_values['metadata_album'], 'track_number': main_values['metadata_track_num'],
                            'explicit': main_values['metadata_explicit'], 'mime': mime, 'art': art}
            main_window['metadata_msg'].update(value=gt('Saving metadata'), text_color='yellow')
            try:
                set_metadata(main_window['metadata_file'].get(), new_metadata)
                main_window['metadata_msg'].update(value=gt('Metadata saved'), text_color='green')
            except ValueError as e:  # track number incorrectly entered
                main_window['metadata_msg'].update(value=f'ERROR: {e}', text_color='red')
            main_window.TKroot.after(2000, lambda: main_window['metadata_msg'].update(value=''))
            main_window['title'].update(' ' + main_window['title'].DisplayText + ' ')  # try updating now playing
    # other GUI updates
    if main_window.metadata['update_listboxes'] and not settings['mini_mode']:
        main_window.metadata['update_listboxes'] = False
        dq_len = len(done_queue)
        lb_tracks = create_track_list()
        main_window['queue'].update(values=lb_tracks, set_to_index=dq_len, scroll_to_index=dq_len)
        pl_tracks = main_window.metadata['pl_tracks']
        pl_formatted = [f'{i + 1}. {format_uri(pl_track)}' for i, pl_track in enumerate(pl_tracks)]
        main_window['pl_tracks'].update(values=pl_formatted)
        if len(all_tracks) != len(main_window['library'].Values):
            lib_data = [[track['title'], get_first_artist(track['artist']), track['album'], uri] for uri, track in
                        index_all_tracks(False).items()]
            main_window['library'].update(values=lib_data)
    if main_window.metadata['update_volume_slider']:
        main_window['mute'].update(image_data=VOLUME_MUTED_IMG if settings['muted'] else VOLUME_IMG)
        main_window['mute'].set_tooltip(gt('unmute') if settings['muted'] else gt('mute'))
        main_window['volume_slider'].update(0 if settings['muted'] else settings['volume'])
        main_window.metadata['update_volume_slider'] = False
    # update progress bar
    progress_bar: Sg.Slider = main_window['progress_bar']
    time_elapsed_text, time_left_text = create_progress_bar_text(get_track_position(), track_length)
    if time_elapsed_text != main_window['time_elapsed'].get(): main_window['time_elapsed'].update(time_elapsed_text)
    if time_left_text != main_window['time_left'].get(): main_window['time_left'].update(time_left_text)
    if music_queue and playing_status.busy() and not sar.alive: progress_bar.update(floor(track_position))
    return True


def create_shortcut():
    """ Creates short-cut in Startup folder (enter "startup" in Explorer address bar to)
        if setting['run_on_startup'], else removes existing shortcut """
    def _create_shortcut():
        app_log.info('create_shortcut called')
        startup_dir = shell.SHGetFolderPath(0, (shellcon.CSIDL_STARTUP, shellcon.CSIDL_COMMON_STARTUP)[0], None, 0)
        debug = settings.get('DEBUG', DEBUG)
        shortcut_path = f"{startup_dir}\\Music Caster{' (DEBUG)' if debug else ''}.lnk"
        with suppress(com_error):
            shortcut_exists = os.path.exists(shortcut_path)
            if settings['run_on_startup'] or debug:
                # noinspection PyUnresolvedReferences
                pythoncom.CoInitialize()
                _shell = win32com.client.Dispatch('WScript.Shell')
                shortcut = _shell.CreateShortCut(shortcut_path)
                if IS_FROZEN:
                    target = f'{working_dir}\\Music Caster.exe'
                else:
                    target = f'{working_dir}\\music_caster.bat'
                    if os.path.exists(target):
                        with open('music_caster.bat', 'w') as f:
                            f.write(f'pythonw "{os.path.basename(sys.argv[0])}" -m')
                    shortcut.IconLocation = f'{working_dir}\\resources\\Music Caster Icon.ico'
                shortcut.Targetpath = target
                shortcut.Arguments = '-m'
                shortcut.WorkingDirectory = working_dir
                shortcut.WindowStyle = 1  # 7: Minimized, 3: Maximized, 1: Normal
                shortcut.save()
                if debug:
                    time.sleep(1)
                    os.remove(shortcut_path)
            elif not settings['run_on_startup'] and shortcut_exists: os.remove(shortcut_path)
    Thread(target=_create_shortcut, name='CreateShortcut').start()


def get_latest_release(ver, force=False):
    """ returns {'version': latest_ver, 'setup': 'setup_link'} if the latest release version is newer (>) than VERSION
    if latest release version <= VERSION, returns false
    if force: return latest release even if latest version <= VERSION """
    releases_url = 'https://api.github.com/repos/elibroftw/music-caster/releases/latest'
    release = requests.get(releases_url).json()
    latest_ver = release.get('tag_name', f'v{VERSION}')[1:]
    _version = [int(x) for x in ver.split('.')]
    compare_ver = [int(x) for x in latest_ver.split('.')]
    if compare_ver > _version or force:
        for asset in release.get('assets', []):
            # check if setup exists
            if 'exe' in asset['name']:
                return {'version': latest_ver, 'setup': asset['browser_download_url']}
    return False


def auto_update():
    """ auto_start should be True when checking for updates at startup up,
        false when checking for updates before exiting """
    with suppress(requests.RequestException):
        app_log.info(f'Function called: auto_update()')
        release = get_latest_release(VERSION, force=(not IS_FROZEN or settings.get('DEBUG', DEBUG)))
        if release:
            latest_ver = release['version']
            setup_dl_link = release['setup']
            app_log.info(f'Update found: v{latest_ver}')
            print('Installer Link:', setup_dl_link)
            if settings.get('DEBUG', DEBUG) or not setup_dl_link: return
            if IS_FROZEN:
                if os.path.exists(UNINSTALLER):
                    # only show message on startup to not confuse the user
                    cmd = 'mc_installer.exe /VERYSILENT /FORCECLOSEAPPLICATIONS /MERGETASKS="!desktopicon"'
                    cmd_args = ' '.join(sys.argv[1:])
                    cmd += f' && "Music Caster.exe" -m {cmd_args}'  # auto start is True when updating on startup
                    download_update = gt('Downloading update $VER').replace('$VER', latest_ver)
                    tray_notify(download_update)
                    tray_tooltip = download_update
                    tray_process_queue.put({'tooltip': tray_tooltip})
                    try:
                        # download setup, close tray, run setup, and exit
                        download(setup_dl_link, 'mc_installer.exe')
                        close_tray()
                        Popen(cmd, shell=True)
                        sys.exit()
                    except OSError as e:
                        if e.errno == errno.ENOSPC:
                            tray_notify(gt('ERROR') + ': ' + gt('No space left on device to auto-update'))
                    except (ConnectionAbortedError, ProtocolError):
                        tray_notify('update_available', context=latest_ver)
                elif os.path.exists('Updater.exe'):
                    # portable installation
                    try:
                        os.startfile('Updater.exe')
                        close_tray()
                        sys.exit()
                    except OSError as e:
                        if e == errno.ECANCELED:
                            # user cancelled update, don't try auto-updating again
                            # inform user what we were trying to do though
                            change_settings('auto_update', False)
                            if settings['notifications']:
                                tray_notify('update_available', context=latest_ver)
                else:
                    # unins000.exe or updater.exe was deleted; better to inform user there is an update available
                    if settings['notifications']: tray_notify('update_available', context=latest_ver)


def send_info():
    with suppress(requests.RequestException):
        mac = hashlib.md5(get_mac().encode()).hexdigest()
        requests.post('https://en3ay96poz86qa9.m.pipedream.net', json={'MAC': mac, 'VERSION': VERSION})


def handle_action(action):
    actions = {
        '__ACTIVATED__': activate_main_window,
        'update_gui': _update_gui,
        # from tray menu
        gt('Rescan Library'): index_all_tracks,
        gt('Refresh Devices'): lambda: start_chromecast_discovery(start_thread=True),
        # isdigit should be an if statement
        gt('Settings'): lambda: activate_main_window('tab_settings'),
        gt('Playlists Menu'): lambda: activate_main_window('tab_playlists'),
        # PL should be an if statement
        gt('Set Timer'): lambda: activate_main_window('tab_timer'),
        gt('Cancel Timer'): cancel_timer,
        gt('System Audio'): play_system_audio,
        gt('Play URL'): lambda: activate_main_window('tab_url', 'url_play'),
        gt('Queue URL'): lambda: activate_main_window('tab_url', 'url_queue'),
        gt('Play URL Next'): lambda: activate_main_window('tab_url', 'url_play_next'),
        gt('Play File(s)'): file_action,
        gt('Queue File(s)'): lambda: file_action('qf'),
        gt('Play File(s) Next'): lambda: file_action('pfn'),
        gt('Play All'): play_all,
        gt('Pause'): pause,
        gt('Resume'): resume,
        gt('next track', 1): next_track,
        gt('previous track', 1): prev_track,
        gt('Stop'): lambda: stop('tray'),
        gt('Repeat One'): lambda: change_settings('repeat', True),
        gt('Repeat All'): lambda: change_settings('repeat', False),
        gt('Repeat Off'): lambda: change_settings('repeat', None),
        gt('locate track', 1): locate_uri,
        gt('Exit'): exit_program
    }
    actions.get(action, lambda: other_tray_actions(action))()


if __name__ == '__main__':
    log_format = logging.Formatter('%(asctime)s %(levelname)s (%(lineno)d): %(message)s')
    log_handler = RotatingFileHandler('music_caster.log', maxBytes=5242880, backupCount=1, encoding='UTF-8')
    log_handler.setFormatter(log_format)
    app_log = logging.getLogger('music_caster')
    app_log.setLevel(logging.INFO)
    app_log.addHandler(log_handler)
    app_log.propagate = False  # disable console output
    try:
        load_settings(True)  # starts indexing all tracks
        if settings['notifications']:
            if settings['update_message'] == '': tray_notify(WELCOME_MSG)
            elif settings['update_message'] != UPDATE_MESSAGE: tray_notify(UPDATE_MESSAGE)
        change_settings('update_message', UPDATE_MESSAGE)
        # check for update and update if no must run arguments were provided or if the update flag was used
        if (len(sys.argv) == 1 or ['-m'] == sys.argv[1:]) and settings['auto_update'] or args.update: auto_update()
        # set file handlers only if installed from the setup (Not a portable installation)
        if os.path.exists(UNINSTALLER):
            with suppress(PermissionError):
                add_reg_handlers(f'{working_dir}/Music Caster.exe', add_folder_context=settings['folder_context_menu'])

        with suppress(FileNotFoundError, OSError): os.remove('mc_installer.exe')
        rmtree('Update', ignore_errors=True)

        # find a port to bind to
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.05)
            while True:
                if not s.connect_ex(('127.0.0.1', Shared.PORT)) == 0:  # if port is not occupied
                    with suppress(OSError):
                        # try to start server and bind it to PORT
                        server_kwargs = {'host': '0.0.0.0', 'port': Shared.PORT, 'threaded': True}
                        Thread(target=app.run, name='FlaskServer', daemon=True, kwargs=server_kwargs).start()
                        break
                Shared.PORT += 1  # port in use or failed to bind to port
        print(f'Running on http://127.0.0.1:{Shared.PORT}/')
        with suppress(Exception):
            rich_presence = pypresence.Presence(MUSIC_CASTER_DISCORD_ID)
            if settings['discord_rpc']:
                 rich_presence.connect()
        temp = (settings['timer_shut_down'], settings['timer_hibernate'], settings['timer_sleep'])
        if temp.count(True) > 1:  # Only one of the below can be True
            if settings['timer_shut_down']: change_settings('timer_hibernate', False)
            change_settings('timer_sleep', False)
        if settings['persistent_queue'] and settings['populate_queue_startup']:  # mutually exclusive
            change_settings('populate_queue_startup', False)
        cast_last_checked = time.monotonic()
        Thread(target=background_tasks, daemon=True, name='BackgroundTasks').start()
        start_chromecast_discovery(start_thread=True)
        audio_player = AudioPlayer()
        if args.uris:
            # wait until previous device has been found or if it hasn't been found
            while all((settings['previous_device'], cast is None, stop_discovery_browser)): time.sleep(0.3)
            play_uris(args.uris, queue_uris=args.queue, play_next=args.playnext)
        elif settings['persistent_queue']:
            # load saved queues from settings.json
            for queue_name in ('done', 'music', 'next'):
                queue = {'done': done_queue, 'music': music_queue, 'next': next_queue}[queue_name]
                for file_or_url in settings['queues'].get(queue_name, []):
                    if valid_audio_file(file_or_url) or file_or_url.startswith('http'):
                        queue.append(file_or_url)
                        uris_to_scan.put(file_or_url)
        elif settings['populate_queue_startup']:
            try:
                indexing_tracks_thread.join()
                play_all(queue_only=True)
            except RuntimeError:
                tray_notify(gt('ERROR') + ':' + gt('Could not populate queue because library scan is disabled'))
        if args.resume_playback and not args.uris:
            if music_queue:
                play(music_queue[0])
        if args.start_playing and not args.uris:
            if music_queue:
                play(music_queue[0])
            else:
                play_all()
        # open window if minimized argument not given
        if not args.minimized and not settings.get('DEBUG', False):
            daemon_commands.put('__ACTIVATED__')
        while True:
            while not daemon_commands.empty(): handle_action(daemon_commands.get())
            if playing_status.playing() and track_length is not None and time.monotonic() > track_end:
                next_track(from_timeout=time.monotonic() > track_end)
            elif timer and time.time() > timer:
                stop('timer')
                timer = 0
                if settings['timer_shut_down']:
                    os.system('shutdown /p /f') if platform.system() == 'Windows' else os.system('shutdown -h now')
                elif settings['timer_hibernate']:
                    if platform.system() == 'Windows': os.system(r'rundll32.exe powrprof.dll,SetSuspendState Hibernate')
                elif settings['timer_sleep']:
                    if platform.system() == 'Windows': os.system('rundll32.exe powrprof.dll,SetSuspendState 0,1,0')
            time.sleep(0.2) if main_window.was_closed() else read_main_window()
    except Exception as exception:
        # try to auto-update before exiting
        if not settings.get('DEBUG', False): auto_update()
        handle_exception(exception, True)
